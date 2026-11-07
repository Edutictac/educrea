from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)


class UserOut(BaseModel):
    is_guest: bool
    is_admin: bool
    included_ai_authorized: bool
    id: UUID
    email: str
    model_config = ConfigDict(from_attributes=True)


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)


class ProjectOut(BaseModel):
    id: UUID
    slug: str
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FileCreate(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = ""


class FileUpdate(BaseModel):
    content: str
    expected_version: int = Field(ge=1)


class FileOut(BaseModel):
    id: UUID
    project_id: UUID
    path: str
    content: str
    version: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FileSummary(BaseModel):
    id: UUID
    path: str
    version: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

