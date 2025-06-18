from fastapi import APIRouter, Depends, Query
from common.core.logger import get_logger
from common.core.container.container import get_container
from application.port.inbound.vector_model_case import VectorModelCase
from adapter.web.vo.base_response import BaseResponse
# 新增导入VO类
from adapter.web.vo.vector_model_vo import CreateVectorModelRequest, DeleteVectorModelRequest  # 从VO目录导入请求模型

logger = get_logger(__name__)

router = APIRouter(prefix="/api/vector_model", tags=["Vector Model"])  # 路由前缀和标签

# 依赖注入：获取业务用例实例（与 model_controller.py 形式一致）
def get_vector_model_case() -> VectorModelCase:
    return get_container().get(VectorModelCase)

@router.get("/list")
async def vector_model_list(vector_case: VectorModelCase = Depends(get_vector_model_case)):
    """获取向量模型列表"""
    return BaseResponse.from_success(data=await vector_case.list())

@router.post("")
async def add_vector_model(
    req: CreateVectorModelRequest,
    vector_case: VectorModelCase = Depends(get_vector_model_case)
):
    """新增向量模型（含厂商、模型名、API Key、基础URL）"""
    await vector_case.add(
        firm=req.firm,
        model=req.model,
        api_key=req.api_key,
        base_url=req.base_url
    )
    return BaseResponse.from_success()

@router.delete("")
async def delete_vector_model(
    req: DeleteVectorModelRequest,  # 请求体参数（pydantic 自动校验）
    vector_case: VectorModelCase = Depends(get_vector_model_case)  # 依赖注入保持不变
):
    """删除指定向量模型（通过请求体中的model_id标识）"""
    await vector_case.delete(id=req.id)  # 从请求体对象中获取id
    return BaseResponse.from_success()  # 返回格式保持不变