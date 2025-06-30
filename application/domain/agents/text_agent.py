from typing import List, Dict, Any

from application.domain.agents.agent import AgentInstance, AgentState
from application.domain.conversation import DialogSegment, DialogSegmentMetadata, MetadataSource, MetadataType
from application.domain.events.event import EventType, Event, EventSubType, EventSource
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from application.domain.generators.generator import LLMGenerator
from application.port.outbound.conversation_port import ConversationPort
from application.port.outbound.event_port import EventPort
from application.port.outbound.generators_port import GeneratorsPort
from application.port.outbound.tools_port import ToolsPort
from application.port.outbound.ws_message_port import WsMessagePort
from common.utils.common_utils import create_uuid
from common.utils.time_utils import create_from_second_now_to_int

from common.core.logger import get_logger

logger = get_logger(__name__)


class TextAgent(AgentInstance):

    def __init__(
            self,
            generators_port: GeneratorsPort,
            llm_generator: LLMGenerator,
            ws_message_port: WsMessagePort,
            conversation_port: ConversationPort,
            tools_port: ToolsPort,
    ):
        super().__init__(llm_generator, generators_port, ws_message_port, conversation_port, tools_port)


    async def lazy_init(self, config: Dict[str, Any]) -> None:
        pass

    def execute(self, history_message_list: List[ChatStreamingChunk], payload: Dict[str, Any], client_id: str) -> None:
        context_message_list = self._thread_to_context(history_message_list)
        content = None
        if "content" in payload:
            content = payload['content']
            logger.info(f"text agent 记录自己的会话历史: {content}")
            del payload['json_result']  # 删除要求json结果返回标识
            self._send_agent_result_event(client_id=client_id, payload=payload, agent_state=AgentState.DONE)
            # 请求大模型澄清用户需求
        else:
            self._send_llm_event(client_id=client_id, context_message_list=context_message_list)

        if content:
            # 保存agent结果
            dialog_segment = DialogSegment.make_assistant_message(content=content, id=self.info.dialog_segment_id,
                                                                  conversation_id=self.info.conversation_id,
                                                                  model=self.llm_generator.model,
                                                                  firm=self.llm_generator.firm,
                                                                  timestamp=create_from_second_now_to_int(),
                                                                  payload={'agent_instance_id': self.info.instance_id},
                                                                  metadata=DialogSegmentMetadata(
                                                                      source=MetadataSource.AGENT,
                                                                      type=MetadataType.AGENT_RESULT))
            self.conversation_port.conversation_add(dialog_segment=dialog_segment)

    def _thread_to_context(self, history_message_list: List[ChatStreamingChunk]) -> List[ChatStreamingChunk]:
        """拼装基础system提示词和会话历史信息"""
        # 拼装系统提示词
        messages: List[ChatStreamingChunk] = [ChatStreamingChunk.from_system(
            message=self.info.agent_prompts["SYSTEM_PROMPT"]
        )]
        # 拼装对话上下文
        messages.extend(history_message_list)
        return messages

    def _send_agent_result_event(self, client_id: str, payload: Dict[str, Any], agent_state: AgentState) -> None:
        payload['agent_state'] = agent_state
        event = Event.from_init(
            client_id=client_id,
            event_type=EventType.AGENT,
            event_sub_type=EventSubType.AGENT_CALL_RESULT,
            source=EventSource.AGENT,
            data={
                "id": create_uuid(),
                "agent_instance_id": self.info.instance_id,
                "dialog_segment_id": self.info.dialog_segment_id,
                "conversation_id": self.info.conversation_id,
                "generator_id": self.info.generator_id,
            },
            payload=payload
        )
        EventPort.get_event_port().emit_event(event)

    def _send_llm_event(self, client_id: str, context_message_list: List[ChatStreamingChunk]):
        """发送大模型请求事件"""
        event = Event.from_init(
            event_type=EventType.USER_MESSAGE,
            event_sub_type=EventSubType.MESSAGE,
            client_id=client_id,
            source=EventSource.AGENT,
            data={
                "id": create_uuid(),
                "dialog_segment_id": self.info.dialog_segment_id,
                "conversation_id": self.info.conversation_id,
                "generator_id": self.info.generator_id,
            },
            payload={
                "agent_instance_id": self.info.instance_id,
                "json_result": False,
                "mcp_name_list": [],
                "tools_group_name_list": [],
                "context_message_list": context_message_list,
            }
        )
        EventPort.get_event_port().emit_event(event)
        logger.info(
            f"[{self.info.name}]Agent实例[{self.info.instance_id}],发送LLM请求事件[{self.info.dialog_segment_id}]")