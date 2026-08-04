# CRM + OKR 公司管理系统（项目骨架）

公司内部经营管理系统骨架：覆盖「线索 → 客户 → 合同 → 回款 → 项目交付 → OKR/工时/考核」链路。

本期目标：**可运行的前后端骨架**（登录 + JWT + RBAC + 核心表 + 主框架布局），业务功能后续按模块填充。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Vue Router + Pinia + Axios |
| 后端 | Python + FastAPI + SQLAlchemy + Pydantic |
| 数据库 | 开发期 SQLite，生产可切 PostgreSQL（改 `DATABASE_URL`） |
| 鉴权 | JWT + RBAC（公司 / 部门 / 个人 三级数据范围）；支持账号密码与飞书 OAuth 登录 |
| 迁移 | Alembic |

## 目录结构

```
crm-okr-system/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # 路由（v1/auth 等）
│   │   ├── core/            # 安全、RBAC
│   │   ├── models/          # ORM 模型
│   │   ├── schemas/         # Pydantic 模型
│   │   ├── services/        # 业务服务
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   └── seed.py          # 初始化角色/权限/管理员
│   ├── alembic/             # 数据库迁移
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # Vue3 前端
│   └── src/
│       ├── api/             # Axios 封装与接口
│       ├── layouts/         # 主框架（侧栏+顶栏+内容区）
│       ├── router/          # 路由与登录守卫
│       ├── stores/          # Pinia
│       └── views/           # 页面
└── README.md
```

## 环境要求

- Python 3.11+（推荐 3.12）
- Node.js 18+（推荐 LTS）
- Git（用于 `git init`；若未安装可用 `winget install Git.Git`）

## 一、后端启动

在 PowerShell / 终端中执行：

```powershell
cd backend

# 1) 创建虚拟环境并激活
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) 安装依赖
pip install -r requirements.txt

# 3) 配置环境变量（首次）
copy .env.example .env

# 4) 数据库迁移（首次已提供 init 迁移，直接 upgrade 即可）
alembic upgrade head

# 5) 初始化角色、权限、管理员账号
python -m app.seed

# 6) 启动 API（热重载）
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> 后续改模型时再执行：`alembic revision --autogenerate -m "your message"` → `alembic upgrade head`

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

**默认管理员**

| 用户名 | 密码 |
|--------|------|
| admin  | admin123 |

> 生产环境请务必修改 `.env` 中的 `SECRET_KEY`，并更换管理员密码。

### 飞书登录（可选）

1. 在 [飞书开放平台](https://open.feishu.cn/app) 创建企业自建应用，拿到 App ID / App Secret。
2. 「安全设置」添加重定向 URL：`http://127.0.0.1:5173/login/feishu/callback`（生产改为实际域名）。
3. 开通并申请用户身份相关权限（如获取用户基本信息），按控制台要求发布/可用性配置。
4. 在 `backend/.env` 增加：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_REDIRECT_URI=http://127.0.0.1:5173/login/feishu/callback
FEISHU_AUTO_PROVISION=false
```

5. 在「组织员工」编辑用户，填写该员工的飞书 `open_id`（或保证系统邮箱与飞书邮箱一致以便首次自动绑定）。
6. 重启后端，登录页出现「飞书登录」按钮。

> `FEISHU_AUTO_PROVISION=true` 时，未绑定用户会自动建「普通员工」账号，仅建议开发联调使用。

**飞书通讯录同步**

1. 在飞书应用开通通讯录只读权限（如「获取通讯录基本信息」「以应用身份读取通讯录」）。
2. **数据权限 → 通讯录权限范围**：若同步从根部门 `0` 开始，必须设为 **全部成员**；若只能开放指定部门，在 `.env` 设置 `FEISHU_CONTACT_ROOT_DEPARTMENT_ID=<该部门 open_department_id>`。改完后需**创建版本并发布**。
3. 使用有「组织员工」权限的账号登录系统 → **组织员工** → **同步飞书通讯录**。
4. 同步规则：部门写入 `code=FS_{open_department_id}`；员工按 `open_id` → 邮箱 → 手机匹配；新建员工默认「普通员工」角色、随机不可知密码（走飞书登录）。

## 二、前端启动

另开一个终端：

```powershell
cd frontend

# 若提示找不到 npm，用下面任一方式：
# 方式 A（推荐）：双击或运行启动脚本
.\start-dev.ps1

# 方式 B：先补 PATH 再启动
$env:Path = "C:\Users\Administrator\AppData\Local\nvm\v22.16.0;" + $env:Path
npm install
npm run dev
```

> Cursor 已配置项目级终端 PATH（`.vscode/settings.json`）。若仍提示找不到 `npm`，请关掉旧终端，再开一个新终端。

浏览器打开：http://127.0.0.1:5173

开发期 Vite 已将 `/api` 代理到 `http://127.0.0.1:8000`，一般无需单独配 CORS。

**同一局域网同事访问：** 前端已监听 `0.0.0.0`，同事请用你电脑的局域网 IP，例如 `http://192.168.x.x:5173`（不要用 `127.0.0.1`）。后端需在本机保持运行；若打不开，检查 Windows 防火墙是否放行 5173 端口。

## 三、验证完整登录链路

1. 先启动后端，再启动前端
2. 打开 http://127.0.0.1:5173 ，应跳转到登录页
3. 使用 `admin` / `admin123` 登录
4. 登录成功后进入首页看板，左侧菜单按管理员权限展示
5. 也可在 http://127.0.0.1:8000/docs 用 `POST /api/v1/auth/login` 或 OAuth2 Authorize 验证

## 四、已落地的核心数据表

- 组织：`departments`
- 用户：`users`（含预留字段 `feishu_open_id`，二期再接飞书）
- RBAC：`roles`、`permissions`、`user_roles`、`role_permissions`
- 售前：`leads`、`lead_follow_ups`、`lead_logs`、`customers`、`contracts`、`payments`
- 审计：`audit_logs`

预置角色：系统管理员、管理层、中层管理、普通员工、销售、交付负责人、运营、开发、讲师主播、财务。

### 线索池（第一期已实现）

对齐《子系统设计-线索池》主干能力：

- 录入（手机号强去重，可 force 强制）
- 列表（全部/我的/公海/我录入）+ 顶部统计
- 公海领取、退回、写跟进、转化为客户、标记流失
- 跟进时间线 + 操作日志
- 默认规则：保护期 **15 天**，退回冷静期 **24 小时**（`.env` 可改 `LEAD_PROTECT_DAYS` / `LEAD_RETURN_COOLDOWN_HOURS`）

升级数据库后请执行：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
python -m app.seed
```

> 若迁移失败（旧库结构冲突），开发期可删除 `backend/app.db` 后重新 `alembic upgrade head` + `seed`。

## 五、生产切换 PostgreSQL

1. 安装驱动（已在 `requirements.txt`）：`pip install "psycopg[binary]>=3.2,<4"`
2. 修改 `backend/.env`：

```env
DATABASE_URL=postgresql+psycopg://postgres:your_password@127.0.0.1:5432/crm_okr
```

3. 空库建表后，可从现有 SQLite 迁数据（保留主键与业务数据）：

```powershell
alembic upgrade head
python -m app.db_migration.cli migrate --source-url "sqlite:///./app.db" --target-url "postgresql+psycopg://postgres:your_password@127.0.0.1:5432/crm_okr" --report "migration-reports/cutover.json"
```

若是全新环境无历史数据，也可直接：

```powershell
alembic upgrade head
python -m app.seed
```

## 六、本期明确不做

- 移动端 / 响应式
- 飞书扫码登录（仅预留字段）
- AI 知识库
- OKR / 工单 / 排期的具体业务逻辑（表与菜单已占位，待需求定稿再实现）

## 七、后续加模块建议

1. 在 `backend/app/models/` 新增模型，并 `alembic revision --autogenerate`
2. 在 `backend/app/api/v1/` 增加路由，并挂到 `api_router`
3. 在 `frontend/src/views/` 写页面，在 `router/index.ts` 注册
4. 如需菜单可见性，在 `backend/app/services/menu.py` 的 `MENU_CATALOG` 与 seed 权限中补充
