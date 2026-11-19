"""密码哈希、令牌生成和 JWT 签发与校验。"""

from datetime import datetime
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash
from pydantic import SecretStr
from starlette.concurrency import run_in_threadpool


JWT_ALGORITHM = "HS256"
JWT_ISSUER = "fastapi-new"
JWT_AUDIENCE = "fastapi-new-api"

_password_hasher = PasswordHash.recommended()
_dummy_password_hash = _password_hasher.hash(token_urlsafe(32))


class InvalidAccessToken(Exception):
    """访问令牌无效或过期。"""


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_password_hasher.hash, password)


async def verify_password(password: str, password_hash: str | None) -> bool:
    return await run_in_threadpool(_password_hasher.verify, password, password_hash or _dummy_password_hash)


def create_access_token(
    user_id: UUID,
    session_id: UUID,
    *,
    secret_key: SecretStr,
    issued_at: datetime,
    expires_at: datetime,
) -> str:
    """签发只用于访问业务接口的 JWT，绑定用户和当前会话。"""
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "jti": str(uuid4()),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": issued_at,
            "exp": expires_at,
            "token_use": "access",
        },
        secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str, secret_key: SecretStr) -> tuple[UUID, UUID]:
    """校验访问令牌并取出用户 ID、会话 ID。"""
    try:
        claims = jwt.decode(
            token,
            secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["sub", "sid", "iss", "aud", "iat", "exp", "token_use"]},
        )
    except jwt.InvalidTokenError as error:
        raise InvalidAccessToken from error

    user_id = claims["sub"]
    session_id = claims["sid"]
    if claims["token_use"] != "access" or not isinstance(user_id, str) or not isinstance(session_id, str):
        raise InvalidAccessToken
    try:
        return UUID(user_id), UUID(session_id)
    except ValueError as error:
        raise InvalidAccessToken from error


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token() -> tuple[str, str]:
    """返回给客户端的原始令牌及用于入库的摘要。"""
    token = token_urlsafe(32)
    return token, hash_refresh_token(token)
