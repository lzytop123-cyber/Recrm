"""独立发布审批流规则（首批 AP-18/AP-01/AP-02/AP-21）。

与完整 `python -m app.seed` 相比，本入口只做两件事：
  1) 建出审批引擎的两张表（approval_instances / approval_tasks，若缺）
  2) 写入并发布 4 条首批审批规则

不重灌角色/权限，避免历史库 schema 漂移导致整体 seed 失败。

用法（backend 目录、已激活 venv）：
    python -m app.seed_approval_flow
"""
from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401 确保全部模型在 metadata 注册
from app.seed import seed_approval_rules


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_approval_rules(db)
        db.commit()
        print("[seed] 审批流引擎表已就绪，首批 4 条规则已发布")
    finally:
        db.close()


if __name__ == "__main__":
    main()
