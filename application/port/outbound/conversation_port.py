from abc import ABC, abstractmethod
from application.domain.conversation import Conversation, DialogSegment
from typing import List, Optional, Any

class ConversationPort(ABC):

    @abstractmethod
    def conversation_save(self, conversation: Conversation) -> Conversation:
        """保存会话"""
        pass

    @abstractmethod
    def conversation_add(self, dialog_segment: DialogSegment) -> DialogSegment:
        """增加对话片段"""
        pass

    @abstractmethod
    def conversation_insert(self, dialog_segment: DialogSegment, index: int) -> DialogSegment:
        """插入对话片段"""
        pass

    @abstractmethod
    def dialog_segment_remove(self, conversation_id: str, dialog_segment_id: str) -> str:
        """删除对话片段"""
        pass

    @abstractmethod
    def dialog_segment_find(self, conversation_id: str, dialog_segment_id) -> Optional[DialogSegment]:
        """
        查找对话片段
        :param conversation_id:
        :param dialog_segment_id:
        :return:
        """

    @abstractmethod
    def update_conversation_record(self, conversation_id: str, updated_segments: List[DialogSegment]):
        pass

    @abstractmethod
    def load_agent_record(self, agent_instance_id: str) -> List[DialogSegment]:
        pass

    @abstractmethod
    def update_agent_record(self, agent_instance_id: str, updated_segments: List[DialogSegment]):
        pass

    @abstractmethod
    def add_agent_record(self, dialog_segment: DialogSegment) -> DialogSegment:
        pass

    @abstractmethod
    def conversation_load(self, conversation_id: str) -> Conversation:
        """获取会话"""
        pass

    @abstractmethod
    def conversation_load_list(self) -> List[Conversation]:
        """获取会话列表"""
        pass

    @abstractmethod
    def conversation_update(self, conversation: Conversation) -> Optional[Conversation]:
        """
        更新会话
        :param conversation: 会话对象
        :return: 会话对象
        """

    @abstractmethod
    def conversation_remove(self, conversation_id: str) -> str:
        """
        删除会话
        :param conversation_id: 会话id
        :return:
        """