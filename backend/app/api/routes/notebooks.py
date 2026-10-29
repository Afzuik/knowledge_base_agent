"""待实现：专题列表、创建、详情。未注册业务端点，不返回假成功。"""
from fastapi import APIRouter

router = APIRouter(prefix="/notebooks", tags=["notebooks"])
