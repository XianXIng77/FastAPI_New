"""业务接口可复用的 JSON 响应结构。"""

from typing import Generic, Self, TypeVar

from pydantic import BaseModel


ResponseData = TypeVar("ResponseData")


class ApiResponse(BaseModel, Generic[ResponseData]):
    """统一业务响应；code 是业务码，不会改变 HTTP 状态码。"""

    code: int = 200
    msg: str = "操作成功"
    data: ResponseData | None = None

    @classmethod
    def success(cls, data: ResponseData | None = None, *, msg: str = "操作成功") -> Self:
        """构造带数据或不带数据的成功响应。"""
        return cls(data=data, msg=msg)
