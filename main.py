from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from core.exception_handlers import request_validation_exception_handler
from db.session import async_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 数据库建表交给 Alembic；应用退出时关闭数据库连接池。
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(title="FastAPI 学习项目", lifespan=lifespan)

# 请求校验失败时隐藏原始输入，保留 FastAPI 的 422/detail 响应结构。
app.add_exception_handler(
    RequestValidationError,
    request_validation_exception_handler,
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.middleware("http")
async def middleware(request: Request, call_next):
    print("中间件 start")
    response = await call_next(request)
    print("中间件 end")
    return response
