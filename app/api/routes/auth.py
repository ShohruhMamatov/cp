from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.token import Token
from app.schemas.user import PasswordChange, UserCreate, UserLogin, UserOut

router = APIRouter(tags=["auth"])


@router.post("/auth", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: SessionDep):
    condition = User.login == data.login
    if data.email:
        condition = or_(condition, User.email == data.email)

    if (await session.scalars(select(User).where(condition))).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Login or email already taken")

    user = User(
        login=data.login,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(data: UserLogin, session: SessionDep):
    user = (await session.scalars(select(User).where(User.login == data.login))).first()
    if user is None or not verify_password(data.password, user.hashed_password):
        # One message for both failure modes — never reveal which half was wrong.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect login or password")

    return Token(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(data: PasswordChange, user: CurrentUser, session: SessionDep):
    if not verify_password(data.old_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Old password is incorrect")

    user.hashed_password = hash_password(data.new_password)
    session.add(user)
    await session.commit()


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user
