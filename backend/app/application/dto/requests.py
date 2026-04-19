from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=9)
    full_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=9)


class AnalysisRequest(BaseModel):
    jd_text: str

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None


class GenerateCVRequest(BaseModel):
    job_title: str
    jd_text: str
    level: str = "Fresher"
    output_format: Literal["markdown", "docx"] = "markdown"


class ChatMessageRequest(BaseModel):
    role: str
    content: str


class ChatContextRequest(BaseModel):
    messages: list[ChatMessageRequest]
    output_format: Literal["markdown", "docx"] = "markdown"
    template_id: Optional[str] = None
    current_cv_id: Optional[UUID] = None


class GeneratedCVUpdateRequest(BaseModel):
    content: str
    output_format: Literal["markdown", "docx"]
