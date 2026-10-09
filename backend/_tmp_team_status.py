import sys

sys.stdout.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models.performance import PerformanceAssessment, PerformanceTemplate
from app.models.user import User

db = SessionLocal()
users = db.query(User).filter(User.real_name.like("%刘%") | User.real_name.like("%王文%") | User.real_name.like("%郝%")).all()
print("users", [(u.id, u.real_name, u.manager_id) for u in users])
rows = (
    db.query(PerformanceAssessment)
    .order_by(PerformanceAssessment.id.desc())
    .limit(30)
    .all()
)
for r in rows:
    tpl = db.get(PerformanceTemplate, r.template_id) if r.template_id else None
    u = db.get(User, r.user_id)
    print(
        r.id,
        u.real_name if u else r.user_id,
        "kind=",
        r.assessment_kind,
        "status=",
        r.status,
        "mgr=",
        r.manager_id,
        "tpl=",
        (tpl.name if tpl else None),
        "tpl_kind=",
        (tpl.assessment_kind if tpl else None),
    )
db.close()
