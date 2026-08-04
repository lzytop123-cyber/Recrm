"""通用文件上传 API。"""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import PermissionChecker
from app.models.user import User
from app.services import uploads as upload_service

router = APIRouter(prefix="/uploads", tags=["文件上传"])


@router.post("", summary="上传附件")
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[
        User, Depends(PermissionChecker(["contract:view", "project:view"], any_of=True))
    ],
    category: Annotated[str, Form()] = "contract_proof",
) -> dict:
    _ = current_user
    return upload_service.save_upload(file, category=category)
