from application.domain.generators.firm import GeneratorFirm
from application.port.outbound.user_setting_port import UserSettingPort
from common.core.container.annotate import component
from typing import Dict, Any, List, Optional
from common.utils.json_file_util import JSONFileUtil
from common.utils.yaml_util import load_yaml

@component
class UserSettingAdapter(UserSettingPort):

    user_setting_file_url = "user_setting.json"

    def __init__(self, ):
        self.config: Dict[str, Any] = load_yaml('adapter/model_sdk/setting/openai/model.yaml')

    def load_firm_setting(self, firm_name: str) -> Optional[GeneratorFirm]:
        user_setting = JSONFileUtil(self.user_setting_file_url)
        firm_setting = user_setting.read_key(firm_name)
        if firm_setting:
            return GeneratorFirm.model_validate(firm_setting)

    def set_firm_setting(self, generator_firm: GeneratorFirm) -> bool:
        user_setting = JSONFileUtil(self.user_setting_file_url)
        if not generator_firm.base_url and generator_firm.api_key:
            generator_firm.base_url = self.config[generator_firm.name]['base_url']
        user_setting.update_key(generator_firm.name, generator_firm.model_dump())
        return True

    def load_firm_setting_list(self) -> List[GeneratorFirm]:
        user_setting = JSONFileUtil(self.user_setting_file_url)
        firm_setting_list: List[GeneratorFirm] = []
        # 遍历项目内置支持的所有厂商
        for firm in self.config.keys():
            firm_setting = user_setting.read_key(firm)
            if firm_setting:
                firm_setting_list.append(GeneratorFirm.model_validate(firm_setting))
            else:
                firm_setting_list.append(GeneratorFirm.from_default(name=firm))
        return firm_setting_list

