from typing import Literal, Optional
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class AnalysisRequest(BaseModel):
    jd_text: str

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None


class GenerateCVRequest(BaseModel):
    job_title: str
    jd_text: str
    level: str = "Fresher"
    output_format: Literal["rich_text", "markdown", "docx"] = "markdown"


class ChatMessageRequest(BaseModel):
    role: str
    content: str


class ChatContextRequest(BaseModel):
    messages: list[ChatMessageRequest]
    output_format: Literal["rich_text", "markdown", "docx"] = "rich_text"


class GeneratedCVUpdateRequest(BaseModel):
    content: str
    output_format: Literal["rich_text", "markdown", "docx"]
