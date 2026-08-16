from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, RequireMember, RequireOwner, SessionDep
from app.models import Membership, Project, Role, User
from app.schemas.project import ProjectCreate, ProjectFull, ProjectInfo, ProjectUpdate
from app.services import storage

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectInfo, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, user: CurrentUser, session: SessionDep):
    project = Project(name=data.name, description=data.description)
    session.add(project)
    await session.flush()  # assigns project.id without committing

    session.add(Membership(user_id=user.id, project_id=project.id, role=Role.OWNER))
    await session.commit()  # project + ownership land atomically, or not at all
    await session.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectFull])
async def list_projects(user: CurrentUser, session: SessionDep):
    stmt = (
        select(Project, Membership.role)
        .join(Membership, Membership.project_id == Project.id)
        .where(Membership.user_id == user.id)
        .options(selectinload(Project.documents))  # one extra query, not one per project
        .order_by(Project.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        ProjectFull.model_validate(project).model_copy(update={"role": role})
        for project, role in rows
    ]


@router.get("/project/{project_id}/info", response_model=ProjectInfo)
async def get_project_info(project_id: int, membership: RequireMember, session: SessionDep):
    return await session.get(Project, project_id)


@router.put("/project/{project_id}/info", response_model=ProjectInfo)
async def update_project_info(
    project_id: int,
    data: ProjectUpdate,
    membership: RequireMember,  # participants may edit
    session: SessionDep,
):
    project = await session.get(Project, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


@router.delete("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, membership: RequireOwner, session: SessionDep):
    project = await session.get(Project, project_id)
    await session.delete(project)  # cascades to documents + memberships
    await session.commit()
    # DB first, files second: failing here leaves orphan files (cheap to sweep)
    # rather than rows pointing at deleted files (broken downloads).
    await storage.delete_prefix(f"projects/{project_id}")


@router.post("/project/{project_id}/invite", status_code=status.HTTP_204_NO_CONTENT)
async def invite_user(
    project_id: int,
    membership: RequireOwner,
    session: SessionDep,
    user: str = Query(..., description="login of the user to invite"),
):
    invitee = (await session.scalars(select(User).where(User.login == user))).first()
    if invitee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    existing = await session.get(
        Membership, {"user_id": invitee.id, "project_id": project_id}
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "User already has access")

    session.add(
        Membership(user_id=invitee.id, project_id=project_id, role=Role.PARTICIPANT)
    )
    await session.commit()