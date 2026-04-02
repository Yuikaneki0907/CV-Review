from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.requests import RegisterRequest, LoginRequest
from app.application.dto.responses import TokenResponse, UserResponse
from app.application.use_cases.auth import AuthUseCase
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.user_repository import UserRepository
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
