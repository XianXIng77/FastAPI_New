from fastapi import APIRouter, HTTPException, Response, status

from api.deps import AccessTokenIdentityDep, CurrentUserDep, SessionDep
from core.config import settings
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, RegisteredUser, TokenPair
from schemas.response import ApiResponse
from services import auth as auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, session: SessionDep) -> ApiResponse[RegisteredUser]:
    """注册邮箱账号，只返回公开的账号信息。"""
    try:
        user = await auth_service.register(session, data)
    except auth_service.AccountAlreadyExists as error:
        raise HTTPException(status_code=409, detail="邮箱或用户名已被使用") from error
    return ApiResponse[RegisteredUser].success(RegisteredUser.model_validate(user), msg="注册成功")


@router.post("/login")
async def login(data: LoginRequest, session: SessionDep, response: Response) -> ApiResponse[TokenPair]:
    """校验邮箱和密码，登录成功后签发一对令牌。"""
    secret_key = settings.jwt_secret_key
    if secret_key is None:
        raise HTTPException(status_code=503, detail="登录服务尚未配置")
    try:
        tokens = await auth_service.login(session, data, secret_key)
    except auth_service.InvalidCredentials as error:
        raise HTTPException(
            status_code=401, detail="邮箱或密码错误", headers={"WWW-Authenticate": "Bearer"}
        ) from error
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse[TokenPair].success(tokens, msg="登录成功")


@router.post("/refresh", responses={401: {"description": "刷新令牌或会话不可用"}})
async def refresh(data: RefreshRequest, session: SessionDep, response: Response) -> ApiResponse[TokenPair]:
    """用仍有效的刷新令牌换取新的一对令牌，无需 Access Token。"""
    secret_key = settings.jwt_secret_key
    if secret_key is None:
        raise HTTPException(status_code=503, detail="登录服务尚未配置")
    try:
        tokens = await auth_service.refresh(session, data.refresh_token.get_secret_value(), secret_key)
    except auth_service.InvalidRefreshToken as error:
        raise HTTPException(status_code=401, detail="刷新令牌无效，请重新登录") from error
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse[TokenPair].success(tokens, msg="刷新成功")


@router.post("/logout", responses={401: {"description": "缺少有效的访问令牌"}})
async def logout(identity: AccessTokenIdentityDep, session: SessionDep) -> ApiResponse[None]:
    """用 Access Token 撤销当前会话，无需请求体。"""
    user_id, session_id = identity
    await auth_service.logout(session, user_id=user_id, session_id=session_id)
    return ApiResponse[None].success(msg="退出成功")


@router.get("/me", responses={401: {"description": "访问令牌无效或会话不可用"}})
async def get_me(current_user: CurrentUserDep, response: Response) -> ApiResponse[RegisteredUser]:
    """返回当前登录用户的公开资料。"""
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse[RegisteredUser].success(RegisteredUser.model_validate(current_user))
