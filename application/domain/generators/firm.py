from pydantic import BaseModel, model_validator

from common.utils.common_utils import create_uuid
from common.utils.auth import ApiKeySecret, Secret
from typing import Optional, Any, Self, List


class GeneratorFirm(BaseModel):

    id: str
    name: str
    model_list: Optional[List[str]] = None
    base_url:Optional[str] = None
    api_key: Optional[ApiKeySecret] = None
    fields: Optional[dict] = {}

    @classmethod
    def from_init(cls, name: str, base_url: str, model_list: Optional[List[str]] = None) -> "GeneratorFirm":
        return GeneratorFirm(id=create_uuid(), name=name, base_url=base_url, model_list=model_list)

    @classmethod
    def from_set_firm(cls, name: str, base_url: str, api_key: str) -> "GeneratorFirm":
        return GeneratorFirm(id=create_uuid(), name=name, base_url=base_url, api_key=Secret.from_api_key(api_key))

    @classmethod
    def from_default(cls, name: str) -> "GeneratorFirm":
        return GeneratorFirm(id=create_uuid(), name=name, base_url="", model_list=[])

    @classmethod
    def from_other(cls, **kwargs) -> "GeneratorFirm":
        return GeneratorFirm(id=create_uuid(), base_url="", model_list=[], **kwargs)

    # 自定义处理模型转化为字典的方法
    def model_dump(self, **kwargs):
        # 使用 super() 获取字典格式
        data = super().model_dump()

        # 转换 api_key 字段为字符串
        data['api_key'] = self.api_key.resolve_value() if self.api_key else None
        return data

    # 在模型验证过程中转换字段
    @classmethod
    def model_validate(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:

        obj['api_key'] = Secret.from_api_key(obj['api_key']) if obj['api_key'] else None
        return cls(**obj)