"""统一处理请求校验错误和 Redis 服务异常。"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """保留字段位置、错误类型和说明，不包含 input、请求体等敏感值。"""
    details = [
        {"loc": error["loc"], "type": error["type"], "msg": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": details},
    )


async def redis_exception_handler(request: Request, exc: RedisError) -> JSONResponse:
    """Redis 不可用时明确拒绝请求，不暴露连接错误中的敏感信息。"""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Redis 服务暂不可用"},
    )
