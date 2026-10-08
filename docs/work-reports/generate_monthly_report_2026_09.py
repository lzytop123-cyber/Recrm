# -*- coding: utf-8 -*-
"""生成 2026年9月工作总结与10月工作计划 Word 汇报稿。"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(__file__).resolve().parent / "2026-09总结与2026-10计划.docx"


def set_run_font(run, name="微软雅黑", size=11, bold=False, color=None):
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = name
    if color is not None:
        run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), name)


def add_para(doc, text, *, size=11, bold=False, color=None, align=None, space_after=6, space_before=0):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)
    return p


def add_heading_cn(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        set_run_font(run, size={1: 16, 2: 13, 3: 12}.get(level, 11), bold=True)
    p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    p.paragraph_format.space_after = Pt(6)
    return p


def set_cell_shading(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill_hex)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def set_cell_text(cell, text, *, bold=False, size=10, fill=None):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(str(text) if text is not None else "")
    set_run_font(run, size=size, bold=bold)
    if fill:
        set_cell_shading(cell, fill)
    tcPr = cell._tc.get_or_add_tcPr()
    vAlign = OxmlElement("w:vAlign")
    vAlign.set(qn("w:val"), "center")
    tcPr.append(vAlign)


def add_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], h, bold=True, size=10, fill="1F4E79")
        for run in table.rows[0].cells[i].paragraphs[0].runs:
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for r_idx, row in enumerate(rows):
        fill = "F2F2F2" if r_idx % 2 else None
        for c_idx, val in enumerate(row):
            set_cell_text(table.rows[r_idx + 1].cells[c_idx], val, size=10, fill=fill)
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return table


def build():
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.4)

    # Title
    add_para(
        doc,
        "9 月工作总结与 10 月工作计划",
        size=20,
        bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=4,
    )
    add_para(
        doc,
        "中泰旭鼎 · CRM / OKR 经营管理系统",
        size=12,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        color=RGBColor(0x66, 0x66, 0x66),
        space_after=14,
    )

    add_table(
        doc,
        ["项目", "内容"],
        [
            ["部门", "市场部"],
            ["岗位定位", "技术（业务系统建设与流程落地）"],
            ["汇报周期", "2026 年 9 月总结 / 10 月计划"],
            ["核心抓手", "中泰旭鼎 CRM / OKR 经营系统（二期建设）"],
            ["汇报日期", "2026-09-28"],
        ],
        col_widths=[3.2, 12],
    )

    # 一、岗位说明
    add_heading_cn(doc, "一、岗位说明（汇报口径）", 1)
    add_para(
        doc,
        "本人在市场部，职责侧重技术落地：把销售、交付、人事、绩效协同中的流程规则，做成系统里可执行、可审批、可统计的能力。",
    )
    add_para(doc, "工作价值不按「写了多少代码」衡量，而按：", bold=True, space_after=2)
    add_para(doc, "1. 流程是否跑通（业务动作 → 审批 → 落库 → 可追溯）")
    add_para(doc, "2. 权责是否清晰（谁能看、谁能批、菜单谁能进）")
    add_para(doc, "3. 经营与考核数据是否可信（指标口径一致、可抽检、可复盘）")

    # 二、9月总结
    add_heading_cn(doc, "二、9 月工作总结", 1)

    add_heading_cn(doc, "2.1 总体结论", 2)
    add_para(
        doc,
        "9 月工作重心从一期「经营闭环加固」转向二期建设：在既有 CRM / 审批 / 绩效底座上，推进知识库治理、AI 助手、KPI 七类考核、人事闭环四大方向，形成可对接、可演示、可联调的前后端能力；同时收口 8 月末审批权责与生产稳定性问题。",
    )
    add_para(
        doc,
        "一句话：一期解决「合同—回款—交付能不能批、能不能结」；二期解决「知识能不能信、考核能不能算、人事能不能办、AI 能不能帮」。",
        bold=True,
    )

    add_heading_cn(doc, "2.2 重点成果", 2)

    add_heading_cn(doc, "（1）二期 PRD 对齐与实施清单落地", 3)
    add_para(
        doc,
        "对照《CRM+OKR 公司管理系统二期 PRD（V2.0）》梳理工作与接口清单，明确「已有 / 要做」边界：一期销售、合同、项目、工单、排期、固定资产等业务接口不重写；二期按 AI、人事、KPI 三条主线补齐。输出对接说明与实施记录，方便前后端并行推进。",
    )

    add_heading_cn(doc, "（2）企业知识库治理 + 智能助手", 3)
    add_para(doc, "业务目标：管理员把制度接进来并发布，员工只在智能助手里问；没有依据就拒答，不能编。", bold=True, space_after=4)
    add_para(doc, "已落地能力（摘要）：")
    add_para(doc, "· 知识条目状态机：草稿 / 待审 / 已发布 / 停用 / 归档；审核、发布、纠错出新版本（禁止无痕覆盖）")
    add_para(doc, "· 飞书来源同步、附件上传与正文抽取、目录空间管理")
    add_para(doc, "· 前端：知识库工作台、条目治理、审核页、飞书同步配置；右下角智能助手（Agent 抽屉）")
    add_para(doc, "· 问答侧：助手检索已发布知识并要求引用来源，降低「瞎答」风险")

    add_heading_cn(doc, "（3）AI Agent 平台与场景能力", 3)
    add_para(doc, "已落地能力（摘要）：")
    add_para(doc, "· 通用多轮对话（SSE）与写操作确认机制，工具调用按当前用户身份执行，禁止越权")
    add_para(doc, "· 场景运行与 Prompt 模板 / 调用审计 / Token 预算等管理接口骨架")
    add_para(doc, "· 对话记忆、场景一键停用等底座，为日报生成、跟进摘要、工单推荐、审批预审等场景预留入口")
    add_para(doc, "说明：本月以「能问、能管、能审计」为主；部分场景一键按钮与前端全量联调仍在推进。")

    add_heading_cn(doc, "（4）KPI 七类考核与绩效运行期", 3)
    add_para(
        doc,
        "业务目标：把各部门考核制度落到可配置模板与可试算规则上，支撑「发起 → 填报/取数 → 确认 → 归档 → 工资」链路。",
        bold=True,
        space_after=4,
    )
    add_para(doc, "已落地能力（摘要）：")
    add_para(doc, "· 规则引擎：签约扣分、线索门槛、满分冲突、观察期、造假一票否决等关键规则入引擎")
    add_para(doc, "· 指标库、模板生命周期（草稿 / 发布 / 停用）、人员匹配、考核批次、材料任务、流转审计")
    add_para(
        doc,
        "· 源表落库：讲师 / 直播主播 / 直播投手 / 品宣 / 内容制作 / AI 运维等考核表接入；市场部与入职培训两类因规则冲突暂阻断发布",
    )
    add_para(doc, "· 前端：KPI 模板、待办、考核页；绩效管理布局与周期/自评/团队等页面并行推进")
    add_para(doc, "· 测试：规则与运行期相关用例已批量通过（本地回归）")

    add_heading_cn(doc, "（5）人事闭环（合同 / 转岗离职 / 假勤 / 工资条）", 3)
    add_para(doc, "业务目标：合同、假勤、转岗离职、工资条在系统里走完；人走了，名下事项清完才能关账号。", bold=True, space_after=4)
    add_para(doc, "已落地能力（摘要）：")
    add_para(doc, "· 劳动合同台账、续签审批、到期预警（含试用期）")
    add_para(doc, "· 转岗申请、离职交接（接收人确认、未完事项检查后禁用账号）")
    add_para(doc, "· 假勤申请走审批中心、余额台账；工资条本人查看与财务更正路径")
    add_para(doc, "· 前端：人事办理工作台（合同 / 转岗 / 离职 / 假勤 / 工资条 / 看板）与「我的假勤工资」")

    add_heading_cn(doc, "（6）审批权责与一期稳定性收口", 3)
    add_para(doc, "8 月末至 9 月初，围绕「批对人、看得见、通知懂」做了加固：")
    add_para(doc, "· 部门 / 中心负责人审批按申请人部门（含上级链）匹配，堵住跨部门、跨中心误审")
    add_para(doc, "· 审批规则支持指定具体审批人；无合同立项等特批路径按业务调整")
    add_para(doc, "· 飞书审批通知去掉晦涩单号，保留中文可读信息；管理员可催办任意审批")
    add_para(doc, "· 资产领用/归还、资源确认等按钮按角色可见；排期新建改由权限码控制")
    add_para(doc, "· 考勤同步日期钳制、seed 角色权限「只增不减」、生产构建调试代码清理等稳定性修复")

    add_heading_cn(doc, "2.3 本月交付物一览", 2)
    add_table(
        doc,
        ["类别", "代表产出", "状态"],
        [
            ["方案 / 清单", "二期 PRD 工作与接口清单、AI/KPI 执行文档", "已输出"],
            ["知识库", "治理接口 + 管理页 + 智能助手对接", "可联调 / 待上线验收"],
            ["AI Agent", "对话、场景、Prompt/审计底座", "骨架就绪 / 场景深化中"],
            ["KPI 绩效", "七类规则引擎 + 运行期接口 + 前端考核页", "可试算 / 部分模板待解冲突"],
            ["人事闭环", "合同/转岗离职/假勤/工资条 + 人事工作台", "可联调 / 待业务验收"],
            ["审批加固", "跨部门误审修复、通知与催办体验", "已合入主干"],
        ],
        col_widths=[3.2, 8.5, 3.5],
    )

    add_heading_cn(doc, "2.4 不足与反思", 2)
    add_para(doc, "1. 二期面铺得较宽：知识库、KPI、人事、AI 并行推进，生产环境尚未形成「整包可验收」的上线节奏。")
    add_para(doc, "2. KPI 外部实时取数、工资批次写回仍未接通；市场部 / 入职培训两类考核因规则冲突暂不能当正式制度发布。")
    add_para(doc, "3. AI 场景（日报、跟进摘要、工单推荐、审批预审）后端骨架有了，一线一键入口与抽查机制还需打磨。")
    add_para(doc, "4. 操作手册与现场演示滞后于功能：一期核销/验收培训债仍在，二期又增加人事与考核新流程，需要用业务语言补 SOP。")
    add_para(doc, "5. 部分二期代码仍在本地联调分支，合入与迁移上生产库需走完整回归，避免影响一期稳定业务。")

    # 三、10月计划
    add_heading_cn(doc, "三、10 月工作计划", 1)

    add_heading_cn(doc, "3.1 目标一句话", 2)
    add_para(
        doc,
        "把二期能力从「能演示、能联调」推到「能上线、会使用、可抽检」：优先打通 KPI 月度考核与人事办结两条刚需链路，知识库先发一批已审制度，AI 场景选 1～2 个高频入口试点。",
        bold=True,
    )

    add_heading_cn(doc, "3.2 重点计划（按优先级）", 2)
    add_table(
        doc,
        ["优先级", "事项", "产出", "预计"],
        [
            ["P0", "KPI：解市场部/入职培训模板冲突；完成一轮「发起考核→确认→归档」联调", "可跑通的月度考核演示 + 问题清单", "第 1–2 周"],
            ["P0", "人事：合同到期预警 + 离职交接实操验收（人事/接收人）", "验收记录 + 1 页 SOP", "第 1–2 周"],
            ["P0", "二期合入主干与生产迁移方案（含回滚）", "上线检查表 + 回归用例", "第 2 周"],
            ["P1", "知识库：首批制度审核发布；助手问答抽检（有引用/拒答）", "发布清单 + 抽检报告", "第 2–3 周"],
            ["P1", "AI 试点：选「知识问答 / 跟进摘要」其中 1–2 个场景做入口联调", "试点入口 + 开关与审计可查", "第 3 周"],
            ["P1", "审批：催办频控与逾期可视；补退回/转交/重提前端封装", "体验清单关闭", "第 2–3 周"],
            ["P2", "KPI 外部取数 / 工资批次联动方案对齐财务", "方案结论或一期联动", "第 3–4 周"],
            ["持续", "缺陷收敛、一期经营闭环稳定、变更用业务语言同步部门", "周更问题与变更说明", "全月"],
        ],
        col_widths=[2.2, 6.2, 4.5, 2.5],
    )

    add_heading_cn(doc, "3.3 与市场部业务的对齐方式", 2)
    add_para(doc, "建议固定两个对齐节奏（可并入部门例会）：")
    add_para(doc, "1. 周初 15 分钟：本周要上线的流程变更（谁受影响、怎么操作）。")
    add_para(doc, "2. 月末 30 分钟：抽检——抽几笔考核单看口径、抽几份交接单看是否断链、抽几条助手问答看是否乱答。")
    add_para(doc, "本人继续输出用业务语言写的变更说明，避免只丢技术更新日志。")

    add_heading_cn(doc, "3.4 个人能力与协作", 2)
    add_para(doc, "· 加深对考核制度口径、人事办结门槛、知识发布责任的理解，技术方案先问「业务能不能批、数据能不能信」。")
    add_para(doc, "· 与人事、财务、交付、销售接口人保持短反馈环；争议规则先对齐再改系统。")
    add_para(doc, "· 保持「最小可用上线 → 审批可追溯 → 再增强」的节奏，10 月优先收口而非继续铺面。")

    # 四、需要支持
    add_heading_cn(doc, "四、需要部门支持的事项", 1)
    add_para(doc, "1. 明确 KPI 月度考核试点部门与周期（建议先选规则已发布的岗位类，避开冲突模板）。")
    add_para(doc, "2. 指定人事侧 1～2 名业务验收人：合同续签、离职交接、工资条查看各走一遍。")
    add_para(doc, "3. 指定知识管理员：首批可发布制度清单（合同模板、销售制度、交付规范等）。")
    add_para(doc, "4. 安排一次 30～40 分钟部门演示窗口（可录屏）：覆盖「助手怎么问、考核怎么走、人事怎么办」。")

    # 五、收束
    add_heading_cn(doc, "五、一句话收束", 1)
    add_para(
        doc,
        "9 月：把二期「知识可信、考核可算、人事可办、AI 可帮」的底座与页面骨架搭起来，并收口审批误审等一期风险。",
    )
    add_para(
        doc,
        "10 月：选刚需链路做实操验收与上线，让市场部月度经营复盘能用上考核与人事数据，让一线能用助手问到已发布制度。",
        bold=True,
    )

    add_para(
        doc,
        "文档用途：部门 9 月总结 / 10 月计划会议汇报稿。可根据当晚会议口径删减举例细节。",
        size=9,
        color=RGBColor(0x88, 0x88, 0x88),
        space_before=16,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"OK: {OUT}")


if __name__ == "__main__":
    build()
