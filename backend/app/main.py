from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .api.router import api_router
from .config import load_settings
from .database import Base, create_sqlite_engine
from .services.backups import create_daily_backup


def create_app(
    database_path: Path | None = None,
    backup_dir: Path | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    settings = load_settings()
    db_path = (database_path or settings.database_path).resolve()
    backups = (backup_dir or settings.backup_dir).resolve()
    frontend_dist = (static_dir or settings.static_dir).resolve()
    engine = create_sqlite_engine(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        create_daily_backup(db_path, backups)
        yield
        engine.dispose()

    app = FastAPI(
        title="FamilyLedger 家庭快捷月度统计台",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.database_path = db_path
    app.state.backup_dir = backups
    app.state.static_dir = frontend_dist
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/api/health", tags=["system"])
    def health(request: Request):
        with Session(request.app.state.engine) as session:
            session.execute(text("SELECT 1"))
            integrity = session.execute(text("PRAGMA integrity_check")).scalar_one()
        return {
            "status": "ok" if integrity == "ok" else "degraded",
            "service": "family-ledger",
            "version": app.version,
            "database_integrity": integrity,
            "database_path": str(request.app.state.database_path),
        }

    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    brand_dir = frontend_dist / "brand"
    if brand_dir.exists():
        app.mount("/brand", StaticFiles(directory=brand_dir), name="brand")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API 路径不存在")
        index = frontend_dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse(
            {
                "service": "family-ledger",
                "message": "前端尚未构建，请在 frontend 目录运行 npm run build",
            }
        )

    return app


app = create_app()
