import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.db.session import get_db
from app.models.org import User
from app.schemas.common import TokenPair, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/github/callback", response_model=TokenPair)
async def github_callback(code: str, db: AsyncSession = Depends(get_db)) -> TokenPair:
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth credentials are not configured on the server."
        )

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
        )
        if token_response.status_code != 200:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Failed to exchange code with GitHub")

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid token response from GitHub: {token_data.get('error_description', 'No access token')}"
            )

        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"}
        )
        if user_response.status_code != 200:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Failed to fetch user info from GitHub")

        gh_user = user_response.json()
        github_id = str(gh_user.get("id"))
        email = gh_user.get("email")
        full_name = gh_user.get("name") or gh_user.get("login")
        avatar_url = gh_user.get("avatar_url")

        if not email:
            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {access_token}"}
            )
            if emails_response.status_code == 200:
                for item in emails_response.json():
                    if item.get("primary") and item.get("verified"):
                        email = item.get("email")
                        break

        if not email:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unable to retrieve a verified email from GitHub")

    result = await db.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.github_id = github_id
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
        else:
            user = User(
                email=email,
                github_id=github_id,
                full_name=full_name,
                avatar_url=avatar_url,
                is_active=True,
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)

    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/google/callback")
async def google_callback() -> dict:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Wire up once Google OAuth app is registered")

