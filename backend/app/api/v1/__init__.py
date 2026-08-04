"""API v1 路由聚合。"""
from fastapi import APIRouter

from app.api.v1 import (
    approvals,
    assets,
    auth,
    contracts,
    customers,
    dashboard,
    finance,
    knowledge,
    leads,
    okrs,
    opportunities,
    org,
    payments,
    performance,
    projects,
    schedules,
    system,
    tickets,
    timesheets,
    uploads,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(approvals.router)
api_router.include_router(leads.router)
api_router.include_router(customers.router)
api_router.include_router(opportunities.router)
api_router.include_router(contracts.router)
api_router.include_router(uploads.router)
api_router.include_router(finance.router)
api_router.include_router(payments.router)
api_router.include_router(projects.router)
api_router.include_router(okrs.router)
api_router.include_router(performance.router)
api_router.include_router(assets.router)
api_router.include_router(knowledge.router)
api_router.include_router(timesheets.router)
api_router.include_router(tickets.router)
api_router.include_router(schedules.router)
api_router.include_router(org.router)
api_router.include_router(system.router)
