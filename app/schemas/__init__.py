from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.models import UserRole, Level, Difficulty, SubmissionStatus


class RegisterRequest(BaseModel):
    name:     str      = Field(..., min_length=2, max_length=100)
    email:    EmailStr
    password: str      = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Senha deve ter ao menos uma letra maiúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve ter ao menos um número")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id:            int
    name:          str
    email:         str
    role:          UserRole
    is_active:     bool
    current_level: Level
    xp_points:     int
    last_login:    Optional[datetime]
    created_at:    datetime
    model_config = {"from_attributes": True}


class LessonResponse(BaseModel):
    id:               int
    order:            int
    title:            str
    content:          str
    code_example:     Optional[str]
    real_world_case:  Optional[str]
    best_practice:    Optional[str]
    reading_minutes:  int
    model_config = {"from_attributes": True}


class ExerciseResponse(BaseModel):
    id:           int
    order:        int
    title:        str
    description:  str
    hint:         str
    difficulty:   Difficulty
    starter_code: Optional[str]
    xp_reward:    int
    is_complete:  bool = False
    best_score:   Optional[float] = None
    model_config = {"from_attributes": True}


class ModuleResponse(BaseModel):
    id:                  int
    level:               Level
    order:               int
    title:               str
    description:         str
    icon:                str
    color:               str
    xp_reward:           int
    total_exercises:     int = 0
    completed_exercises: int = 0
    total_lessons:       int = 0
    model_config = {"from_attributes": True}


class SubmitCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50_000)


class SubmissionResponse(BaseModel):
    id:          int
    exercise_id: int
    code:        str
    ai_feedback: Optional[str]
    ai_score:    Optional[float]
    status:      SubmissionStatus
    created_at:  datetime
    model_config = {"from_attributes": True}


class ProgressSummary(BaseModel):
    total_exercises:     int
    completed_exercises: int
    total_submissions:   int
    completion_pct:      float
    xp_points:           int
    current_level:       Level


class MessageResponse(BaseModel):
    message: str


class AdminStatsResponse(BaseModel):
    total_users:       int
    active_users:      int
    total_submissions: int
    total_completions: int
    modules_count:     int
    exercises_count:   int
