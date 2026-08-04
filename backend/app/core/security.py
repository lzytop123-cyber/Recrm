"""
安全相关工具：密码哈希、JWT 签发与校验。
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# bcrypt 加盐哈希；固定 bcrypt 4.0.1 以避免 passlib 兼容问题
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """明文密码 -> bcrypt 哈希。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | int,
    extra_claims: Optional[dict[str, Any]] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    """签发 JWT access token。sub 一般为用户 id。"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """解析并校验 JWT，失败抛 JWTError。"""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


class TokenError(Exception):
    """Token 无效或已过期。"""

    pass


def get_subject_from_token(token: str) -> str:
    """从 token 取出 sub（用户 id 字符串）。"""
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise TokenError("token missing subject")
        return str(subject)
    except JWTError as exc:
        raise TokenError("invalid token") from exc
