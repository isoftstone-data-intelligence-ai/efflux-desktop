from fastapi import APIRouter, Depends, Body
from common.core.logger import get_logger
from common.core.container.container import get_container
from application.port.inbound.user_settings_case import UserSettingsCase
from application.domain.generators.firm import GeneratorFirm
from adapter.web.vo.generator_firm_vo import GeneratorFirmResultVo
from adapter.web.vo.base_response import BaseResponse
from typing import Optional, List, Dict
logger = get_logger(__name__)

router = APIRouter(prefix="/api/user_setting", tags=["USER_SETTING"])

def user_settings_case() -> UserSettingsCase:
    return get_container().get(UserSettingsCase)

@router.get("/llm_firm")
async def get_llm_firm(firm: str, user_settings_service: UserSettingsCase = Depends(user_settings_case)) -> BaseResponse:
    generator_firm: GeneratorFirm = await user_settings_service.load_firm_setting(firm)
    if generator_firm:
        generator_firm_result_vo: GeneratorFirmResultVo = GeneratorFirmResultVo.from_generator_firm(generator_firm)
        return BaseResponse.from_success(data=generator_firm_result_vo)
    else:
        return BaseResponse.from_success()

@router.put("/llm_firm")
async def set_llm_firm(firm: str, api_key: Optional[str] = None, base_url: Optional[str] = None, fields: Optional[Dict] = Body(...), user_settings_service: UserSettingsCase = Depends(user_settings_case)) -> BaseResponse:
    generator_firm: GeneratorFirm = GeneratorFirm.from_set_firm(
        name=firm, api_key=api_key, base_url=base_url, fields=fields)
    return BaseResponse.from_success(
        data=await user_settings_service.set_firm_setting(generator_firm))

@router.get("/llm_firm_list")
async def get_llm_firm_list(user_settings_service: UserSettingsCase = Depends(user_settings_case)) -> BaseResponse:
    generator_firm_result_vo_list: List[GeneratorFirmResultVo] = []
    for firm_setting in await user_settings_service.load_firm_setting_list():
        generator_firm_result_vo_list.append(GeneratorFirmResultVo.from_generator_firm(firm_setting))
    return BaseResponse.from_success(data=generator_firm_result_vo_list)
