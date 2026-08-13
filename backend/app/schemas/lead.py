"""线索池请求/响应 Schema。"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    """快速录入：客户主体+电话+需求方向；联系人可空。"""

    name: Optional[str] = Field(None, max_length=100, description="联系人，空则用主体名")
    company_name: str = Field(..., min_length=1, max_length=200, description="客户主体")
    credit_code: Optional[str] = Field(None, max_length=50)
    company_domain: Optional[str] = Field(None, max_length=100)
    phone: str = Field(..., min_length=1, max_length=30)
    email: Optional[str] = None
    region: Optional[str] = None
    source: str = Field(default="manual", description="来源类型编码")
    source_detail: Optional[str] = None
    need_desc: Optional[str] = None
    budget: Optional[Decimal] = None
    expected_deal_at: Optional[datetime] = None
    business_type: str = Field(default="ai_product", description="需求方向/业务类型")
    remark: Optional[str] = None
    self_follow: Optional[bool] = Field(
        None,
        description="是否自己跟进；销售默认 True，非销售传 True 将被拒绝并进待分配池",
    )


class LeadUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    company_name: Optional[str] = None
    credit_code: Optional[str] = None
    company_domain: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    region: Optional[str] = None
    source: Optional[str] = None
    source_detail: Optional[str] = None
    need_desc: Optional[str] = None
    budget: Optional[Decimal] = None
    expected_deal_at: Optional[datetime] = None
    business_type: Optional[str] = None
    remark: Optional[str] = None


class LeadAssignRequest(BaseModel):
    owner_id: int = Field(..., description="接收人用户 ID")
    remark: Optional[str] = None


class LeadBatchAssignmentItem(BaseModel):
    lead_id: int
    owner_id: int


class LeadBatchAssignRequest(BaseModel):
    lead_ids: list[int] = Field(..., min_length=1)
    owner_ids: list[int] = Field(default_factory=list, description="average 模式必填")
    method: str = Field(default="average", description="average / manual")
    assignments: list[LeadBatchAssignmentItem] = Field(
        default_factory=list,
        description="manual 模式必填：逐条指定",
    )
    reason: Optional[str] = None


class LeadBatchAssignResultItem(BaseModel):
    lead_id: int
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    reason: Optional[str] = None


class LeadBatchAssignResult(BaseModel):
    success_count: int
    failed_count: int
    success: list[LeadBatchAssignResultItem] = []
    failed: list[LeadBatchAssignResultItem] = []


class LeadTransferRequest(BaseModel):
    owner_id: int = Field(..., description="转入人用户 ID")
    reason: Optional[str] = None


class LeadReturnRequest(BaseModel):
    reason_type: Optional[str] = Field(
        None,
        description="释放原因类型：no_need/unreachable/competitor/budget/other",
    )
    reason: Optional[str] = Field(None, max_length=500)


class LeadFollowUpCreate(BaseModel):
    follow_at: Optional[datetime] = None
    method: str = Field(default="phone", description="电话/微信/邮件/面谈/会议")
    content: str = Field(..., min_length=1)
    customer_feedback: Optional[str] = None
    result: str = Field(default="keep", description="advance/keep/return/lost")
    next_follow_at: Optional[datetime] = None


class LeadConvertRequest(BaseModel):
    customer_name: Optional[str] = Field(None, description="客户名称，默认用公司名或联系人")
    remark: Optional[str] = None
    opportunity_title: Optional[str] = Field(None, description="商机名称，默认用客户名")
    opportunity_stage: str = Field(default="need_confirm")
    expected_amount: Optional[Decimal] = None
    business_type: str = Field(default="other")
    requirement_summary: Optional[str] = None


class LeadLostRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class LeadFollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    user_id: int
    follow_at: datetime
    method: str
    content: str
    customer_feedback: Optional[str] = None
    result: str
    next_follow_at: Optional[datetime] = None
    created_at: datetime


class LeadLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    detail: Optional[str] = None
    created_at: datetime


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    company_name: Optional[str] = None
    credit_code: Optional[str] = None
    company_domain: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    region: Optional[str] = None
    source: str
    source_detail: Optional[str] = None
    need_desc: Optional[str] = None
    budget: Optional[Decimal] = None
    expected_deal_at: Optional[datetime] = None
    business_type: Optional[str] = None
    status: str
    owner_id: Optional[int] = None
    creator_id: Optional[int] = None
    department_id: Optional[int] = None
    protect_until: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    last_followed_at: Optional[datetime] = None
    converted_customer_id: Optional[int] = None
    converted_opportunity_id: Optional[int] = None
    converted_at: Optional[datetime] = None
    lost_reason: Optional[str] = None
    lost_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # 列表展示辅助
    owner_name: Optional[str] = None
    creator_name: Optional[str] = None
    is_protected: bool = False


class LeadConvertOut(BaseModel):
    lead: LeadOut
    customer_id: int
    opportunity_id: int


class LeadDetailOut(LeadOut):
    follow_ups: List[LeadFollowUpOut] = []
    logs: List[LeadLogOut] = []


class SalesJourneyMilestone(BaseModel):
    key: str
    label: str
    status: str  # done / current / pending / skipped
    at: Optional[datetime] = None
    actor: Optional[str] = None
    entity: Optional[str] = None  # lead / customer / opportunity / contract / project
    entity_id: Optional[int] = None


class SalesJourneyLinks(BaseModel):
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    contract_id: Optional[int] = None
    project_id: Optional[int] = None
    lead_label: Optional[str] = None
    customer_name: Optional[str] = None
    opportunity_no: Optional[str] = None
    contract_no: Optional[str] = None
    project_no: Optional[str] = None
    project_name: Optional[str] = None


class SalesJourneyOut(BaseModel):
    milestones: List[SalesJourneyMilestone] = []
    links: SalesJourneyLinks = SalesJourneyLinks()
    current_key: Optional[str] = None


class LeadListOut(BaseModel):
    total: int
    items: List[LeadOut]


class LeadStatsOut(BaseModel):
    total: int
    pending_assign: int
    assigned: int
    following: int
    converted: int
    returned: int
    lost: int
    public_pool: int
    today_created: int = 0
    today_assigned: int = 0
    following_mine: int = 0
    protect_expiring: int = 0
    converted_month: int = 0
    mine: int = 0
    created: int = 0
    created_pending_assign: int = 0
    created_assigned: int = 0
    created_following: int = 0
    created_converted: int = 0


class LeadQuotaOut(BaseModel):
    daily_claimed: int
    daily_limit: int
    protected_count: int
    protect_limit: int
    protect_days: int
    cooldown_hours: int
    can_claim: bool
    block_reason: Optional[str] = None


class DuplicateCheckOut(BaseModel):
    has_duplicate: bool
    is_hard_duplicate: bool = False
    by_phone: List[LeadOut] = []
    by_company: List[LeadOut] = []
    by_credit: List[LeadOut] = []
    by_domain: List[LeadOut] = []


class LeadImportRowIn(BaseModel):
    """批量导入确认时的一行（来自预览结果）。"""

    row_no: int
    company_name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=1, max_length=30)
    name: Optional[str] = Field(None, max_length=100)
    credit_code: Optional[str] = Field(None, max_length=50)
    company_domain: Optional[str] = Field(None, max_length=100)
    business_type: str = Field(default="ai_product")
    need_desc: Optional[str] = None
    remark: Optional[str] = None
    force: bool = Field(False, description="硬重复时是否强制录入")


class LeadImportPreviewRow(BaseModel):
    row_no: int
    company_name: str = ""
    phone: str = ""
    name: Optional[str] = None
    credit_code: Optional[str] = None
    company_domain: Optional[str] = None
    business_type: str = "ai_product"
    business_type_label: str = ""
    need_desc: Optional[str] = None
    remark: Optional[str] = None
    status: str = Field(description="ok / soft / hard / error")
    message: str = ""
    can_import: bool = True
    force_required: bool = False


class LeadImportPreviewOut(BaseModel):
    total: int
    ok_count: int
    soft_count: int
    hard_count: int
    error_count: int
    rows: List[LeadImportPreviewRow]


class LeadImportConfirmRequest(BaseModel):
    rows: List[LeadImportRowIn] = Field(..., min_length=1, max_length=200)
    self_follow: Optional[bool] = Field(
        None,
        description="是否自跟进；非销售强制进待分配池",
    )


class LeadImportConfirmItem(BaseModel):
    row_no: int
    ok: bool
    lead_id: Optional[int] = None
    message: str = ""


class LeadImportConfirmOut(BaseModel):
    success_count: int
    failed_count: int
    skipped_count: int = 0
    items: List[LeadImportConfirmItem]
