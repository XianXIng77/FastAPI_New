from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.staticfiles import StaticFiles

from api.routes.auth import router as auth_router
from core.config import PROJECT_ROOT
from core.exception_handlers import request_validation_exception_handler
from db.session import async_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 数据库建表交给 Alembic；应用退出时关闭数据库连接池。
    try:
        yield
    finally:
        await async_engine.dispose()


app = FastAPI(title="FastAPI 学习项目", lifespan=lifespan, docs_url=None)
app.include_router(auth_router)
app.mount("/ui", StaticFiles(directory=PROJECT_ROOT / "ui", html=True), name="auth_test_ui")
app.mount(
    "/docs/assets",
    StaticFiles(directory=PROJECT_ROOT / "static" / "swagger-ui" / "5.34.1"),
    name="swagger_ui_assets",
)

# 请求校验失败时隐藏原始输入，保留 FastAPI 的 422/detail 响应结构。
app.add_exception_handler(
    RequestValidationError,
    request_validation_exception_handler,
)


@app.get("/docs", include_in_schema=False)
async def swagger_ui(request: Request):
    return get_swagger_ui_html(
        openapi_url=request.url_for("openapi").path,
        title=f"{app.title} - Swagger UI",
        swagger_js_url=request.url_for("swagger_ui_assets", path="swagger-ui-bundle.js").path,
        swagger_css_url=request.url_for("swagger_ui_assets", path="swagger-ui.css").path,
        swagger_favicon_url=request.url_for("swagger_ui_assets", path="favicon-32x32.png").path,
        oauth2_redirect_url=request.url_for("swagger_ui_oauth2_redirect").path,
        swagger_ui_parameters={"validatorUrl": None},
    )


@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def swagger_ui_oauth2_redirect():
    return get_swagger_ui_oauth2_redirect_html()
