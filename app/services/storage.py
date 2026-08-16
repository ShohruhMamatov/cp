import shutil
import uuid
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from app.core.config import settings

BASE_DIR = settings.storage_path


def build_key(project_id: int, extension: str) -> str:
    """Storage key, laid out to mirror the S3 prefix scheme we move to later."""
    return f"projects/{project_id}/documents/{uuid.uuid4().hex}{extension}"


def _resolve(key: str) -> Path:
    path = (BASE_DIR / key).resolve()
    if not path.is_relative_to(BASE_DIR):
        raise ValueError(f"key escapes storage root: {key}")
    return path


async def save_fileobj(fileobj, key: str) -> int:
    """Write the upload to disk; return the bytes actually written."""

    def _write() -> int:
        path = _resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fileobj.seek(0)
        with path.open("wb") as dst:
            shutil.copyfileobj(fileobj, dst, length=1024 * 1024)
        return path.stat().st_size

    return await run_in_threadpool(_write)


async def delete_object(key: str) -> None:
    def _delete() -> None:
        _resolve(key).unlink(missing_ok=True)

    await run_in_threadpool(_delete)


async def delete_prefix(prefix: str) -> None:
    def _delete() -> None:
        target = _resolve(prefix)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)

    await run_in_threadpool(_delete)


def local_path(key: str) -> Path:
    """Local-storage only. The S3 version returns a presigned URL instead."""
    return _resolve(key)