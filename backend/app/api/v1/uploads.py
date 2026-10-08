"""通用文件上传 API。"""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import PermissionChecker
from app.models.user import User
from app.services import uploads as upload_service

router = APIRouter(prefix="/uploads", tags=["文件上传"])


@router.post("", summary="上传附件")
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["contract:view", "project:view", "org:manage", "knowledge:manage"], any_of=True))
    ],
    category: Annotated[str, Form()] = "contract_proof",
) -> dict:
    _ = current_user
    return upload_service.save_upload(file, category=category)


@router.get("/{file_path:path}", summary="读取已上传文件")
def get_uploaded_file(file_path: str) -> FileResponse:
    """兼容前端把 baseURL(/api/v1) 拼到 /uploads/... 上的访问。"""
    path = upload_service.resolve_stored_file(file_path)
    return FileResponse(path)
