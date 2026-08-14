# CRM Management Architecture Diagram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained 16:9 HTML/SVG diagram that explains the CRM+OKR system's layered operating architecture to management.

**Architecture:** Use Diagram Design's Architecture grammar with four vertical tiers: Feishu collaboration, the left-to-right commercial chain, management controls, and a unified governance/data foundation. Keep the figure static, brand-matched, and limited to seven nodes and six labeled connectors.

**Tech Stack:** Standalone HTML5, embedded CSS, inline accessible SVG, Noto Serif SC, Noto Sans SC, Geist Mono, Diagram Design `self_check.py`, browser visual inspection.

## Global Constraints

- Output file: `docs/diagrams/crm-management-architecture.html`.
- Output format: one self-contained HTML file; the only external dependency allowed is the exact Google Fonts CSS2 URL.
- Size preset: `slide-16x9`; SVG `viewBox="0 0 1600 800"` inside a page intended for a 1600×900 viewport.
- Diagram type: Architecture; static, no JavaScript and no animation.
- Brand tokens: paper `#f8fafc`, paper-2 `#f1f5f9`, ink `#0f172a`, muted `#64748b`, soft `#94a3b8`, accent `#1e40af`, accent-tint `#eff6ff`, link `#3b82f6`.
- Typography: title Noto Serif SC 700; node names Noto Sans SC 600; technical labels Geist Mono.
- Complexity: exactly 7 principal nodes, 6 connectors, and 2 focal nodes.
- Connector rules: straight lines only for shared axes; otherwise rounded orthogonal paths with 8px bends; no diagonal connectors, shared stroke paths, hidden connectors, or labels touching their lines.
- Every coordinate, font size, node dimension, and layout gap must be divisible by 4.
- Exclude technical topology, database details, API protocols, approval internals, salary formulas, animation, PNG, and SVG exports.
- Use the wording `财务确认`; never imply automatic bookkeeping or treat unverified finance data as authoritative.
- Present OKR and performance as management constraints and evaluation; never imply automatic calibration or salary approval.

---

## File Structure

- Create `docs/diagrams/crm-management-architecture.html`: the complete deliverable, including page frame, embedded brand CSS, accessible SVG, zones, connectors, nodes, legend, and footer note.
- Reference `docs/superpowers/specs/2026-08-14-crm-management-architecture-diagram-design.md`: approved scope and acceptance criteria; do not modify during implementation.
- Reference `C:/Users/Administrator/.codex/skills/diagram-design/assets/template.html`: base single-file structure.
- Run `C:/Users/Administrator/.codex/skills/diagram-design/scripts/self_check.py`: packaged safety and accessibility verifier.

---

### Task 1: Build the branded management architecture diagram

**Files:**
- Create: `docs/diagrams/crm-management-architecture.html`
- Reference: `docs/superpowers/specs/2026-08-14-crm-management-architecture-diagram-design.md`

**Interfaces:**
- Consumes: the approved seven-node information architecture and CRM brand tokens.
- Produces: a standalone HTML document whose SVG exposes `data-node`, `data-connector`, and `data-focal` attributes for deterministic checks.

- [ ] **Step 1: Verify the deliverable does not already exist**

Run:

```powershell
Test-Path 'docs/diagrams/crm-management-architecture.html'
```

Expected: `False`. If it is `True`, inspect the file and preserve any user-authored content before proceeding.

- [ ] **Step 2: Create the page frame and brand CSS**

Create the file with `lang="zh-CN"`, the exact font stylesheet, and these root variables:

```html
<link href="https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@400;500;600;700&family=Noto+Serif+SC:wght@600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --paper:#f8fafc; --paper-2:#f1f5f9; --ink:#0f172a;
    --muted:#64748b; --soft:#94a3b8; --accent:#1e40af;
    --accent-tint:#eff6ff; --link:#3b82f6; --rule:#cbd5e1;
    --sans:'Noto Sans SC','Segoe UI','Microsoft YaHei',sans-serif;
    --serif:'Noto Serif SC','Songti SC',serif;
    --mono:'Geist Mono',ui-monospace,monospace;
  }
</style>
```

The body must use `background:var(--paper)`, have no shadows, and present an eyebrow, the title `CRM+OKR 统一经营管理架构`, and a one-line management subtitle.

- [ ] **Step 3: Add the accessible SVG skeleton and markers**

Use this exact contract:

```html
<svg viewBox="0 0 1600 800" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-labelledby="crm-management-architecture-title crm-management-architecture-desc">
  <title id="crm-management-architecture-title">CRM+OKR 统一经营管理架构</title>
  <desc id="crm-management-architecture-desc">管理层架构图，展示飞书协同入口、销售到项目交付的核心经营链路、目标绩效与经营预警，以及统一治理和数据底座。</desc>
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#64748b"/></marker>
    <marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#1e40af"/></marker>
    <marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#3b82f6"/></marker>
  </defs>
</svg>
```

The `<title>` must remain the first child of `<svg>`.

- [ ] **Step 4: Draw the four tiers before drawing nodes**

Use three light zones and one foundation strip:

| Tier | Zone coordinates | Content coordinates |
|---|---:|---:|
| Feishu collaboration | `x=80 y=40 w=1440 h=120` | node `x=520 y=80 w=560 h=64` |
| Core operating chain | `x=80 y=192 w=1440 h=200` | nodes `x=160/640/1120 y=256 w=320 h=96` |
| Management controls | `x=80 y=424 w=1440 h=144` | nodes `x=160/1120 y=472 w=320 h=64` |
| Unified foundation | no zone; strip node | node `x=240 y=608 w=1120 h=64` |

Zone fills use `rgba(15,23,42,0.02)`, strokes use `rgba(15,23,42,0.10)`, and each zone label sits on a paper mask at least 16px above the first enclosed node.

- [ ] **Step 5: Draw all six connectors before nodes**

Add `data-connector` to each connector and use these relationships:

| Connector | From → To | Label | Treatment |
|---|---|---|---|
| `feishu-entry` | 飞书协同入口 → 销售中心 | 统一入口 | link-blue rounded orthogonal path |
| `lead-to-contract` | 销售中心 → 合同回款 | 商机转化 | horizontal muted line |
| `contract-to-project` | 合同回款 → 项目交付 | 商务交接 | horizontal accent line |
| `okr-to-sales` | OKR · 绩效 → 销售中心 | 目标评价 | dashed vertical muted line, arrow points upward |
| `project-to-dashboard` | 项目交付 → 经营看板 · 预警 | 进度风险 | vertical muted line |
| `contract-to-dashboard` | 合同回款 → 经营看板 · 预警 | 回款预警 | rounded orthogonal accent path |

For every label, add a paper-colored mask whose nearest edge is 8px from the connector. Use distinct attach points on the dashboard's top edge: `x=1200` for project facts and `x=1240` for contract alerts.

- [ ] **Step 6: Draw exactly seven nodes after the connectors**

Each node must include a unique `data-node` value:

```text
feishu-collaboration  飞书协同入口      工作台 · 通讯录 · 日历 · 消息
sales-center          销售中心          线索 · 客户 · 商机
contract-receivables  合同回款          合同 · 收款计划 · 财务确认
project-delivery      项目交付          立项 · 计划 · 任务 · 验收
okr-performance       OKR · 绩效        目标对齐 · 过程评价 · 结果校准
dashboard-alerts      经营看板 · 预警   指标汇总 · 异常识别 · 管理纠偏
governance-foundation 统一治理与数据底座 组织权限 · 统一数据 · 审计留痕 · 知识库
```

Add `data-focal` only to `contract-receivables` and `dashboard-alerts`. Focal nodes use accent stroke and accent-tint fill; stores/foundation use paper-2 and muted stroke; all other nodes use white fill and ink or soft strokes.

- [ ] **Step 7: Add a bottom legend and management note**

Place a hairline separator at `y=712`, a horizontal legend row below it, and this note at the far right:

```text
一套数据口径 · 一条经营主线 · 两类管理抓手
```

The legend may describe only the treatments actually used: primary flow, management signal, Feishu/external integration, and unified foundation.

- [ ] **Step 8: Run the packaged self-check**

Run:

```powershell
python 'C:/Users/Administrator/.codex/skills/diagram-design/scripts/self_check.py' 'docs/diagrams/crm-management-architecture.html'
```

Expected: exit code `0` and no reported failures.

- [ ] **Step 9: Commit the initial diagram**

```powershell
git add -- 'docs/diagrams/crm-management-architecture.html'
git commit -m "docs: add CRM management architecture diagram"
```

---

### Task 2: Verify structure, geometry, and slide readability

**Files:**
- Modify only if verification finds a defect: `docs/diagrams/crm-management-architecture.html`
- Test: `docs/diagrams/crm-management-architecture.html`

**Interfaces:**
- Consumes: the HTML artifact from Task 1.
- Produces: a checked artifact with proven node/connector/focal counts, accessible SVG metadata, valid single-file safety, and visually readable 16:9 composition.

- [ ] **Step 1: Run deterministic structure assertions**

Run:

```powershell
$diagram = Get-Content -Raw 'docs/diagrams/crm-management-architecture.html'
$nodeCount = ([regex]::Matches($diagram, 'data-node=')).Count
$connectorCount = ([regex]::Matches($diagram, 'data-connector=')).Count
$focalCount = ([regex]::Matches($diagram, 'data-focal=')).Count
if ($nodeCount -ne 7 -or $connectorCount -ne 6 -or $focalCount -ne 2) {
  throw "Unexpected counts: nodes=$nodeCount connectors=$connectorCount focal=$focalCount"
}
"STRUCTURE_OK nodes=$nodeCount connectors=$connectorCount focal=$focalCount"
```

Expected: `STRUCTURE_OK nodes=7 connectors=6 focal=2`.

- [ ] **Step 2: Check prohibited patterns and unresolved placeholders**

Run:

```powershell
$diagram = Get-Content -Raw 'docs/diagrams/crm-management-architecture.html'
$forbidden = @('JetBrains Mono','box-shadow','writing-mode','[diagram-slug]')
$hits = $forbidden | Where-Object { $diagram.Contains($_) }
if ($hits) { throw "Forbidden content: $($hits -join ', ')" }
if ($diagram -match '<line[^>]+x1="(\d+)"[^>]+y1="(\d+)"[^>]+x2="(\d+)"[^>]+y2="(\d+)"' ) {
  # Every line element is reviewed visually; off-axis relationships must be paths.
  'LINE_ELEMENTS_PRESENT_REVIEW_AXES'
}
'CONTENT_GUARDS_OK'
```

Expected: `CONTENT_GUARDS_OK`; any `<line>` elements must be horizontal or vertical separators/connectors.

- [ ] **Step 3: Re-run the full packaged verification**

Run:

```powershell
python 'C:/Users/Administrator/.codex/skills/diagram-design/scripts/self_check.py' 'docs/diagrams/crm-management-architecture.html'
```

Expected: exit code `0` and no failures.

- [ ] **Step 4: Inspect the rendered slide at 1600×900**

Open the local HTML in the app browser, set the viewport to 1600×900, and capture one screenshot. Verify all of the following from the screenshot:

- All seven nodes and six relationships are visible without scrolling.
- The two focal nodes are visually dominant but do not overpower the title.
- No connector crosses a node, label mask, or another connector.
- Every connector label is readable and separated from its line.
- Chinese text does not wrap into awkward single-character columns.
- The bottom legend remains inside the SVG and does not collide with the foundation strip.

- [ ] **Step 5: Fix only observed defects and repeat Steps 1–4**

Use `apply_patch` for targeted HTML/SVG edits. Do not add nodes, connectors, colors, cards, animation, or technical detail while fixing layout defects.

- [ ] **Step 6: Commit verification fixes if the file changed**

```powershell
git add -- 'docs/diagrams/crm-management-architecture.html'
git diff --cached --check
git commit -m "fix: polish CRM architecture diagram geometry"
```

If no file change was required after visual verification, do not create an empty commit.
