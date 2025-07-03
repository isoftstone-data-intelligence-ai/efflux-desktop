from pydantic import BaseModel

from common.utils.auth import ApiKeySecret, OtherSecret
from common.utils.common_utils import create_uuid
from typing import Iterable, Optional, Any, Dict
from common.core.errors.business_exception import BusinessException
from common.core.errors.business_error_code import GeneratorErrorCode

class LLMGenerator(BaseModel):

    id: str
    firm: str
    model: str
    api_key_secret: Optional[ApiKeySecret] = None
    is_enabled: Optional[bool] = None
    generators_type: Optional[str] = None
    fields: Optional[Dict[str, Any]] = None

    @classmethod
    def from_init(cls, firm: str, model: str, generators_type: str = None) -> "LLMGenerator":
        return LLMGenerator(id=create_uuid(), firm=firm, model=model, is_enabled=True, generators_type=generators_type)

    @classmethod
    def from_disabled(cls, firm: str, model: str, fields: Optional[Dict[str, Any]] = None):
        return LLMGenerator(id=create_uuid(), firm=firm, model=model, fields=fields, is_enabled=False)

    def set_api_key_secret(self, api_key_secret: ApiKeySecret | OtherSecret):
        self.api_key_secret = api_key_secret

    def check_firm_api_key(self) -> None:
        """
        验证厂商api_key
        """
        if not self.api_key_secret:
            raise BusinessException(error_code=GeneratorErrorCode.NO_APIKEY_FOUND, dynamics_message=self.firm)

    # 自定义处理模型转化为字典的方法
    def model_dump(self, **kwargs):
        # 使用 super() 获取字典格式
        data = super().model_dump()
        # 忽略字段
        if 'api_key_secret' in data:
            del data['api_key_secret']
        return data