"""
应用配置：通过环境变量 / .env 加载。
开发期默认 SQLite，生产改为 PostgreSQL 只需改 DATABASE_URL。
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CRM-OKR System"
    debug: bool = True
    # SQLAlchemy echo：默认关闭。开启后每条 SQL 打日志，经营总览等聚合接口会明显变慢
    sql_echo: bool = False
    # JWT 签名密钥，生产环境务必更换
    secret_key: str = "dev-secret-key-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 默认 24 小时

    # SQLAlchemy 连接串；sqlite 用相对路径，postgres 示例见 .env.example
    database_url: str = "sqlite:///./app.db"

    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # 线索池规则（文档待确认项的默认值，可在 .env 覆盖）
    lead_protect_days: int = 15  # 分配后保护期天数
    lead_return_cooldown_hours: int = 24  # 退回公海冷静期（小时）
    lead_daily_claim_limit: int = 20  # 每人每日公海抢领上限
    lead_protect_hold_limit: int = 100  # 每人同时持有「保护中」线索上限

    # 飞书网页应用登录（开放平台「凭证与基础信息」+「安全设置-重定向 URL」）
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    # 必须与飞书后台配置一致，通常指向前端回调页
    feishu_redirect_uri: str = "http://127.0.0.1:5173/login/feishu/callback"
    feishu_authorize_url: str = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
    feishu_token_url: str = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
    feishu_user_info_url: str = "https://open.feishu.cn/open-apis/authen/v1/user_info"
    # 登录所需 scope；可按开放平台权限申请结果调整
    feishu_scope: str = "contact:user.base:readonly"
    # 未绑定 open_id 的飞书用户是否自动建号（正式环境建议 false，由组织模块建账号后绑定）
    feishu_auto_provision: bool = False
    # 通讯录同步起始部门 open_department_id；查根部门 0 要求权限范围为「全部成员」
    feishu_contact_root_department_id: str = "0"

    # DeepSeek 云 API（OpenAI 兼容）；LLM_API_KEY 为空则知识库走检索拼接回退
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 45

    @property
    def feishu_enabled(self) -> bool:
        return bool(self.feishu_app_id and self.feishu_app_secret and self.feishu_redirect_uri)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
