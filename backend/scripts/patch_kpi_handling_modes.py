"""按「谁掌握事实」重配正式模板指标填报归属：员工填 / 主管填，取消系统自动抓取。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

load_dotenv(Path("backend/.env"))
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

# metric_key → employee_submit | manager_score
# 未列出的：加分/数量类默认员工；减分/投诉/主观评价默认主管
MANAGER_KEYS = {
    # 市场
    "market.response_late",
    "market.collaboration",
    "market.sync",
    "market.reports",
    "market.solution",
    "market.sales_sop",
    # 运维
    "ops.complaints",
    "ops.service",
    # 内容
    "content.complaints",
    # 品宣
    "brand.video_quality",
    "brand.attitude",
    "brand.compliance",
    "brand.ledger",
    # 直播主播
    "live.review",
    "live.violation",
    "live.drive",
    "live.optimize",
    "live.learn",
    # 直播投手
    "ads.review",
    "ads.drive",
    "ads.optimize",
    "ads.learn",
    # 讲师：评价/扣分/投诉/规范类
    "lecturer.talk_good",
    "lecturer.talk_excellent",
    "lecturer.internal_excellent",
    "lecturer.talk_bad",
    "lecturer.talk_complaint",
    "lecturer.internal_bad",
    "lecturer.internal_complaint",
    "lecturer.behavior",
    "lecturer.behavior_impact",
    "lecturer.etiquette",
    "lecturer.knowledge",
    "lecturer.absence",
}

EMPLOYEE_KEYS = {
    # 市场
    "market.valid_leads",
    "market.signed_clients",
    "market.new_customers",
    "market.visits",
    "market.valid_channels",
    # 运维
    "ops.published",
    "ops.views",
    "ops.leads",
    "ops.renewals",
    # 内容
    "content.output",
    "content.views",
    "content.leads",
    # 品宣
    "brand.shoot_count",
    "brand.copy_count",
    "brand.views",
    "brand.likes",
    "brand.shares",
    "brand.poster",
    "brand.poster_copy",
    "brand.poster_forward",
    "brand.private_leads",
    "brand.store_visit",
    "brand.salon",
    "brand.private_retain",
    "brand.yuling_visit",
    "brand.assoc_expand",
    "brand.assoc_convert",
    "brand.assoc_invite",
    # 直播
    "live.gmv",
    "live.convert",
    "live.hours",
    "ads.gmv",
    "ads.convert",
    "ads.cost",
    # 讲师：员工清楚的业务结果
    "lecturer.lead",
    "lecturer.lead_sign",
    "lecturer.collab_sign",
    "lecturer.revenue",
}

# 名称关键词兜底（无 metric_key / custom 项）
MANAGER_NAME_HINTS = (
    "投诉", "违规", "缺席", "行为规范", "礼仪", "知识库", "协同", "响应时效",
    "同步", "复盘", "服务客户", "工作态度", "合规", "台账", "主观能动", "学习力",
    "工作优化", "视频质量", "评差", "评优", "评分<", "评分＞", "评分>",
)
EMPLOYEE_NAME_HINTS = (
    "线索", "签约", "拜访", "拓展", "播放", "客资", "发布", "续约", "数量",
    "时长", "完成率", "转化", "费用", "商机", "收入", "拍摄", "文案", "点赞",
    "转发", "引流", "到店", "沙龙", "协会", "海报", "需求分析", "销售标准",
)


def decide(metric_key: str | None, name: str, score_rule: str | None) -> str:
    key = (metric_key or "").strip()
    if key in MANAGER_KEYS:
        return "manager_score"
    if key in EMPLOYEE_KEYS:
        return "employee_submit"
    # custom / 无 key：按名称与规则
    n = name or ""
    if any(h in n for h in MANAGER_NAME_HINTS):
        return "manager_score"
    if score_rule in ("event_deduction",) or (score_rule or "").endswith("deduction"):
        return "manager_score"
    if any(h in n for h in EMPLOYEE_NAME_HINTS):
        return "employee_submit"
    if score_rule in ("event_bonus", "manual_points"):
        # 默认：加分/数量员工，主观名已在 manager hints
        return "employee_submit"
    return "manager_score"


def main() -> None:
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, status FROM performance_templates
                WHERE status IN ('published', 'approved')
                ORDER BY id
                """
            )
            tpls = cur.fetchall()
            print("templates:", tpls)

            updated = []
            for tid, tname, status in tpls:
                cur.execute(
                    """
                    SELECT id, name, metric_key, score_rule, handling_mode, data_source
                    FROM performance_template_items
                    WHERE template_id=%s
                    ORDER BY order_no, id
                    """,
                    (tid,),
                )
                for iid, name, mkey, rule, old_h, old_src in cur.fetchall():
                    mode = decide(mkey, name, rule)
                    cur.execute(
                        """
                        UPDATE performance_template_items
                        SET handling_mode=%s,
                            data_source='manual',
                            source_ref=COALESCE(NULLIF(source_ref,''), 'ledger.manual'),
                            updated_at=NOW()
                        WHERE id=%s
                        """,
                        (mode, iid),
                    )
                    updated.append((tid, tname, iid, name, mkey, old_h, mode))

            # 指标库同步（有则改）
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name='performance_indicator_definitions'
                """
            )
            ind_cols = {r[0] for r in cur.fetchall()}
            if {"metric_key", "handling_mode", "data_source_code"} <= ind_cols:
                cur.execute(
                    "SELECT id, metric_key, name, handling_mode FROM performance_indicator_definitions"
                )
                for iid, mkey, name, old_h in cur.fetchall():
                    mode = decide(mkey, name or "", None)
                    cur.execute(
                        """
                        UPDATE performance_indicator_definitions
                        SET handling_mode=%s,
                            data_source_code='ledger.manual'
                        WHERE id=%s
                        """,
                        (mode, iid),
                    )

            # 同步 definition_json 内 items 的 handling（若存在）
            for tid, tname, status in tpls:
                cur.execute(
                    "SELECT definition_json FROM performance_templates WHERE id=%s",
                    (tid,),
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    continue
                defn = row[0]
                if isinstance(defn, str):
                    try:
                        defn = json.loads(defn)
                    except json.JSONDecodeError:
                        continue
                if not isinstance(defn, dict):
                    continue
                items = defn.get("items")
                if not isinstance(items, list):
                    continue
                changed = False
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    name = str(it.get("name") or "")
                    mkey = it.get("metric_key")
                    rule = None
                    r = it.get("rule")
                    if isinstance(r, dict):
                        rule = r.get("type")
                    mode = decide(mkey, name, rule)
                    if it.get("handling_mode") != mode:
                        it["handling_mode"] = mode
                        changed = True
                    if it.get("data_source") == "system":
                        it["data_source"] = "manual"
                        changed = True
                if changed:
                    cur.execute(
                        """
                        UPDATE performance_templates
                        SET definition_json=%s::jsonb, updated_at=NOW()
                        WHERE id=%s
                        """,
                        (json.dumps(defn, ensure_ascii=False), tid),
                    )

        conn.commit()

    print("\nUPDATED:")
    for row in updated:
        print(f"  tpl#{row[0]} {row[1]} | {row[3]} ({row[4]}) {row[5]} -> {row[6]}")
    print(f"\ntotal items: {len(updated)}")


if __name__ == "__main__":
    main()
