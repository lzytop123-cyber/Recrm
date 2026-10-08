"""知识附件抽文本：PDF 用 pypdf；图片用 RapidOCR（未安装则跳过）。"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_MAX_CHARS = 50_000


def extract_attachment_text(path: Path) -> str:
    if not path.is_file():
        return ""
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            return _pdf_text(path)[:_MAX_CHARS]
        if suffix in _IMAGE_EXT:
            return _image_text(path)[:_MAX_CHARS]
    except Exception as exc:  # noqa: BLE001
        logger.warning("attachment extract failed %s: %s", path.name, exc)
    return ""


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _image_text(path: Path) -> str:
    # ponytail: RapidOCR 可选；未装则图片不进检索，装上即可
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        logger.warning("rapidocr_onnxruntime not installed; skip image OCR for %s", path.name)
        return ""

    engine = RapidOCR()
    result, _ = engine(str(path))
    if not result:
        return ""
    # result rows: [box, text, score]
    return "\n".join(str(row[1]).strip() for row in result if len(row) > 1 and row[1]).strip()
