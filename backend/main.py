from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import get_settings
from database import engine
from middleware.security import setup_security
from routers.agreements import router as agreements_router, subcontractors_router
from routers.ai import router as ai_router
from routers.archive import router as archive_router
from routers.auth import router as auth_router
from routers.comments import router as comments_router
from routers.masters import router as masters_router
from routers.pdf import router as pdf_router
from routers.reports import router as reports_router
from routers.resolution import router as resolution_router
from routers.users import router as users_router
from routers.workflow import router as workflow_router

settings = get_settings()

app = FastAPI(title="SAMS API", version="1.0")
setup_security(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "1.0"}


@app.get("/health/db")
async def health_db_check() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(masters_router, prefix="/api")
app.include_router(agreements_router, prefix="/api")
app.include_router(subcontractors_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(archive_router, prefix="/api")
app.include_router(comments_router, prefix="/api")
app.include_router(pdf_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(resolution_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
