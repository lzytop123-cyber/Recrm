"""业务选人/选部门用的精简目录 schema（不含人事档案敏感字段）。"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DirectoryDepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str] = None
    parent_id: Optional[int] = None
    children: List["DirectoryDepartmentOut"] = Field(default_factory=list)


class DirectoryPersonOut(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    is_active: bool = True


class DirectoryPersonListOut(BaseModel):
    total: int
    items: List[DirectoryPersonOut]


class DirectoryProjectOut(BaseModel):
    id: int
    name: str
    project_no: str
    status: str


class DirectoryProjectListOut(BaseModel):
    total: int
    items: List[DirectoryProjectOut]


class DirectoryProjectTaskOut(BaseModel):
    id: int
    project_id: int
    title: str
    status: str


class DirectoryProjectTaskListOut(BaseModel):
    total: int
    items: List[DirectoryProjectTaskOut]


class DirectoryCustomerOut(BaseModel):
    id: int
    name: str


class DirectoryCustomerListOut(BaseModel):
    total: int
    items: List[DirectoryCustomerOut]


class DirectoryContractOut(BaseModel):
    id: int
    contract_no: str
    title: str
    status: str
    customer_name: Optional[str] = None


class DirectoryContractListOut(BaseModel):
    total: int
    items: List[DirectoryContractOut]


DirectoryDepartmentOut.model_rebuild()
