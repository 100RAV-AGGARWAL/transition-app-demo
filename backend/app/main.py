from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import AsyncSessionLocal, Base, engine
from .routers import admin, chat, cmc, debug, properties, scheduling
from .seed import seed_if_empty
from .settings import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

print(f"----------------------------------\nStarting {settings.app_name} in {settings.environment} environment and frontend origin {settings.frontend_origin}\n----------------------------------")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin, "http://localhost:3000",
        "http://localhost:5173", "https://project-libyg.vercel.app/"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(debug.router, prefix=settings.api_prefix)
app.include_router(properties.router, prefix=settings.api_prefix)
app.include_router(cmc.router, prefix=settings.api_prefix)
app.include_router(scheduling.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)


async def _ensure_postgres_enum_values(conn) -> None:
    await conn.execute(
        text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'callstatus') AND NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = 'callstatus' AND e.enumlabel = 'pending'
            ) THEN
                ALTER TYPE callstatus ADD VALUE 'pending';
            END IF;
        END
        $$;
    """))


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await _ensure_postgres_enum_values(conn)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_if_empty(session)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment
    }
