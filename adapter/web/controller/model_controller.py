from fastapi import APIRouter, Depends
from common.core.logger import get_logger
from common.core.container.container import get_container
from application.port.inbound.model_case import ModelCase
from adapter.web.vo.base_response import BaseResponse
from typing import Optional
logger = get_logger(__name__)

router = APIRouter(prefix="/api/model", tags=["Model"])

def get_model_case() -> ModelCase:
    return get_container().get(ModelCase)

@router.get("/firm/list")
async def firm_list(model_case: ModelCase = Depends(get_model_case)):
    return BaseResponse.from_success(data=await model_case.firm_list())

@router.get("/model/list")
async def model_list(firm: str, model_case: ModelCase = Depends(get_model_case)):
    return BaseResponse.from_success(data=await model_case.model_list(firm))

@router.get("/enabled_model/list")
async def enabled_model_list(firm: Optional[str] = None, model_case: ModelCase = Depends(get_model_case)):
    return BaseResponse.from_success(data=await model_case.enabled_model_list(firm))

@router.put("/model/enable")
async def enable_model(
    firm: str,
    model: str,
    enabled: bool,
    model_type: Optional[str] = None,
    model_case: ModelCase = Depends(get_model_case)
):
    return BaseResponse.from_success(
        data=await model_case.enable_or_disable_model(
            firm=firm,
            model=model,
            enabled=enabled,
            model_type=model_type
        )
    )