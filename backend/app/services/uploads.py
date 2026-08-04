"""本地文件上传：合同证明等附件。"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

# backend/uploads/
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"

ALLOWED_CATEGORIES = {"contract_proof", "acceptance_proof"}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_BYTES = 20 * 1024 * 1024


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem).strip("_")
    return (cleaned or "file")[:80]


def save_upload(file: UploadFile, *, category: str) -> dict:
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="不支持的上传类型")
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 PDF / PNG / JPG")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="单文件不超过 20MB")

    subdir = {
        "contract_proof": "contracts",
        "acceptance_proof": "acceptance",
    }.get(category, category)
    dest_dir = UPLOAD_ROOT / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}_{_safe_stem(file.filename)}{ext}"
    dest_path = dest_dir / stored_name
    dest_path.write_bytes(data)

    relative = f"{subdir}/{stored_name}"
    return {
        "filename": file.filename,
        "path": relative,
        "url": f"/uploads/{relative}",
        "size": len(data),
    }
