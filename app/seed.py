"""Seed completo do banco de dados com todos os níveis e módulos."""
import asyncio
from app.models import (
    User, Module, Lesson, Exercise, Level, Difficulty, UserRole
)
from app.core.database import AsyncSessionLocal, init_db
from app.core.security import hash_password
from app.curriculum_basico import BASICO_M1_3
from app.curriculum_outros import BASICO_M4_6, INTERMEDIARIO_MODULES, AVANCADO_MODULES
from sqlalchemy import select


async def seed_database():
    await init_db()

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        existing = await db.execute(select(Module).limit(1))
        if existing.scalar_one_or_none():
            print("Database already seeded.")
            return

        print("Seeding database...")

        # ── Seed Curriculum ────────────────────────────────────────────
        curriculum = [
            (Level.basico, BASICO_M1_3 + BASICO_M4_6),
            (Level.intermediario, INTERMEDIARIO_MODULES),
            (Level.avancado, AVANCADO_MODULES),
        ]

        for level, modules_data in curriculum:
            for mod_data in modules_data:
                lessons_data  = mod_data.pop("lessons", [])
                exercises_data = mod_data.pop("exercises", [])

                module = Module(level=level, **mod_data)
                db.add(module)
                await db.flush()

                for l in lessons_data:
                    db.add(Lesson(module_id=module.id, **l))

                for e in exercises_data:
                    diff_str = e.pop("difficulty", "facil")
                    diff_map = {"facil": Difficulty.facil, "medio": Difficulty.medio, "dificil": Difficulty.dificil}
                    db.add(Exercise(
                        module_id=module.id,
                        difficulty=diff_map.get(diff_str, Difficulty.facil),
                        **e
                    ))

        # ── Seed Users ─────────────────────────────────────────────────
        admin = User(
            name="Admin",
            email="admin@pythonbackend.dev",
            password_hash=hash_password("Admin2024!"),
            role=UserRole.admin,
            current_level=Level.avancado,
        )
        db.add(admin)

        demo = User(
            name="Dev Demo",
            email="demo@python.dev",
            password_hash=hash_password("Python2024!"),
            role=UserRole.student,
            current_level=Level.basico,
        )
        db.add(demo)

        await db.commit()
        print("✅ Seed completo!")
        print("   Admin:  admin@pythonbackend.dev / Admin2024!")
        print("   Demo:   demo@python.dev / Python2024!")


if __name__ == "__main__":
    asyncio.run(seed_database())
