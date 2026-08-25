"""
FastAPI 入口：挂载路由、CORS、启动时可选种子数据提示。
启动：在 backend 目录执行
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
文档：http://127.0.0.1:8000/docs
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.config import get_settings
from app.database import Base, engine
import app.models  # noqa: F401  # 触发所有模型注册到 Base.metadata

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="公司内部 CRM + OKR 经营管理系统 API（骨架）",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _ensure_schema() -> None:
    """checkfirst 只补建缺失表，不影响现有数据，绕过 Alembic 在 SQLite 上的问题。"""
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as exc:  # noqa: BLE001
        # 不让建表失败阻止应用起来
        print(f"[startup] create_all skipped: {exc}")


app.include_router(api_router)

_upload_dir = Path(__file__).resolve().parent.parent / "uploads"
_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_upload_dir)), name="uploads")


@app.get("/", tags=["健康检查"])
def root():
    return {"message": f"{settings.app_name} API is running", "docs": "/docs"}


@app.get("/health", tags=["健康检查"])
def health():
    return {"status": "ok"}
