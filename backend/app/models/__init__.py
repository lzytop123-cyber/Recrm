"""
ORM 模型汇总导出，供 Alembic 与业务层统一导入。
后续商机/项目/任务/OKR/工单/排期等模块在此追加。
"""
from app.models.associations import role_permissions, user_roles
from app.models.approval_rule import ApprovalRule
from app.models.audit_log import AuditLog
from app.models.contract import Contract
from app.models.customer import Customer, CustomerFollowUp
from app.models.department import Department
from app.models.finance import Receipt, ReceiptAllocation, ReceivablePlan, Refund
from app.models.lead import Lead, LeadFollowUp, LeadLog
from app.models.opportunity import Opportunity, OpportunityActivity
from app.models.payment import Payment
from app.models.permission import Permission
from app.models.project import Project, ProjectMilestone, ProjectResourceNeed, ProjectTask
from app.models.okr import KeyResult, Okr
from app.models.performance import PerformanceAppeal, PerformanceAssessment, PerformanceCycle
from app.models.asset import (
    AssetBorrowItem,
    AssetBorrowRequest,
    AssetDepreciationRule,
    AssetDepreciationSnapshot,
    AssetDisposal,
    AssetInventoryLine,
    AssetInventorySession,
    AssetMaintenance,
    FixedAsset,
    ShootingSchedule,
    ShootingScheduleAsset,
    ShootingScheduleMember,
)
from app.models.knowledge import KnowledgeArticle, KnowledgeSource, KnowledgeSpace
from app.models.platform import (
    Delegation,
    ExportJob,
    Notification,
    SystemConfig,
    SystemDictionary,
)
from app.models.role import Role
from app.models.schedule import Schedule
from app.models.ticket import Ticket, TicketRecord
from app.models.timesheet import Timesheet
from app.models.user import User
from app.models.employee_hr import EmployeeHistoryEvent, FeishuAttendanceDaily, SystemSyncState

__all__ = [
    "user_roles",
    "role_permissions",
    "Department",
    "User",
    "EmployeeHistoryEvent",
    "FeishuAttendanceDaily",
    "SystemSyncState",
    "Role",
    "Permission",
    "ApprovalRule",
    "Lead",
    "LeadFollowUp",
    "LeadLog",
    "Customer",
    "CustomerFollowUp",
    "Opportunity",
    "OpportunityActivity",
    "Contract",
    "Payment",
    "ReceivablePlan",
    "Receipt",
    "ReceiptAllocation",
    "Refund",
    "Project",
    "ProjectMilestone",
    "ProjectTask",
    "ProjectResourceNeed",
    "Okr",
    "KeyResult",
    "PerformanceCycle",
    "PerformanceAssessment",
    "PerformanceAppeal",
    "FixedAsset",
    "AssetBorrowRequest",
    "AssetBorrowItem",
    "AssetInventorySession",
    "AssetInventoryLine",
    "AssetMaintenance",
    "AssetDepreciationRule",
    "AssetDepreciationSnapshot",
    "AssetDisposal",
    "ShootingSchedule",
    "ShootingScheduleAsset",
    "ShootingScheduleMember",
    "Notification",
    "SystemConfig",
    "SystemDictionary",
    "Delegation",
    "ExportJob",
    "KnowledgeSpace",
    "KnowledgeSource",
    "KnowledgeArticle",
    "Timesheet",
    "Ticket",
    "TicketRecord",
    "Schedule",
    "AuditLog",
]
