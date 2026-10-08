# KPI、员工管理、知识库页面优化

日期：2026-09-30。使用本地 `frontend-design` 技能优化现有 Vue / Element Plus 页面。

## 视觉与布局

管理页面采用统一的蓝白配色：主色 `#1e40af`、正文 `#172b4d`、辅助文字 `#52647c`、边框 `#dce4ef`、浅色背景 `#f3f6fb`、内容白底。中文字体使用微软雅黑 / 苹方系统字体，标题、正文、辅助信息形成清晰层级。

减少页头装饰和阴影，强化导航、筛选、结果数量与主要操作。统计区域采用连贯的分隔布局，表格增加行间距，手机端将考核模板、人员和知识文档改为摘要列表。样式限定在显式标记的管理模块内。

## 页面改动

- **KPI**：补充本期、模板、往期导航；模板支持名称、部门、岗位搜索和状态筛选，“待配置”同时包含草稿与退回模板。发起页按周期、人员、截止日期分步组织，提供当前准备状态。切换周期清空旧选择并重新匹配人员；旧请求不能覆盖新周期。手动纳入被排除人员时必须填写原因；截止日期按流程严格递增，启用 HR 复核时提交相应截止时间。加载失败提供重试入口。
- **员工管理**：增加部门树搜索、筛选说明、结果数量和重置操作；合同到期统计可进入合同台账，人事办理入口更清楚。桌面编辑表单使用两列布局，手机使用一列。员工摘要卡片使用独立按钮，避免嵌套按钮导致的点击问题。
- **知识库**：文档与审核导航、目录与“全部文档”、摘要、阅读入口及操作层级更清楚。身份标签和管理操作依据实际权限显示。搜索保留最新结果，刷新保留所选目录，删除后修正无效分页。审核来源筛选使用服务端分页，首次进入加载全局待审核数量。手机端保留管理员的编辑、提交审核和删除入口。

## 验证结果

- `node --test tests/*.test.cjs tests/agent-regression.cjs`：25 项通过，0 失败。
- `npm run build -- --outDir dist-ui-review`：Vue / TypeScript 检查及生产构建通过。
- `node tests/workspaces-browser.cjs`：桌面 1440×1000、平板 820×1000、手机 390×844 全部通过；覆盖筛选和重置、阅读抽屉、模板选择、人工纳入原因、周期切换、加载失败重试、阅读者权限、审核初始总数及手机管理操作。无页面运行异常，无意外写入接口调用。
- 对上述改动进行只读代码审查；发现的统计筛选范围和审核初始数量问题已修复，并通过浏览器回归验证。

浏览器验证使用拦截的接口样例数据，未对真实业务记录、飞书或其他外部服务进行写入。真实后端权限与第三方服务联调不在本次验证结果内。构建仍提示主入口包超过 500 KB，以及依赖中 PURE 注释位置警告，构建正常完成。

## 页面预览

截图使用样例数据。以下为优化后的页面：

| 页面 | 桌面 | 手机 |
| --- | --- | --- |
| KPI 发起 | [预览](ui-optimization-20260930/kpi-launch-desktop.png) | [预览](ui-optimization-20260930/kpi-launch-mobile.png) |
| KPI 人员确认 | [预览](ui-optimization-20260930/kpi-people-desktop.png) | [预览](ui-optimization-20260930/kpi-people-mobile.png) |
| 考核模板 | [预览](ui-optimization-20260930/kpi-templates-desktop.png) | [预览](ui-optimization-20260930/kpi-templates-mobile.png) |
| 员工管理 | [预览](ui-optimization-20260930/employees-desktop.png) | [预览](ui-optimization-20260930/employees-mobile.png) |
| 知识库 | [预览](ui-optimization-20260930/knowledge-desktop.png) | [预览](ui-optimization-20260930/knowledge-mobile.png) |

浏览器回归脚本：`frontend/tests/workspaces-browser.cjs`。需要本机 Chrome 和 Playwright；可通过 `PLAYWRIGHT_PATH` 指向已安装的 Playwright 模块。
