from pydantic import BaseModel

from typing import Optional
from application.domain.generators.firm import GeneratorFirm


class GeneratorFirmResultVo(BaseModel):

    id: str
    name: str
    base_url:Optional[str] = None
    api_key: Optional[str] = None
    fields: Optional[dict] = {}

    @classmethod
    def from_generator_firm(cls, generator_firm: GeneratorFirm):
        api_key_value: str = generator_firm.api_key.resolve_value() if generator_firm.api_key else None
        return GeneratorFirmResultVo(
            id=generator_firm.id,
            name=generator_firm.name,
            base_url=generator_firm.base_url,
            api_key=api_key_value,
            fields=generator_firm.fields or {},
        )