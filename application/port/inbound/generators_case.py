from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from application.domain.conversation import DialogSegmentContent

class GeneratorsCase(ABC):

    @abstractmethod
    async def generate_stream(self,
        client_id: str,
        generator_id: str,
        query: Optional[str | List[DialogSegmentContent]],
        system: str,
        conversation_id: str,
        mcp_name_list: Optional[List[str]] = None,
        agent_name: Optional[str] = None,
        tools_group_name_list: Optional[List[str]] = None,
        task_confirm: Optional[Dict[str, Any]] = None,
        artifacts: Optional[bool] = False
    ) -> tuple[str | None, str, str]:
        """
        ppt生成交互
        :param client_id: ws id
        :param generator_id: 生成模型id
        :param query: 用户消息
        :param system: 系统提示词
        :param conversation_id: 会话id
        :param mcp_name_list: mcp名列表
        :param agent_name: agent名
        :param task_confirm: 任务确认
        :param tools_group_name_list
        :return:
        """

    @abstractmethod
    async def stop_generate(
        self,
        client_id: str,
        conversation_id: str,
    ) -> str:
        """
        停止生成
        :param client_id: ws id
        :param conversation_id:
        :return:
        """

    @abstractmethod
    async def confirm(
            self,
            client_id: str,
            generator_id: str,
            conversation_id: str,
            agent_instance_id: str,
            dialog_segment_id: str,
            confirm_type: str,
            content: Dict[str, str],
    ) -> Optional[str]:
        """
        停止生成
        :param client_id: ws id
        :param generator_id: llm id
        :param conversation_id: 会话id
        :param agent_instance_id: agent_instance_id
        :param dialog_segment_id: 对话片段id
        :param confirm_type: 确认类型
        :param content: 待确认数据
        :return:
        """


    @abstractmethod
    async def generate(self,
        generator_id: str,
        query: str,
        conversation_id: str,
        mcp_name_list: Optional[List[str]] = None,
        tools_group_name_list: Optional[List[str]] = None,
        task_confirm: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        ppt生成交互
        :param generator_id: 生成模型id
        :param query: 用户消息
        :param conversation_id: 会话id
        :param mcp_name_list: mcp名列表
        :param task_confirm: 任务确认
        :return:
        """

    @abstractmethod
    async def generate_test(self,
        generator_id: str,
        query: str,
        conversation_id: str,
        mcp_name_list: List[str],
        tools_group_name_list: Optional[List[str]] = None,
        task_confirm: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        ppt生成交互
        :param generator_id: 生成模型id
        :param query: 用户消息
        :param conversation_id: 会话id
        :param mcp_name_list: mcp名列表
        :param task_confirm: 任务确认
        :return:
        """
