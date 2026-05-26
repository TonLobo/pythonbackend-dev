from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_admin
from app.models import Module, Lesson, Exercise, UserProgress, Submission, User, Level, SubmissionStatus
from app.schemas import (
    ModuleResponse, LessonResponse, ExerciseResponse,
    SubmitCodeRequest, SubmissionResponse, MessageResponse,
    ProgressSummary, AdminStatsResponse,
)
import httpx, json

modules_router = APIRouter(prefix="/modules", tags=["Módulos"])
exercises_router = APIRouter(prefix="/exercises", tags=["Exercícios"])
progress_router  = APIRouter(prefix="/users",    tags=["Progresso"])
admin_router     = APIRouter(prefix="/admin",    tags=["Admin"])


# ── Modules ──────────────────────────────────────────────────────────────────

@modules_router.get("", response_model=List[ModuleResponse])
async def list_modules(
    level: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Module).order_by(Module.level, Module.order)
    if level:
        try:
            q = q.where(Module.level == Level(level))
        except ValueError:
            raise HTTPException(400, f"Nível inválido: {level}")

    result = await db.execute(q.options(selectinload(Module.exercises), selectinload(Module.lessons)))
    modules = result.scalars().all()

    # Fetch completed exercise IDs for this user
    prog_result = await db.execute(
        select(UserProgress.exercise_id).where(
            UserProgress.user_id == current_user.id,
            UserProgress.is_complete == True,
        )
    )
    completed_ids = set(prog_result.scalars().all())

    return [
        ModuleResponse(
            id=m.id, level=m.level, order=m.order, title=m.title,
            description=m.description, icon=m.icon, color=m.color,
            xp_reward=m.xp_reward,
            total_exercises=len(m.exercises),
            completed_exercises=sum(1 for e in m.exercises if e.id in completed_ids),
            total_lessons=len(m.lessons),
        )
        for m in modules
    ]


@modules_router.get("/{module_id}/lessons", response_model=List[LessonResponse])
async def list_lessons(module_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    res = await db.execute(select(Lesson).where(Lesson.module_id == module_id).order_by(Lesson.order))
    return res.scalars().all()


@modules_router.get("/{module_id}/exercises", response_model=List[ExerciseResponse])
async def list_exercises(
    module_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ex_res = await db.execute(
        select(Exercise).where(Exercise.module_id == module_id).order_by(Exercise.order)
    )
    exercises = ex_res.scalars().all()

    prog_res = await db.execute(
        select(UserProgress).where(
            UserProgress.user_id == current_user.id,
            UserProgress.exercise_id.in_([e.id for e in exercises]),
        )
    )
    prog_map = {p.exercise_id: p for p in prog_res.scalars().all()}

    return [
        ExerciseResponse(
            id=e.id, order=e.order, title=e.title, description=e.description,
            hint=e.hint, difficulty=e.difficulty, starter_code=e.starter_code,
            xp_reward=e.xp_reward,
            is_complete=prog_map.get(e.id, None) and prog_map[e.id].is_complete or False,
            best_score=prog_map.get(e.id, None) and prog_map[e.id].best_score or None,
        )
        for e in exercises
    ]


# ── Exercises ─────────────────────────────────────────────────────────────────

async def evaluate_with_ai(title: str, description: str, code: str) -> tuple[str, float]:
    prompt = f"""Você é professor sênior de Python backend avaliando um exercício.

EXERCÍCIO: {title}
DESCRIÇÃO: {description}

CÓDIGO DO ALUNO:
```python
{code}
```

Responda APENAS com JSON válido:
{{"score": <0-100>, "feedback": "<feedback em português, 3-4 parágrafos>", "passed": <true se score>=70>}}

Critérios: 90-100=excelente/idiomático, 70-89=correto com melhorias, 50-69=parcial, 0-49=incorreto.
Sem markdown, apenas o JSON."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            res.raise_for_status()
            data = res.json()
            text = "".join(b.get("text", "") for b in data.get("content", []))
            clean = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed = json.loads(clean)
            return parsed.get("feedback", "Sem feedback."), float(parsed.get("score", 50))
    except Exception as e:
        return f"Avaliação não disponível: {str(e)}", 0.0


@exercises_router.post("/{exercise_id}/submit", response_model=SubmissionResponse)
async def submit_code(
    exercise_id: int,
    body: SubmitCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ex_res = await db.execute(select(Exercise).where(Exercise.id == exercise_id))
    exercise = ex_res.scalar_one_or_none()
    if not exercise:
        raise HTTPException(404, "Exercício não encontrado")

    feedback, score = await evaluate_with_ai(exercise.title, exercise.description, body.code)
    passed = score >= 70

    sub = Submission(
        user_id=current_user.id,
        exercise_id=exercise_id,
        code=body.code,
        ai_feedback=feedback,
        ai_score=score,
        status=SubmissionStatus.passed if passed else SubmissionStatus.reviewed,
    )
    db.add(sub)
    await db.flush()

    # Update progress
    prog_res = await db.execute(
        select(UserProgress).where(
            UserProgress.user_id == current_user.id,
            UserProgress.exercise_id == exercise_id,
        )
    )
    prog = prog_res.scalar_one_or_none()

    if prog:
        if passed:
            prog.is_complete = True
        if prog.best_score is None or score > prog.best_score:
            prog.best_score = score
    else:
        prog = UserProgress(
            user_id=current_user.id,
            exercise_id=exercise_id,
            is_complete=passed,
            best_score=score,
        )
        db.add(prog)

    # Award XP
    if passed:
        current_user.xp_points += exercise.xp_reward

    await db.refresh(sub)
    return sub


@exercises_router.post("/{exercise_id}/complete", response_model=MessageResponse)
async def mark_complete(
    exercise_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ex_res = await db.execute(select(Exercise).where(Exercise.id == exercise_id))
    exercise = ex_res.scalar_one_or_none()
    if not exercise:
        raise HTTPException(404, "Exercício não encontrado")

    prog_res = await db.execute(
        select(UserProgress).where(
            UserProgress.user_id == current_user.id,
            UserProgress.exercise_id == exercise_id,
        )
    )
    prog = prog_res.scalar_one_or_none()

    if prog:
        if not prog.is_complete:
            prog.is_complete = True
            current_user.xp_points += exercise.xp_reward
    else:
        prog = UserProgress(user_id=current_user.id, exercise_id=exercise_id, is_complete=True)
        db.add(prog)
        current_user.xp_points += exercise.xp_reward

    return {"message": "Exercício marcado como concluído"}


@exercises_router.get("/{exercise_id}/submissions", response_model=List[SubmissionResponse])
async def my_submissions(
    exercise_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Submission)
        .where(Submission.user_id == current_user.id, Submission.exercise_id == exercise_id)
        .order_by(Submission.created_at.desc())
        .limit(10)
    )
    return res.scalars().all()


# ── Progress ──────────────────────────────────────────────────────────────────

@progress_router.get("/me/progress", response_model=ProgressSummary)
async def my_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_ex = (await db.execute(select(func.count(Exercise.id)))).scalar() or 0
    completed = (await db.execute(
        select(func.count(UserProgress.id)).where(
            UserProgress.user_id == current_user.id, UserProgress.is_complete == True
        )
    )).scalar() or 0
    total_subs = (await db.execute(
        select(func.count(Submission.id)).where(Submission.user_id == current_user.id)
    )).scalar() or 0

    return ProgressSummary(
        total_exercises=total_ex,
        completed_exercises=completed,
        total_submissions=total_subs,
        completion_pct=round(completed / total_ex * 100, 1) if total_ex else 0,
        xp_points=current_user.xp_points,
        current_level=current_user.current_level,
    )


# ── Admin ─────────────────────────────────────────────────────────────────────

@admin_router.get("/stats", response_model=AdminStatsResponse)
async def platform_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return AdminStatsResponse(
        total_users=(await db.execute(select(func.count(User.id)))).scalar() or 0,
        active_users=(await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar() or 0,
        total_submissions=(await db.execute(select(func.count(Submission.id)))).scalar() or 0,
        total_completions=(await db.execute(select(func.count(UserProgress.id)).where(UserProgress.is_complete == True))).scalar() or 0,
        modules_count=(await db.execute(select(func.count(Module.id)))).scalar() or 0,
        exercises_count=(await db.execute(select(func.count(Exercise.id)))).scalar() or 0,
    )


@admin_router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    res = await db.execute(select(User).order_by(User.created_at.desc()))
    users = res.scalars().all()
    subs = {r[0]: r[1] for r in (await db.execute(
        select(Submission.user_id, func.count(Submission.id)).group_by(Submission.user_id)
    )).all()}
    done = {r[0]: r[1] for r in (await db.execute(
        select(UserProgress.user_id, func.count(UserProgress.id))
        .where(UserProgress.is_complete == True)
        .group_by(UserProgress.user_id)
    )).all()}

    return [
        {
            "id": u.id, "name": u.name, "email": u.email,
            "role": u.role, "is_active": u.is_active,
            "current_level": u.current_level, "xp_points": u.xp_points,
            "total_submissions": subs.get(u.id, 0),
            "completed_exercises": done.get(u.id, 0),
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@admin_router.patch("/users/{user_id}/toggle-active")
async def toggle_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if user_id == admin.id:
        raise HTTPException(400, "Não é possível desativar a própria conta")
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    user.is_active = not user.is_active
    return {"message": f"Usuário {'ativado' if user.is_active else 'desativado'}"}
