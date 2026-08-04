"""经营总览 Schema。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class OverviewKpi(BaseModel):
    key: str
    label: str
    value: float | int
    display: str
    icon: str = ""
    note: str = ""
    delta: str = ""
    delta_tone: str = Field("up", description="up/down/neutral")
    accent: bool = False
    path: Optional[str] = None


class RevenueTrendPoint(BaseModel):
    month: str
    label: str
    income: float = Field(description="确认收入（万元）")
    cash: float = Field(description="已回款（万元）")


class FunnelStep(BaseModel):
    label: str
    value: int


class AlertItem(BaseModel):
    key: str
    symbol: str
    title: str
    detail: str
    tone: str = "warning"
    path: str
    action: str = "查看"


class ProjectHealthOut(BaseModel):
    score: int
    healthy: int
    watch: int
    risk: int


class TodayScheduleItem(BaseModel):
    id: int
    time: str
    title: str
    subtitle: str
    external: bool = False
    path: str = "/schedules"


class OrgScoreItem(BaseModel):
    name: str
    score: int


class DashboardOut(BaseModel):
    data_scope: str
    display_name: str
    as_of: str
    kpis: List[OverviewKpi] = []
    revenue_trend: List[RevenueTrendPoint] = []
    funnel: List[FunnelStep] = []
    alerts: List[AlertItem] = []
    project_health: ProjectHealthOut = Field(
        default_factory=lambda: ProjectHealthOut(score=0, healthy=0, watch=0, risk=0)
    )
    today_schedules: List[TodayScheduleItem] = []
    org_execution: List[OrgScoreItem] = []
