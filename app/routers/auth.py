from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone, timedelta
from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, check_rate_limit,
    record_failed, clear_attempts,
)
from app.core.config import settings
from app.core.deps import get_current_user
from app.models import User, UserSession, UserRole, Level
from app.schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
    RefreshRequest, UserResponse, MessageResponse,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    count_result = await db.execute(select(User))
    is_first = count_result.first() is None

    user = User(
        name=body.name.strip(),
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role=UserRole.admin if is_first else UserRole.student,
        current_level=Level.basico,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{body.email.lower()}"

    allowed, wait = check_rate_limit(identifier)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Muitas tentativas. Aguarde {wait}s",
            headers={"Retry-After": str(wait)},
        )

    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        record_failed(identifier)
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada")

    clear_attempts(identifier)

    access_token  = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=expires_at,
        user_agent=request.headers.get("User-Agent", "")[:300],
        ip_address=ip,
    )
    db.add(session)
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    result = await db.execute(
        select(UserSession).where(
            UserSession.refresh_token == body.refresh_token,
            UserSession.is_revoked == False,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="Sessão inválida")

    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expirado")

    session.is_revoked = True
    new_access  = create_access_token({"sub": payload["sub"]})
    new_refresh = create_refresh_token({"sub": payload["sub"]})
    new_session = UserSession(
        user_id=session.user_id,
        refresh_token=new_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_session)
    await db.flush()

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(UserSession)
        .where(UserSession.refresh_token == body.refresh_token)
        .values(is_revoked=True)
    )
    return {"message": "Logout realizado"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
