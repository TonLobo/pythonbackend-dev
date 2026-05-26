from sqlalchemy import String, Integer, Boolean, Text, Float, ForeignKey, DateTime, Enum, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from datetime import datetime
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    student = "student"
    admin   = "admin"


class Level(str, enum.Enum):
    basico       = "basico"
    intermediario = "intermediario"
    avancado     = "avancado"


class Difficulty(str, enum.Enum):
    facil  = "facil"
    medio  = "medio"
    dificil = "dificil"


class SubmissionStatus(str, enum.Enum):
    pending  = "pending"
    reviewed = "reviewed"
    passed   = "passed"


class User(Base):
    __tablename__ = "users"
    id:            Mapped[int]       = mapped_column(Integer, primary_key=True)
    name:          Mapped[str]       = mapped_column(String(100), nullable=False)
    email:         Mapped[str]       = mapped_column(String(200), unique=True, nullable=False, index=True)
    password_hash: Mapped[str]       = mapped_column(String(200), nullable=False)
    role:          Mapped[UserRole]  = mapped_column(Enum(UserRole), default=UserRole.student)
    is_active:     Mapped[bool]      = mapped_column(Boolean, default=True)
    current_level: Mapped[Level]     = mapped_column(Enum(Level), default=Level.basico)
    last_login:    Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    xp_points:     Mapped[int]       = mapped_column(Integer, default=0)

    submissions: Mapped[List["Submission"]]   = relationship(back_populates="user", cascade="all, delete-orphan")
    progress:    Mapped[List["UserProgress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions:    Mapped[List["UserSession"]]  = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"
    id:            Mapped[int]  = mapped_column(Integer, primary_key=True)
    user_id:       Mapped[int]  = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token: Mapped[str]  = mapped_column(String(500), unique=True, nullable=False)
    is_revoked:    Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent:    Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    ip_address:    Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user: Mapped["User"] = relationship(back_populates="sessions")


class Module(Base):
    """A module belongs to a level and contains lessons + exercises."""
    __tablename__ = "modules"
    id:          Mapped[int]   = mapped_column(Integer, primary_key=True)
    level:       Mapped[Level] = mapped_column(Enum(Level), nullable=False, index=True)
    order:       Mapped[int]   = mapped_column(Integer, nullable=False)
    title:       Mapped[str]   = mapped_column(String(200), nullable=False)
    description: Mapped[str]   = mapped_column(Text, nullable=False)
    icon:        Mapped[str]   = mapped_column(String(10), default="📦")
    color:       Mapped[str]   = mapped_column(String(20), default="#3b82f6")
    xp_reward:   Mapped[int]   = mapped_column(Integer, default=100)

    lessons:   Mapped[List["Lesson"]]   = relationship(back_populates="module", order_by="Lesson.order", cascade="all, delete-orphan")
    exercises: Mapped[List["Exercise"]] = relationship(back_populates="module", order_by="Exercise.order", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("level", "order", name="uq_module_level_order"),)


class Lesson(Base):
    """Theory content: explanation + code examples."""
    __tablename__ = "lessons"
    id:          Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id:   Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    order:       Mapped[int] = mapped_column(Integer, nullable=False)
    title:       Mapped[str] = mapped_column(String(200), nullable=False)
    content:     Mapped[str] = mapped_column(Text, nullable=False)   # Markdown
    code_example: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    real_world_case: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    best_practice:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reading_minutes: Mapped[int] = mapped_column(Integer, default=5)

    module: Mapped["Module"] = relationship(back_populates="lessons")


class Exercise(Base):
    __tablename__ = "exercises"
    id:           Mapped[int]        = mapped_column(Integer, primary_key=True)
    module_id:    Mapped[int]        = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    order:        Mapped[int]        = mapped_column(Integer, nullable=False)
    title:        Mapped[str]        = mapped_column(String(200), nullable=False)
    description:  Mapped[str]        = mapped_column(Text, nullable=False)
    hint:         Mapped[str]        = mapped_column(Text, nullable=False)
    difficulty:   Mapped[Difficulty] = mapped_column(Enum(Difficulty), nullable=False)
    starter_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    solution_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    xp_reward:    Mapped[int]        = mapped_column(Integer, default=20)

    module:      Mapped["Module"]           = relationship(back_populates="exercises")
    submissions: Mapped[List["Submission"]] = relationship(back_populates="exercise", cascade="all, delete-orphan")
    progress:    Mapped[List["UserProgress"]] = relationship(back_populates="exercise", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("module_id", "order", name="uq_exercise_module_order"),)


class Submission(Base):
    __tablename__ = "submissions"
    id:          Mapped[int]              = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int]              = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_id: Mapped[int]              = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    code:        Mapped[str]              = mapped_column(Text, nullable=False)
    ai_feedback: Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    ai_score:    Mapped[Optional[float]]  = mapped_column(Float, nullable=True)
    status:      Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus), default=SubmissionStatus.pending)

    user:     Mapped["User"]     = relationship(back_populates="submissions")
    exercise: Mapped["Exercise"] = relationship(back_populates="submissions")

    __table_args__ = (Index("ix_sub_user_ex", "user_id", "exercise_id"),)


class UserProgress(Base):
    __tablename__ = "user_progress"
    id:          Mapped[int]  = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int]  = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[int]  = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    is_complete:  Mapped[bool] = mapped_column(Boolean, default=False)
    best_score:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    user:     Mapped["User"]     = relationship(back_populates="progress")
    exercise: Mapped["Exercise"] = relationship(back_populates="progress")

    __table_args__ = (UniqueConstraint("user_id", "exercise_id", name="uq_prog_user_ex"),)
