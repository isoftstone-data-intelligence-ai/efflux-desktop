from datetime import datetime
from enum import Enum

from common.utils.common_utils import create_uuid
from common.utils.file_util import open_and_base64
from common.utils.time_utils import create_from_second_now, create_from_timestamp, create_from_timestamp_to_int
from application.domain.generators.tools import ToolInstance
from pydantic import BaseModel
from typing import Optional, List, Literal, Dict, Any
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk

class MetadataSource(Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    AGENT = "AGENT"

class MetadataType(Enum):
    MESSAGE = "MESSAGE"
    AGENT_BEGIN = "AGENT_BEGIN"
    AGENT_RESULT = "AGENT_RESULT"
    USER_CONFIRMATION = "USER_CONFIRMATION"

class DialogSegmentMetadata(BaseModel):
    source: MetadataSource
    type: MetadataType

    def model_dump(self, **kwargs):
        # 使用 super() 获取字典格式
        data = super().model_dump()
        # 转换 为字符串
        data['source'] = self.source.value if self.source else None
        data['type'] = self.type.value if self.type else None
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # 字符串转枚举
        if 'source' in obj and isinstance(obj['source'], MetadataSource):
            obj['source'] = MetadataSource(value=obj['source'])
        if 'type' in obj and isinstance(obj['type'], MetadataType):
            obj['type'] = MetadataType(value=obj['type'])
        return super().model_validate(obj)

class DialogSegmentContent(BaseModel):
    id: Optional[str] = None
    type: Literal["text", "image", "file"]
    content: str

class DialogSegment(BaseModel):
    """对话片段"""

    # 对话ID
    id: str
    # 会话ID
    conversation_id: Optional[str] = None
    # 模型
    model: Optional[str] = None
    # 内容
    content: Optional[str | List[DialogSegmentContent]] = None
    # 思考
    reasoning_content: Optional[str] = None
    # 拓展负载信息
    payload: Dict[str, Any] = None
    # 结束标识
    finish_reason: Optional[str] = None
    # 类型
    role: Optional[str] = None
    # 工具调用集合
    tool_calls: Optional[List[ToolInstance]] = None
    # 创建时间
    created: Optional[datetime] = None
    # 元数据
    metadata: DialogSegmentMetadata

    @classmethod
    def make_user_message(
        cls,
        content: str | List[DialogSegmentContent],
        conversation_id: str,
        id: Optional[str] = None,
        metadata: Optional[DialogSegmentMetadata] = None,
        payload: Dict[str, Any] = None
    ) -> "DialogSegment":
        default_metadata = DialogSegmentMetadata(source=MetadataSource.USER, type=MetadataType.MESSAGE)
        return cls(
            id=id if id else create_uuid(),
            conversation_id=conversation_id,
            content=content,
            role="user",
            finish_reason="stop",
            created=create_from_second_now(),
            payload=payload if payload else {},
            metadata=metadata if metadata is not None else default_metadata,
        )

    @classmethod
    def make_assistant_message(
        cls, content: str,
        conversation_id: str,
        model: str,
        timestamp: int,
        reasoning_content: Optional[str] = None,
        id: Optional[str] = None,
        metadata: Optional[DialogSegmentMetadata] = None,
        payload: Dict[str, Any] = None
    ) -> "DialogSegment":
        default_metadata = DialogSegmentMetadata(source=MetadataSource.ASSISTANT, type=MetadataType.MESSAGE)
        return cls(
            id=id if id else create_uuid(),
            conversation_id=conversation_id,
            content=content,
            reasoning_content=reasoning_content,
            model=model,
            role="assistant",
            finish_reason="stop",
            created = create_from_timestamp(timestamp),
            payload=payload if payload else {},
            metadata=metadata if metadata is not None else default_metadata,
        )

    def convert_chat_streaming_chunk(self) -> ChatStreamingChunk:
        dialog_segment_content_copy = self.content
        if self.role == 'user' and self.content and isinstance(self.content, List):
            content_list = []
            for dialog_segment_content_item in self.content:
                if dialog_segment_content_item.type == 'text':
                    content_list.append({'type': "text", 'text': dialog_segment_content_item.content})
                if dialog_segment_content_item.type == 'image':
                    base64_image = open_and_base64(dialog_segment_content_item.content)
                    content_list.append({
                    "type": "image_url",
                    "image_url":{
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
            dialog_segment_content_copy = content_list
        return ChatStreamingChunk(
            id=self.id,
            model=self.model,
            content=dialog_segment_content_copy,
            reasoning_content=self.reasoning_content,
            role=self.role,
            finish_reason=self.finish_reason,
            created=create_from_timestamp_to_int(self.created)
        )

    # 自定义处理模型转化为字典的方法
    def model_dump(self, **kwargs):
        # 使用 super() 获取字典格式
        data = super().model_dump()
        # 转换 datetime 字段为字符串（ISO 格式）
        data['created'] = self.created.isoformat() if self.created else None
        data['metadata'] = self.metadata.model_dump(**kwargs)
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # 确保将创建的字符串转换为 datetime 对象
        if 'created' in obj and isinstance(obj['created'], str):
            obj['created'] = datetime.fromisoformat(obj['created'])
        if 'metadata' in obj and isinstance(obj['metadata'], dict):
            obj['metadata'] = DialogSegmentMetadata.model_validate(obj['metadata'], **kwargs)
        return super().model_validate(obj)

class Conversation(BaseModel):
    """chat bot 会话对象"""

    # 会话ID
    id: Optional[str] = None
    # 会话主题
    theme: Optional[str] = None
    # 创建时间
    created: Optional[datetime] = None
    # 最后对话片段
    last_dialog_segment: Optional[DialogSegment] = None
    # 当前会话最大长度
    max_length: int = 50
    # 会话类型
    type: Optional[Literal["chat", "plan"]]
    # 对话片段集合
    dialog_segment_list: Optional[List[DialogSegment]] = None

    @classmethod
    def init(cls, conversation_type: Optional[Literal["chat", "plan"]]) -> "Conversation":
        return cls(id=create_uuid(), created=create_from_second_now(), dialog_segment_list=[], type=conversation_type)

    @classmethod
    def from_update_theme(cls, id: str, theme: str):
        return cls(id=id, theme=theme, type="chat")

    def convert_sort_memory(self) -> List[ChatStreamingChunk]:
        """用于普通会话的消息集合拼装，由于LLM任务开始的时候用户的输入已经保存，所以这里处理最后条消息，可能base64个图片"""
        rs_list: List[ChatStreamingChunk] = []
        for i, dialog_segment in enumerate(self.dialog_segment_list):
            if dialog_segment.metadata.type != MetadataType.MESSAGE and dialog_segment.metadata.type != MetadataType.AGENT_RESULT:
                continue
            if i == len(self.dialog_segment_list) - 1:
                # 最后一个元素解析图片，非最后的对话则删除图片记录
                chat_streaming_chunk = dialog_segment.convert_chat_streaming_chunk()
                rs_list.append(chat_streaming_chunk)
            else:
                if dialog_segment.role == 'user' and dialog_segment.content and isinstance(dialog_segment.content, List):
                    continue
                else:
                    chat_streaming_chunk = dialog_segment.convert_chat_streaming_chunk()
                    rs_list.append(chat_streaming_chunk)
        return rs_list

    def convert_sort_memory_history(self) -> List[ChatStreamingChunk]:
        """用于多agent，即对话历史拼装相对灵活，只拼装历史（在应用逻辑中确保没有拼接当前用户的输入信息，不然会忽略掉用户输入的包含图片的整条消息）"""
        rs_list: List[ChatStreamingChunk] = []
        for i, dialog_segment in enumerate(self.dialog_segment_list):
            if dialog_segment.role == 'user' and dialog_segment.content and isinstance(dialog_segment.content, List):
                continue
            else:
                chat_streaming_chunk = dialog_segment.convert_chat_streaming_chunk()
                rs_list.append(chat_streaming_chunk)
        return rs_list

    # 自定义处理模型转化为字典的方法
    def model_dump(self, **kwargs):
        # 使用 super() 获取字典格式
        data = super().model_dump()
        # 转换 datetime 字段为字符串（ISO 格式）
        data['created'] = self.created.isoformat() if self.created else None
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # 确保将创建的字符串转换为 datetime 对象
        if 'created' in obj and isinstance(obj['created'], str):
            obj['created'] = datetime.fromisoformat(obj['created'])
        return super().model_validate(obj)