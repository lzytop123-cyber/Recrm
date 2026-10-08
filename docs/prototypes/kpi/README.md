# 七类考核原型

**当前入口：日常简版。** 用浏览器打开 `docs/prototypes/kpi/frontend.html`，同目录保留 `frontend-flow.css`、`frontend-flow.js` 和 `frontend-simple.js`。
流程为：发起考核（可多部门）→ 员工各自提交 → 各部门主管并行评分 → 结果确认 → 已完成。HR可勾选增加结果复核。支持多部门批次与多人独立推进；默认预置市场 / 运维 / 内容三个已发布模板，可在本页一次勾选批量发起。不请求后端，未改Vue工程。

发起考核已改为页内三步工作台：多选已发布模板 → 按部门核对匹配人员 → 设置截止日期并批量发起。每个模板生成独立批次；自动匹配默认勾选；排除或手动纳入必须填写原因；重复考核为阻断项。人员匹配逻辑在 `personnel-matching.js`。

**模板管理已经可交互：** 新建/复制模板 → 配置基本信息和指标 → 自动校验与试算 → 业务负责人审核/退回 → HR发布 → 发起考核勾选。只有已发布模板可用于新考核；已发布模板修改时必须复制新版本。模板状态机位于 `template-workflow.js`，前端页面与接口建议见 `前端交付说明.md`。

**新版本使用说明与验证范围：** 见 `frontend-优化说明.md`。原型进度保存在本机浏览器（`kpi-flow-simple-v5`），可从左侧“重新演示”重置。

首次打开简版会接续旧版已发起的张明考核，保留材料、评分和旧版HR复核要求；尚未发起则进入一页发起。简版保存到独立缓存，旧版缓存不删除。要完整体验默认四步和多人发起，可点左侧“重新演示”（会清除简版演示进度，操作前有确认）。

原13步页面保留为 `frontend-reference.html`，只用于旧版专项与模板参考，不作为日常主流程。模板规则首次使用或变更时确认；本简版预置已确认的合成演示模板，其他正式草稿不自动批准。周期和岗位固定为9月市场部演示，未模拟任意组织与周期管理。

新增验证：`node docs/prototypes/kpi/frontend-simple.test.cjs`、`node docs/prototypes/kpi/frontend-simple.smoke.cjs`、`node docs/prototypes/kpi/template-workflow.test.cjs`，覆盖多人隔离、一次提交、主管退回、可选复核、申诉、自动完成、缓存接续，以及模板创建、配置、校验、审核、发布、版本复制和发起选择。并保留原3套回归检查；本地 file:// 页面受浏览器自动化安全策略限制，未完成浏览器视觉验收。

**原Cursor版本备份：** `frontend-before-optimization.html`。下面的规则画板、选型页和已有PNG仍属于原版本，未随本次流程优化重新生成，不能作为新版页面截图。

**页面选型说明：** `docs/prototypes/kpi/选型.html`。  
**规则走查画板（不套 CRM 壳）：** `docs/prototypes/kpi/index.html`（`#p01`–`#p12`）。

## 源文件 → 模板

| 源文件 | 模板 |
|---|---|
| 市场部.xlsx | MARKET_MONTHLY |
| AI技术运维考核表.xlsx | AI_OPS_MONTHLY |
| 内容制作团队考核表.xlsx | CONTENT_MONTHLY |
| 品宣团队考核表.xlsx | BRAND_MONTHLY |
| 直播绩效考核表.xlsx | LIVE_HOST_MONTHLY、LIVE_ADS_MONTHLY |
| 培训部.docx | ONBOARD_SALES/FUNCTION × D5/M1/M3（6个） |
| 讲师考核制度.docx + 配套文表.docx | LECTURER_MONTHLY + 反馈/观察期表单 |

共 **13 个模板草稿**。规则编辑页（p02）可切换市场/运维/内容/品宣/主播/投手/讲师查看原表指标。

## 与现有系统的对应

| 原型页 | 现有前端参考 | 关键状态 | 接口 |
|---|---|---|---|
| 01 模板与版本 | `/performance/admin/templates` | 草稿、待确认、审批中、冲突 | `POST /templates/{id}/validate` |
| 02 规则编辑 | `PerformanceTemplateEditView` | 110≠100、提交禁用 | `POST /templates/{id}/revise` |
| 03 规则试算 | （新） | 客资覆盖、缺失不算0 | `POST /templates/{id}/preview` |
| 04 周期分配 | 周期生成扩展 | 未分配、同优先级冲突 | `GET/POST /template-assignments` |
| 05 数据台账 | （新） | 待审核、已确认、已更正 | `GET /metric-facts` |
| 06 导入预览 | （新） | 未知员工、整批不写 | `POST /imports/preview` |
| 07 我的绩效 | `/performance/mine` | 月度与入职并存 | `POST /assessments/{id}/confirm` |
| 08 评分明细 | `PerformanceScoringView` | 改分理由、旧确认失效 | `POST /assessments/{id}/refresh-data` |
| 09 入职阶段 | （新） | D5/M1/M3，不发工资 | `POST /stage-cases` |
| 10 讲师反馈 | （新） | 匿名、评差计数、加减分 | `GET/POST /feedback-records` |
| 11 观察期 | （新） | 再次触发不解除、改薪走HR | `POST /observation-cases` |
| 12 归档薪酬 | 周期归档 | 禁5000兜底、造假不合格 | `POST /assessments/{id}/archive` |

路径均在 `/api/v1/performance` 下。字段说明见 `docs/work-reports/KPI七类接入-后端接口对接说明.md`。

## 截图

| 图片 | 页面 |
|---|---|
| 01-template-list.png | 模板与版本 |
| 02-template-editor.png | 规则编辑（默认 AI 运维冲突态） |
| 03-score-preview.png | 规则试算 |
| 04-cycle-assignment.png | 周期分配 |
| 05-metric-ledger.png | 数据台账 |
| 06-import-preview.png | 导入预览 |
| 07-my-performance.png | 我的绩效 |
| 08-scoring-detail.png | 评分明细 |
| 09-onboarding.png | 入职阶段 |
| 10-lecturer-feedback.png | 讲师反馈 |
| 11-observation.png | 观察期 |
| 12-result-archive.png | 归档薪酬 |

和现有前端的差别：这些页面只在本目录，没有接到 Vue 工程。周期按分配批量生成、外部平台取数、工资批次入账仍未做。
# 补材料清单更新

员工打开“补充缺少的材料”即可看到具体客户、已有资料、缺失原因、补充要求和处理入口。初始样例为9条线索：6条系统已带入，3条需要补充行业、需求或沟通依据。支持逐条保存草稿，全部补齐后统一提交；HR可以指定一条退回并写明要求，其余材料保留待核实。

仍使用原有本地进度，不需要重置。旧版已提交或已审核的汇总材料继续保留，标注为“旧版汇总材料”，不凭空生成逐客户明细。新一轮演示使用9条明细清单。只有保存过的草稿会在刷新后保留。此处仍为独立合成原型，不上传真实附件。

验证：运行 `node docs/prototypes/kpi/frontend-flow.test.cjs`、`node docs/prototypes/kpi/frontend-flow.smoke.cjs`、`node docs/prototypes/kpi/evidence-checklist.test.cjs`。页面生成检查不是浏览器视觉验收。
