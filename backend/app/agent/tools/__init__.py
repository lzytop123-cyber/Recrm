"""Agent 工具包。"""
from app.agent.tools.approval import (
    act_on_approval,
    get_approval_status,
    list_my_pending_approvals,
    precheck_approval,
)
from app.agent.tools.customer import (
    create_customer,
    get_customer_detail,
    list_my_customers,
    search_customers,
)
from app.agent.tools.followup import get_followup_records
from app.agent.tools.knowledge import search_knowledge
from app.agent.tools.lead import (
    add_lead_follow_up,
    assign_lead,
    convert_lead,
    create_lead,
    get_lead_detail,
    list_my_leads,
    search_leads,
)
from app.agent.tools.okr import create_key_result, get_okr_detail, list_my_okrs, my_okr_stats
from app.agent.tools.opportunity import (
    add_opportunity_activity,
    change_opportunity_stage,
    create_opportunity,
    get_opportunity_detail,
    list_my_opportunities,
    search_opportunities,
)
from app.agent.tools.performance import (
    create_performance_appeal,
    get_assessment_detail,
    get_cycle_launch_progress,
    list_my_assessments,
    list_team_assessments,
    submit_manager_rate,
    submit_self_rate,
)
from app.agent.tools.project import (
    get_project_detail,
    list_my_projects,
    search_projects,
    update_project_manager,
)
from app.agent.tools.ticket import get_ticket_detail, list_my_tickets, recommend_ticket_solutions
from app.agent.tools.work_report import get_work_report_facts

ALL_TOOLS = [
    search_knowledge,
    get_work_report_facts,
    get_followup_records,
    recommend_ticket_solutions,
    list_my_tickets,
    get_ticket_detail,
    precheck_approval,
    list_my_projects,
    search_projects,
    get_project_detail,
    list_my_okrs,
    get_okr_detail,
    my_okr_stats,
    list_my_pending_approvals,
    get_approval_status,
    act_on_approval,
    list_my_customers,
    search_customers,
    get_customer_detail,
    update_project_manager,
    list_my_leads,
    search_leads,
    get_lead_detail,
    create_lead,
    add_lead_follow_up,
    assign_lead,
    convert_lead,
    list_my_opportunities,
    search_opportunities,
    get_opportunity_detail,
    create_opportunity,
    change_opportunity_stage,
    add_opportunity_activity,
    list_my_assessments,
    list_team_assessments,
    get_assessment_detail,
    get_cycle_launch_progress,
    submit_self_rate,
    submit_manager_rate,
    create_performance_appeal,
    create_customer,
    create_key_result,
]
