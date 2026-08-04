"""
经营总览聚合：对齐高保真原型 overview 布局。
KPI / 收入回款双折线 / 销售漏斗 / 预警 / 项目健康度 / 今日排期 / 组织执行。
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.rbac import collect_data_scopes, user_can, widest_data_scope
from app.models.contract import (
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_COMPLETED,
    CONTRACT_STATUS_SIGNED,
)
from app.models.department import Department
from app.models.okr import OKR_LEVEL_DEPARTMENT, OKR_STATUS_ACTIVE, OKR_STATUS_PENDING
from app.models.opportunity import OPP_STAGE_NEGOTIATION, OPP_STAGE_PROPOSAL
from app.models.schedule import SCHEDULE_TYPE_EXTERNAL
from app.models.user import User
from app.services import (
    contract as contract_service,
    lead as lead_service,
    okr as okr_service,
    opportunity as opportunity_service,
    payment as payment_service,
    project as project_service,
    schedule as schedule_service,
    ticket as ticket_service,
)


def _fmt_money(v: Decimal | float | int) -> str:
    n = float(v or 0)
    return f"¥{n:,.0f}"


def _safe_stats(fn, db: Session, user: User, **kwargs) -> dict:
    try:
        return fn(db, user, **kwargs) or {}
    except Exception:
        return {}


def _shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _wan(amount: Decimal) -> float:
    """元 → 万元，保留 1 位小数。"""
    return float((amount / Decimal("10000")).quantize(Decimal("0.1")))


def build_revenue_trend(
    db: Session,
    user: User,
    *,
    today: Optional[date] = None,
    contracts: Optional[list] = None,
    payments: Optional[list] = None,
) -> list[dict]:
    """近 6 个月：确认收入（合同签署/生效额）+ 已回款（已确认收款），单位万元。"""
    current_month = (today or date.today()).replace(day=1)
    months = [_shift_month(current_month, offset) for offset in range(-5, 1)]
    income = {m.strftime("%Y-%m"): Decimal("0") for m in months}
    cash = {m.strftime("%Y-%m"): Decimal("0") for m in months}

    if user_can(user, "contract:view"):
        rows = contracts
        if rows is None:
            _, rows = contract_service.list_contracts(
                db, user, page=1, page_size=10000, enrich=False
            )
        active_like = {
            CONTRACT_STATUS_SIGNED,
            CONTRACT_STATUS_ACTIVE,
            CONTRACT_STATUS_COMPLETED,
        }
        for c in rows:
            if c.status not in active_like:
                continue
            ref = c.signed_date or c.effective_date
            if ref is None and c.created_at:
                ref = c.created_at.date() if hasattr(c.created_at, "date") else None
            if ref is None:
                continue
            key = ref.strftime("%Y-%m")
            if key in income:
                income[key] += c.amount or Decimal("0")

    if user_can(user, "payment:view"):
        rows = payments
        if rows is None:
            _, rows = payment_service.list_payments(
                db, user, page=1, page_size=10000, enrich=False
            )
        for p in rows:
            if p.status != "confirmed" or p.paid_date is None:
                continue
            key = p.paid_date.strftime("%Y-%m")
            if key in cash:
                cash[key] += p.amount or Decimal("0")

    return [
        {
            "month": m.strftime("%Y-%m"),
            "label": f"{m.month}月",
            "income": _wan(income[m.strftime("%Y-%m")]),
            "cash": _wan(cash[m.strftime("%Y-%m")]),
        }
        for m in months
    ]


def _build_funnel(
    db: Session,
    user: User,
    *,
    lead_s: Optional[dict] = None,
    opp_s: Optional[dict] = None,
) -> list[dict]:
    lead_s = lead_s if lead_s is not None else (
        _safe_stats(lead_service.lead_stats, db, user) if user_can(user, "lead:view") else {}
    )
    opp_s = opp_s if opp_s is not None else (
        _safe_stats(opportunity_service.opportunity_stats, db, user)
        if user_can(user, "opportunity:view")
        else {}
    )
    proposal = 0
    won = int(opp_s.get("won", 0) or 0)
    if user_can(user, "opportunity:view"):
        try:
            proposal, _ = opportunity_service.list_opportunities(
                db, user, stage=OPP_STAGE_PROPOSAL, page=1, page_size=1
            )
        except Exception:
            proposal = 0

    leads_total = int(lead_s.get("total", 0) or 0)
    effective = int(lead_s.get("following", 0) or 0) + int(lead_s.get("converted", 0) or 0)
    opps = int(opp_s.get("total", 0) or 0)
    return [
        {"label": "录入线索", "value": leads_total},
        {"label": "有效线索", "value": effective},
        {"label": "形成商机", "value": opps},
        {"label": "方案报价", "value": proposal},
        {"label": "赢单", "value": won},
    ]


def _build_alerts(
    db: Session,
    user: User,
    *,
    proj: Optional[dict] = None,
    pay: Optional[dict] = None,
    lead_s: Optional[dict] = None,
    contract_s: Optional[dict] = None,
) -> list[dict]:
    alerts: list[dict] = []

    if user_can(user, "project:view"):
        ps = proj if proj is not None else _safe_stats(project_service.project_stats, db, user)
        risk = int(ps.get("high_risk", 0) or 0)
        if risk:
            alerts.append(
                {
                    "key": "project_risk",
                    "symbol": "!",
                    "title": f"{risk} 个项目处于高风险",
                    "detail": "里程碑、进度或遗留问题需介入",
                    "tone": "danger",
                    "path": "/projects",
                    "action": "处理",
                }
            )

    if user_can(user, "payment:view"):
        pay = pay if pay is not None else _safe_stats(payment_service.payment_stats, db, user)
        due = Decimal(str(pay.get("due_soon_amount") or 0))
        overdue = int(pay.get("overdue", 0) or 0)
        if overdue:
            pending_amt = Decimal(str(pay.get("pending_amount") or 0))
            alerts.append(
                {
                    "key": "payment_overdue",
                    "symbol": "¥",
                    "title": f"{overdue} 笔应收已逾期",
                    "detail": (
                        f"待收款合计 {_fmt_money(pending_amt)}"
                        if pending_amt > 0
                        else "请尽快催收或核销"
                    ),
                    "tone": "danger",
                    "path": "/payments",
                    "action": "查看",
                }
            )
        elif due > 0:
            alerts.append(
                {
                    "key": "payment_due_soon",
                    "symbol": "¥",
                    "title": "应收将在短期内到期",
                    "detail": f"合计 {_fmt_money(due)}",
                    "tone": "warning",
                    "path": "/payments",
                    "action": "查看",
                }
            )

    if user_can(user, "ticket:view"):
        ts = _safe_stats(ticket_service.ticket_stats, db, user)
        near = int(ts.get("near_sla", 0) or 0)
        overdue_t = int(ts.get("overdue", 0) or 0)
        if overdue_t:
            alerts.append(
                {
                    "key": "ticket_overdue",
                    "symbol": "↗",
                    "title": f"{overdue_t} 张工单已超时",
                    "detail": "请尽快跟进处理",
                    "tone": "danger",
                    "path": "/tickets",
                    "action": "跟进",
                }
            )
        elif near:
            alerts.append(
                {
                    "key": "ticket_near_sla",
                    "symbol": "↗",
                    "title": f"{near} 张工单接近 SLA",
                    "detail": "剩余时间不足，建议优先处理",
                    "tone": "warning",
                    "path": "/tickets",
                    "action": "跟进",
                }
            )

    if user_can(user, "contract:view"):
        cs = (
            contract_s
            if contract_s is not None
            else _safe_stats(contract_service.contract_stats, db, user)
        )
        pending = int(cs.get("pending_approval", 0) or 0)
        if pending:
            alerts.append(
                {
                    "key": "contract_pending",
                    "symbol": "✓",
                    "title": f"{pending} 份合同待审批",
                    "detail": "等待财务 / 管理层处理",
                    "tone": "warning",
                    "path": "/sales?tab=contracts",
                    "action": "查看",
                }
            )

    if user_can(user, "lead:view"):
        ls = lead_s if lead_s is not None else _safe_stats(lead_service.lead_stats, db, user)
        pending_lead = int(ls.get("pending_assign", 0) or 0)
        if pending_lead:
            alerts.append(
                {
                    "key": "lead_pending",
                    "symbol": "◎",
                    "title": f"{pending_lead} 条线索待分配",
                    "detail": "公共池或待指派线索",
                    "tone": "warning",
                    "path": "/sales?tab=pool",
                    "action": "处理",
                }
            )

    if user_can(user, "schedule:view"):
        ss = _safe_stats(schedule_service.schedule_stats, db, user)
        conflicts = int(ss.get("conflict_count", 0) or 0)
        if conflicts:
            alerts.append(
                {
                    "key": "schedule_conflict",
                    "symbol": "!",
                    "title": f"{conflicts} 项排期冲突",
                    "detail": "人员时间重复占用",
                    "tone": "danger",
                    "path": "/schedules",
                    "action": "处理",
                }
            )

    return alerts[:7]


def _build_project_health(db: Session, user: User) -> dict:
    if not user_can(user, "project:view"):
        return {"score": 0, "healthy": 0, "watch": 0, "risk": 0}
    try:
        _, items = project_service.list_projects(
            db, user, page=1, page_size=5000, enrich=False
        )
    except Exception:
        return {"score": 0, "healthy": 0, "watch": 0, "risk": 0}

    from app.services.project import compute_health

    healthy = watch = risk = 0
    progresses: list[int] = []
    for p in items:
        h = compute_health(p)
        if h == "risk":
            risk += 1
        elif h == "attention":
            watch += 1
        else:
            healthy += 1
        if p.status in {"executing", "accepting", "planning"}:
            progresses.append(int(p.progress or 0))

    score = int(round(sum(progresses) / len(progresses))) if progresses else (
        int(round(100 * healthy / max(healthy + watch + risk, 1)))
    )
    return {"score": score, "healthy": healthy, "watch": watch, "risk": risk}


def _build_today_schedules(db: Session, user: User) -> list[dict]:
    if not user_can(user, "schedule:view"):
        return []
    today = date.today()
    start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    end = datetime.combine(today, time.max, tzinfo=timezone.utc)
    try:
        _, items = schedule_service.list_schedules(
            db, user, date_from=start, date_to=end, page=1, page_size=8
        )
    except Exception:
        return []

    rows = []
    for s in items:
        st = s.start_time
        if st and st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        local = st.astimezone() if st else None
        time_label = local.strftime("%H:%M") if local else "--:--"
        emp = getattr(s, "employee_name", None) or "未指定"
        external = s.schedule_type == SCHEDULE_TYPE_EXTERNAL
        rows.append(
            {
                "id": s.id,
                "time": time_label,
                "title": s.title,
                "subtitle": f"{'外部会议 · ' if external else ''}{emp}",
                "external": external,
                "path": "/schedules",
            }
        )
    return rows


def _build_org_execution(db: Session, user: User) -> list[dict]:
    if not user_can(user, "okr:view"):
        return []
    try:
        _, items = okr_service.list_okrs(db, user, page=1, page_size=5000, enrich=False)
    except Exception:
        return []

    dept_okrs = [
        x
        for x in items
        if x.level == OKR_LEVEL_DEPARTMENT and x.status in {OKR_STATUS_PENDING, OKR_STATUS_ACTIVE}
    ]
    by_dept: dict[int, list[int]] = {}
    for o in dept_okrs:
        if not o.department_id:
            continue
        by_dept.setdefault(o.department_id, []).append(int(o.progress or 0))

    if not by_dept:
        # 无部门 OKR 时用公司/个人平均兜底展示
        active = [x for x in items if x.status in {OKR_STATUS_PENDING, OKR_STATUS_ACTIVE}]
        if not active:
            return []
        avg = int(round(sum(x.progress or 0 for x in active) / len(active)))
        return [{"name": "全公司", "score": avg}]

    dept_ids = list(by_dept.keys())
    depts = {
        d.id: d.name
        for d in db.query(Department).filter(Department.id.in_(dept_ids)).all()
    }
    rows = []
    for did, progresses in by_dept.items():
        score = int(round(sum(progresses) / len(progresses)))
        rows.append({"name": depts.get(did, f"部门#{did}"), "score": score})
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows[:6]


def _mom_delta(curr: Decimal, prev: Decimal) -> tuple[str, str]:
    if prev <= 0 and curr <= 0:
        return "持平", "neutral"
    if prev <= 0:
        return "环比新增", "up"
    pct = float((curr - prev) * Decimal("100") / prev)
    tone = "up" if pct >= 0 else "down"
    sign = "+" if pct >= 0 else ""
    return f"环比 {sign}{pct:.1f}%", tone


def build_dashboard(db: Session, user: User) -> dict:
    role_codes = {r.code for r in user.roles}
    is_admin = "admin" in role_codes
    scope = "company" if is_admin else widest_data_scope(collect_data_scopes(user) or {"personal"})
    display_name = user.real_name or user.username
    now = datetime.now().astimezone()
    as_of = f"截至今天 {now.strftime('%H:%M')}，集中查看经营、回款、项目和组织执行状态。"

    # 各域统计只算一次，后面 KPI / 漏斗 / 预警复用，避免重复打库
    pay = _safe_stats(payment_service.payment_stats, db, user) if user_can(user, "payment:view") else {}
    opp = (
        _safe_stats(opportunity_service.opportunity_stats, db, user)
        if user_can(user, "opportunity:view")
        else {}
    )
    proj = _safe_stats(project_service.project_stats, db, user) if user_can(user, "project:view") else {}
    okr = _safe_stats(okr_service.okr_stats, db, user) if user_can(user, "okr:view") else {}
    lead_s = _safe_stats(lead_service.lead_stats, db, user) if user_can(user, "lead:view") else {}
    contract_s = (
        _safe_stats(contract_service.contract_stats, db, user)
        if user_can(user, "contract:view")
        else {}
    )

    month_income = Decimal(str(pay.get("month_contract_amount") or 0))
    # 上月合同额用于环比（轻量列表，不做 enrich）；同时留给趋势图复用
    prev_income = Decimal("0")
    contracts: list = []
    if user_can(user, "contract:view"):
        today = date.today()
        month_start = today.replace(day=1)
        prev_start = _shift_month(month_start, -1)
        try:
            _, contracts = contract_service.list_contracts(
                db, user, page=1, page_size=10000, enrich=False
            )
            for c in contracts:
                ref = c.signed_date or (c.created_at.date() if c.created_at else None)
                if ref and prev_start <= ref < month_start:
                    prev_income += c.amount or Decimal("0")
        except Exception:
            contracts = []

    confirmed = Decimal(str(pay.get("confirmed_amount") or 0))
    pending_review = Decimal(str(pay.get("pending_review_amount") or 0))
    income_delta, income_tone = _mom_delta(month_income, prev_income)

    proposal = 0
    negotiation = int(opp.get("negotiation", 0) or 0)
    if user_can(user, "opportunity:view"):
        try:
            proposal, _ = opportunity_service.list_opportunities(
                db, user, stage=OPP_STAGE_PROPOSAL, page=1, page_size=1
            )
            if not negotiation:
                negotiation, _ = opportunity_service.list_opportunities(
                    db, user, stage=OPP_STAGE_NEGOTIATION, page=1, page_size=1
                )
        except Exception:
            pass

    open_count = int(opp.get("open_count", 0) or 0)
    executing = int(proj.get("executing", 0) or 0)
    accepting = int(proj.get("accepting", 0) or 0)
    high_risk = int(proj.get("high_risk", 0) or 0)
    on_track = max(executing - high_risk, 0)

    avg_progress = int(okr.get("avg_progress", 0) or 0)
    active_okr = int(okr.get("active", 0) or 0)
    risk_okr = int(okr.get("risk_count", 0) or 0)
    normal_okr = max(active_okr - risk_okr, 0)
    watch_okr = min(risk_okr, max(active_okr // 5, 0)) if active_okr else 0

    kpis: list[dict] = []
    if user_can(user, "payment:view") or user_can(user, "contract:view"):
        kpis.append(
            {
                "key": "month_income",
                "label": "本月确认收入",
                "value": float(month_income),
                "display": _fmt_money(month_income),
                "icon": "¥",
                "note": f"已回款 {_fmt_money(confirmed)} · 待核销 {_fmt_money(pending_review)}",
                "delta": income_delta,
                "delta_tone": income_tone,
                "accent": True,
                "path": "/payments",
            }
        )
    if user_can(user, "opportunity:view"):
        kpis.append(
            {
                "key": "open_opps",
                "label": "有效商机",
                "value": open_count,
                "display": str(open_count),
                "icon": "◎",
                "note": f"方案报价 {proposal} · 商务谈判 {negotiation}",
                "delta": f"赢单 {int(opp.get('won', 0) or 0)} 单",
                "delta_tone": "up",
                "accent": False,
                "path": "/sales?tab=customers",
            }
        )
    if user_can(user, "project:view"):
        kpis.append(
            {
                "key": "executing_projects",
                "label": "执行中项目",
                "value": executing,
                "display": str(executing),
                "icon": "▣",
                "note": f"按期 {on_track} · 延期风险 {high_risk} · 待验收 {accepting}",
                "delta": f"{high_risk} 项预警" if high_risk else "运行平稳",
                "delta_tone": "down" if high_risk else "up",
                "accent": False,
                "path": "/projects",
            }
        )
    if user_can(user, "okr:view"):
        kpis.append(
            {
                "key": "company_okr",
                "label": "公司目标进度",
                "value": active_okr,
                "display": str(active_okr),
                "icon": "◇",
                "note": f"正常 {normal_okr} · 需关注 {watch_okr} · 已阻塞 {max(risk_okr - watch_okr, 0)}",
                "delta": f"完成度 {avg_progress}%",
                "delta_tone": "up" if avg_progress >= 60 else "down",
                "accent": False,
                "path": "/okrs",
            }
        )

    # 不足 4 个时用线索等补齐，保持原型 4 卡视觉
    if len(kpis) < 4 and user_can(user, "lead:view"):
        kpis.append(
            {
                "key": "leads",
                "label": "线索跟进中",
                "value": int(lead_s.get("following", 0) or 0),
                "display": str(int(lead_s.get("following", 0) or 0)),
                "icon": "◎",
                "note": f"本月转化 {int(lead_s.get('converted_month', 0) or 0)} · 公海 {int(lead_s.get('public_pool', 0) or 0)}",
                "delta": f"今日新增 {int(lead_s.get('today_created', 0) or 0)}",
                "delta_tone": "up",
                "accent": False,
                "path": "/sales",
            }
        )

    revenue_trend = []
    if user_can(user, "payment:view") or user_can(user, "contract:view"):
        try:
            revenue_trend = build_revenue_trend(db, user, contracts=contracts)
        except Exception:
            revenue_trend = []

    return {
        "data_scope": scope,
        "display_name": display_name,
        "as_of": as_of,
        "kpis": kpis[:4],
        "revenue_trend": revenue_trend,
        "funnel": _build_funnel(db, user, lead_s=lead_s, opp_s=opp),
        "alerts": _build_alerts(
            db,
            user,
            proj=proj,
            pay=pay,
            lead_s=lead_s,
            contract_s=contract_s,
        ),
        "project_health": _build_project_health(db, user),
        "today_schedules": _build_today_schedules(db, user),
        "org_execution": _build_org_execution(db, user),
    }
