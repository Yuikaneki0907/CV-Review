from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.requests import RegisterRequest, LoginRequest, UserUpdateRequest
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

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session)
):
    from uuid import UUID
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # We will need to query the UserModel if phone_number is not in the entity
    # Actually, we can fetch from UserModel to get phone_number, or update domain User
    # But since UserResponse has phone_number now, let's fetch model or add it to domain.
    # To keep it simple, we will fetch the raw model using session.
    from sqlalchemy import select
    from app.infrastructure.database.models import UserModel
    result = await session.execute(select(UserModel).where(UserModel.id == UUID(user_id)))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        full_name=db_user.full_name,
        phone_number=db_user.phone_number
    )

@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    data: UserUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session)
):
    from uuid import UUID
    user_repo = UserRepository(session)
    updated_user = await user_repo.update(
        user_id=UUID(user_id),
        full_name=data.full_name,
        phone_number=data.phone_number
    )
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    from sqlalchemy import select
    from app.infrastructure.database.models import UserModel
    result = await session.execute(select(UserModel).where(UserModel.id == UUID(user_id)))
    db_user = result.scalar_one_or_none()
    
    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        full_name=db_user.full_name,
        phone_number=db_user.phone_number
    )
