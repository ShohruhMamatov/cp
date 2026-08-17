import os

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireMember, SessionDep, get_membership
from app.core.config import ALLOWED_CONTENT_TYPES, settings
from app.models import Document, Project, User
from app.schemas.document import DocumentOut
from app.services import storage
from typing import Annotated

router = APIRouter(tags=["documents"])


def _file_size(upload: UploadFile) -> int:
    upload.file.seek(0, os.SEEK_END)
    size = upload.file.tell()
    upload.file.seek(0)
    return size


def _validate(upload: UploadFile) -> str:
    """Check type and per-file size; return the canonical extension."""
    extension = ALLOWED_CONTENT_TYPES.get(upload.content_type or "")
    if extension is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type: {upload.content_type}",
        )
    if _file_size(upload) > settings.max_file_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"'{upload.filename}' exceeds the {settings.max_file_bytes} byte limit",
        )
    return extension


async def _load_document(session: AsyncSession, user: User, document_id: int) -> Document:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    await get_membership(session, user.id, document.project_id)  # 404 if no access
    return document


@router.get("/project/{project_id}/documents", response_model=list[DocumentOut])
async def list_documents(project_id: int, membership: RequireMember, session: SessionDep):
    stmt = select(Document).where(Document.project_id == project_id).order_by(Document.id)
    return list(await session.scalars(stmt))


@router.post(
    "/project/{project_id}/documents",
    response_model=list[DocumentOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    project_id: int,
    membership: RequireMember,
    user: CurrentUser,
    session: SessionDep,
    files: Annotated[list[UploadFile], File()],
):
    project = await session.get(Project, project_id)

    # Validate the whole batch before writing anything — a half-written batch
    # is worse than a rejected one.
    extensions = [_validate(upload) for upload in files]
    incoming = sum(_file_size(upload) for upload in files)

    if project.total_size_bytes + incoming > settings.max_project_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Project storage limit exceeded")

    created: list[Document] = []
    written = 0
    for upload, extension in zip(files, extensions, strict=True):
        key = storage.build_key(project_id, extension)
        size = await storage.save_fileobj(upload.file, key)
        written += size
        document = Document(
            project_id=project_id,
            filename=upload.filename,
            storage_key=key,
            content_type=upload.content_type,
            size_bytes=size,
            uploaded_by=user.id,
        )
        session.add(document)
        created.append(document)

    project.total_size_bytes += written
    await session.commit()
    for document in created:
        await session.refresh(document)
    return created


@router.get("/document/{document_id}")
async def download_document(document_id: int, user: CurrentUser, session: SessionDep):
    document = await _load_document(session, user, document_id)
    path = storage.local_path(document.storage_key)
    if not path.is_file():
        raise HTTPException(status.HTTP_410_GONE, "File is missing from storage")
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.filename,  # sets Content-Disposition: attachment
    )


@router.put("/document/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: int,
    user: CurrentUser,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
):
    document = await _load_document(session, user, document_id)
    extension = _validate(file)

    project = await session.get(Project, document.project_id)
    old_size = document.size_bytes
    if project.total_size_bytes - old_size + _file_size(file) > settings.max_project_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Project storage limit exceeded")

    # Write to a NEW key, then delete the old one after the commit. If the
    # commit fails, the original file is untouched and the row still points at it.
    old_key = document.storage_key
    new_key = storage.build_key(document.project_id, extension)
    size = await storage.save_fileobj(file.file, new_key)

    document.filename = file.filename
    document.storage_key = new_key
    document.content_type = file.content_type
    document.size_bytes = size
    project.total_size_bytes = project.total_size_bytes - old_size + size
    await session.commit()

    await storage.delete_object(old_key)
    await session.refresh(document)
    return document


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: int, user: CurrentUser, session: SessionDep):
    document = await _load_document(session, user, document_id)
    project = await session.get(Project, document.project_id)

    key = document.storage_key
    project.total_size_bytes = max(0, project.total_size_bytes - document.size_bytes)
    await session.delete(document)
    await session.commit()
    await storage.delete_object(key)
