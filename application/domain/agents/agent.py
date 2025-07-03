from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel

from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from application.domain.generators.generator import LLMGenerator
from application.port.outbound.generators_port import GeneratorsPort
from application.port.outbound.conversation_port import ConversationPort
from application.port.outbound.tools_port import ToolsPort

from typing import Dict, Any, Optional, List, Literal

from application.port.outbound.ws_message_port import WsMessagePort


class AgentState(Enum):
    INIT = "INIT"
    RUNNING = "RUNNING"
    DONE = "DONE"

class Agent(BaseModel):

    id: Optional[str] = None
    name: Optional[str] = None
    generator_id: Optional[str] = None
    tools_group_list: Optional[List[Dict[str, Any]]] = None
    description: Optional[str] = None
    built_in: Optional[bool] = False
    agent_prompts: Optional[Dict[str, str]] = None
    result_type: Optional[Literal["text", "html", "svg", "code"]] = None

    def info(
        self,
        conversation_id: str,
        dialog_segment_id: str,
        generator_id: str,
        instance_id: Optional[str] = None
    ) -> "AgentInfo":
        return AgentInfo(
            id = self.id,
            name = self.name,
            tools_group_list = self.tools_group_list,
            description = self.description,
            built_in = self.built_in,
            agent_prompts = self.agent_prompts,
            conversation_id = conversation_id,
            dialog_segment_id = dialog_segment_id,
            result_type = self.result_type,
            generator_id = self.generator_id if self.generator_id else generator_id,
            instance_id=instance_id,
            state=AgentState.INIT,
        )

class AgentInfo(BaseModel):
    # 持久化
    id: Optional[str] = None
    name: Optional[str] = None
    generator_id: Optional[str] = None
    tools_group_list: Optional[List[Dict[str, Any]]] = None
    description: Optional[str] = None
    built_in: Optional[bool] = None
    agent_prompts: Optional[Dict[str, str]] = None
    result_type: Optional[Literal["text", "html", "svg", "code"]] = None

    # 运行状态
    state: Optional[AgentState] = None
    max_actions_per_step: Optional[int] = 5
    current_action_count: Optional[int] = 0

    # 持久化信息
    instance_id: str
    conversation_id: str
    dialog_segment_id: str
    generator_id: str

    def model_dump(self, **kwargs):
        # 使用 super() 获取字典格式
        data = super().model_dump()
        # 转换 为字符串
        data['state'] = self.state.value if self.state else None
        # if 'agent_prompts' in data:
        #     del data['agent_prompts']
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # 字符串转枚举
        if 'state' in obj and isinstance(obj['state'], AgentState):
            obj['state'] = AgentState(value=obj['state'])
        return super().model_validate(obj)


class AgentInstance(ABC):

    def __init__(
        self,
        llm_generator: LLMGenerator,
        generators_port: GeneratorsPort,
        ws_message_port: WsMessagePort,
        conversation_port: ConversationPort,
        tools_port: ToolsPort,
    ):
        self.llm_generator = llm_generator
        self.generators_port = generators_port
        self.ws_message_port = ws_message_port
        self.conversation_port = conversation_port
        self.tools_port = tools_port
        self.info: Optional[AgentInfo] = None

    @abstractmethod
    async def lazy_init(self, config: Dict[str, Any]) -> None:
        """懒加载agent配置"""


    @abstractmethod
    def execute(self, history_message_list: List[ChatStreamingChunk], payload: Dict[str, Any], client_id: str) -> None:
        """执行agent"""

    def init_info(self, agent_info: AgentInfo):
        """初始化agent状态"""
        self.info = agent_info

    def get_info(self):
        return self.info

    def run(self):
        self.info.state = AgentState.RUNNING