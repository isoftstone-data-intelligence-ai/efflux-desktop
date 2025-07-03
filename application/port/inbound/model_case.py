from abc import ABC, abstractmethod
from application.domain.generators.generator import LLMGenerator
from application.domain.generators.firm import GeneratorFirm
from typing import List, Optional

class ModelCase(ABC):

    @abstractmethod
    async def firm_list(self) -> List[GeneratorFirm]:
        """
        获取所有模型厂商
        :return:
        """

    @abstractmethod
    async def model_list(self, firm: str) -> List[LLMGenerator]:
        """
        获取所有指定厂商项目支持的模型列表
        :param firm: 厂商名
        :return: 模型列表对象
        """

    @abstractmethod
    async def enabled_model_list(self, firm: str) -> List[LLMGenerator]:
        """
        获取所有指定模型厂商已启用的模型列表
        :param firm: 厂商名
        :return: 模型对象列表
        """

    @abstractmethod
    async def enable_or_disable_model(self, firm: str, model: str, enabled: bool, model_type: str) -> Optional[bool]:
        """
        启用或禁用模型
        :param firm: 厂商名
        :param model: 模型名
        :param enabled: 是否启用
        :return: 操作结果
        """