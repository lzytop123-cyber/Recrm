"""认证相关 Schema。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    real_name: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleBrief(BaseModel):
    id: int
    name: str
    code: str
    data_scope: str

    model_config = {"from_attributes": True}


class MenuItem(BaseModel):
    """前端左侧菜单项（由权限码推导）。"""

    path: str
    title: str
    icon: Optional[str] = None
    permission: Optional[str] = None


class UserInfoResponse(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    is_active: bool
    roles: List[RoleBrief] = []
    permissions: List[str] = []
    data_scope: str = "personal"
    menus: List[MenuItem] = []
    lead_entry_only: bool = False
    home_path: str = "/dashboard"

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfoResponse


class FeishuLoginConfig(BaseModel):
    enabled: bool
    redirect_uri: str | None = None


class FeishuAuthorizeResponse(BaseModel):
    authorize_url: str
    state: str


class FeishuCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=512)
    state: str | None = Field(None, max_length=2048)


class FeishuLoginResponse(LoginResponse):
    redirect: str = "/dashboard"