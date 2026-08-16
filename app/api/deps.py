from typing import Annotated, Any, Callable, Coroutine

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_session
from app.models import Membership, Role, User

bearer_scheme = HTTPBearer(auto_error=True)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: SessionDep,
) -> User:
    try:
        user_id = decode_token(credentials.credentials)
    except (JWTError, KeyError, ValueError) as exc:
        raise _unauthorized() from exc

    user = await session.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_membership(
    session: AsyncSession, user_id: int, project_id: int
) -> Membership:
    membership = await session.get(
        Membership, {"user_id": user_id, "project_id": project_id}
    )
    if membership is None:
        # 404, not 403: a 403 would confirm the project exists to someone
        # with no right to know that.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return membership


def require_role(*allowed: Role) -> Callable[..., Coroutine[Any, Any, Membership]]:
    """Dependency *factory* — returns a closure so each route can declare
    its own permission level in the signature."""

    async def dependency(
        session: SessionDep,
        user: CurrentUser,
        project_id: int = Path(...),
    ) -> Membership:
        membership = await get_membership(session, user.id, project_id)
        if membership.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Insufficient permissions for this project"
            )
        return membership

    return dependency


RequireMember = Annotated[Membership, Depends(require_role(Role.OWNER, Role.PARTICIPANT))]
RequireOwner = Annotated[Membership, Depends(require_role(Role.OWNER))]