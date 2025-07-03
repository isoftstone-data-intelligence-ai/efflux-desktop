from abc import ABC, abstractmethod
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from application.domain.generators.firm import GeneratorFirm
from application.domain.generators.generator import LLMGenerator
from application.domain.generators.tools import Tool
from typing import Iterable, Generator, Callable, List, Optional, Dict, Any

class GeneratorsPort(ABC):

    @abstractmethod
    def generate(
        self,
        llm_generator: LLMGenerator,
        messages: Iterable[ChatStreamingChunk] = None,
        tools: Iterable[Tool] = None,
        **generation_kwargs,
    ) -> ChatStreamingChunk:
        """
        同步大模型消息接口
        :param llm_generator: 生成模型对象
        :param messages: 消息集合
        :param tools: 工具数组
        :return:
        """
        pass

    @abstractmethod
    def generate_json(
        self,
        llm_generator: LLMGenerator,
        validate_json: Optional[Callable[[Dict[str, Any]], bool]] = None,
        messages: Iterable[ChatStreamingChunk] = None,
        **generation_kwargs,
    )-> Dict[str, Any] | None:
        """
        流式大模型消息返回json方法
        :param llm_generator: 生成模型对象
        :param validate_json: 验证json格式的回调方法
        :param messages: 消息集合
        :return:
        """
        pass

    @abstractmethod
    def generate_test(
        self,
        llm_generator: LLMGenerator,
        validate_json: Optional[Callable[[Dict[str, Any]], bool]] = None,
        messages: Iterable[ChatStreamingChunk] = None,
        tools: Iterable[Tool] = None,
        **generation_kwargs,
    )-> Dict[str, Any] | None:
        """
        流式大模型消息返回json方法
        :param llm_generator: 生成模型对象
        :param validate_json: 验证json格式的回调方法
        :param messages: 消息集合
        :return:
        """
        pass

    @abstractmethod
    def generate_event(
        self,
        llm_generator: LLMGenerator,
        messages: Iterable[ChatStreamingChunk] = None,
        tools:Iterable[Tool] = None,
        **generation_kwargs,
    ) -> Generator[ChatStreamingChunk, None, None]:
        """
        流式大模型消息接口
        :param llm_generator: 生成模型对象
        :param messages: 消息
        :param tools: 工具数组
        :return:
        """
        pass

    @abstractmethod
    def load_generate(self, generate_id: str) -> LLMGenerator:
        """
        获取llm生成器
        :param generate_id: 模型生成器id
        :return:
        """
    @abstractmethod
    def load_firm(self) -> List[GeneratorFirm]:
        """
        返回所有厂商及模型
        :return:
        """

    @abstractmethod
    def load_model_by_firm(self, firm_name: str) -> List[LLMGenerator]:
        """
        获取用户的指定厂商模型列表
        :param firm_name:
        :return:
        """

    @abstractmethod
    def is_non_standard(self, firm_name: str) -> bool:
        """
        是否非标准支持的大模型厂商
        :param firm_name:
        :return:
        """

    @abstractmethod
    def load_model_by_other_firm(self, firm_name: str) -> List[LLMGenerator]:
        """
        获取用户的指定非标厂商模型列表
        :param firm_name:
        :return:
        """

    @abstractmethod
    def load_enabled_model_by_firm(self, firm_name: str) -> List[LLMGenerator]:
        """
        获取用户设置启用的指定厂商模型列表
        :param firm_name:
        :return:
        """

    @abstractmethod
    def load_enabled_model(self) -> List[LLMGenerator]:
        """
        获取用户设置启用的模型列表
        :return:
        """

    @abstractmethod
    def enable_or_disable_model(
        self, firm: str, model: str, enabled: bool, model_type: str
    ) -> Optional[bool]:
        """
        启用或禁用模型
        :param firm: 厂商名
        :param model: 模型名
        :param enabled: 是否启用
        :param model_type: 模型类型
        :return: 操作结果
        """
