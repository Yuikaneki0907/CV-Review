from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.requests import (
    RegisterRequest,
    LoginRequest,
    UserUpdateRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.application.dto.responses import (
    TokenResponse,
    UserResponse,
    ForgotPasswordResponse,
    MessageResponse,
)
from app.application.use_cases.auth import AuthUseCase
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.notifications.email_service import SMTPEmailService
from app.presentation.dependencies import get_current_user_id
from app.logger import get_logger

logger = get_logger("app.presentation.auth")

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse)
async def register(
    data: RegisterRequest, session: AsyncSession = Depends(get_db_session)
):
    logger.info("Register attempt: email=%s", data.email)
    user_repo = UserRepository(session)
    use_case = AuthUseCase(user_repo)
    try:
        user = await use_case.register(data.email, data.password, data.full_name)
        logger.info("Register SUCCESS: email=%s, user_id=%s", user.email, user.id)
        return UserResponse(id=user.id, email=user.email, full_name=user.full_name)
    except ValueError as e:
        logger.warning("Register FAILED: email=%s, reason=%s", data.email, str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest, session: AsyncSession = Depends(get_db_session)
):
    logger.info("Login attempt: email=%s", data.email)
    user_repo = UserRepository(session)
    use_case = AuthUseCase(user_repo)
    try:
        token = await use_case.login(data.email, data.password)
        logger.info("Login SUCCESS: email=%s", data.email)
        return TokenResponse(access_token=token)
    except ValueError as e:
        logger.warning("Login FAILED: email=%s, reason=%s", data.email, str(e))
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
):
    logger.info("Forgot password request: email=%s", data.email)
    user_repo = UserRepository(session)
    use_case = AuthUseCase(user_repo, SMTPEmailService())
    try:
        result = await use_case.request_password_reset(data.email)
        logger.info(
            "Forgot password accepted: email=%s, email_sent=%s",
            data.email,
            result.email_sent,
        )
        return ForgotPasswordResponse(**result.__dict__)
    except RuntimeError as e:
        logger.error("Forgot password unavailable: email=%s, reason=%s", data.email, str(e))
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
):
    logger.info("Reset password attempt")
    user_repo = UserRepository(session)
    use_case = AuthUseCase(user_repo)
    try:
        result = await use_case.reset_password(data.token, data.new_password)
        logger.info("Reset password SUCCESS")
        return MessageResponse(message=result.message)
    except ValueError as e:
        logger.warning("Reset password FAILED: reason=%s", str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session)
):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)

@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    data: UserUpdateRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session)
):
    user_repo = UserRepository(session)
    updated_user = await user_repo.update(
        user_id=user_id,
        full_name=data.full_name,
        phone_number=data.phone_number
    )
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    await session.commit()
    return UserResponse.model_validate(updated_user)
