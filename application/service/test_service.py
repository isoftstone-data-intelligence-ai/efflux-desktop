from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from application.domain.generators.firm import GeneratorFirm
from application.domain.generators.generator import LLMGenerator
from application.domain.tasks.task import Task, TaskType
from application.domain.conversation import Conversation
from application.port.outbound.conversation_port import ConversationPort
from application.port.outbound.generators_port import GeneratorsPort
from application.port.outbound.user_setting_port import UserSettingPort
from common.core.container.annotate import component
from application.port.outbound.task_port import TaskPort
from application.port.inbound.test_case import TestCase
from application.port.outbound.event_port import EventPort
from application.port.outbound.cache_port import CachePort
from application.domain.events.event import Event, EventType, EventSubType
import injector

from common.core.errors.business_error_code import GeneratorErrorCode
from common.core.errors.business_exception import BusinessException
from common.utils.common_utils import create_uuid, CONVERSATION_STOP_FLAG_KEY
from common.core.logger import get_logger
from typing import Optional, List, Dict, Any
import json

logger = get_logger(__name__)


@component
class TestService(TestCase):

    @injector.inject
    def __init__(
        self,
        task_manager: TaskPort,
        conversation_port: ConversationPort,
        generators_port: GeneratorsPort,
        cache_port: CachePort,
        event_port: EventPort,
        user_setting_port: UserSettingPort,
    ):
        self.task_manager = task_manager
        self.conversation_port = conversation_port
        self.cache_port = cache_port
        self.event_port = event_port
        self.generators_port = generators_port
        self.user_setting_port = user_setting_port

    async def test_task(self):
        task = Task.from_singleton(task_type=TaskType.LLM_CALL, data={})
        self.task_manager.execute_task(task=task)

    async def test_task_stop(self, task_id: str) -> bool:
        return self.task_manager.cancel_task(task_id=task_id)

    async def test_call_agent(self, query: str, generator_id: str, conversation_id: Optional[str] = None) -> tuple[str | None, str]:
        query_str = None
        if isinstance(query, List):
            for item in query:
                if item.type == 'text':
                    query_str = item.content
        # 创建会话
        if not conversation_id:
            conversation = Conversation()
            conversation.init()
            conversation.theme = query_str
            conversation.dialog_segment_list = []
            self.conversation_port.conversation_save(conversation=conversation)
            conversation_id = conversation.id
            logger.info(f"首次发送消息创建会话：[ID：{conversation.id} - 主题：{conversation.theme}]")
        else:
            logger.info(f"历史会话消息：[ID：{conversation_id}]")
        uuid = create_uuid()
        # 清除会话的停止状态
        self.cache_port.set_data(name=CONVERSATION_STOP_FLAG_KEY, key=conversation_id, value=False)
        event = Event.from_init(
            client_id="1",
            event_type=EventType.AGENT,
            event_sub_type=EventSubType.AGENT_CALL,
            data={
                "id": uuid,
                "agent_id": "4877f996-2fb5-400d-9b26-245a824e325f",
                "conversation_id": conversation_id,
                "generator_id": generator_id,
                "content": query,
            }
        )
        logger.info(f"[GeneratorService]发起[{EventType.AGENT} - {EventSubType.AGENT_CALL}]事件：[ID：{event.id}]")
        self.event_port.emit_event(event)
        return conversation_id, uuid

    async def test_prompts(self, chunks: List[ChatStreamingChunk], generator_id: str) -> Dict[str, Any]:
        return self.generators_port.generate_json(llm_generator=self._llm_generator(generator_id=generator_id), messages=chunks, validate_json=None, json_object=True)

    def _llm_generator(self, generator_id: str) -> LLMGenerator:
        # 获取厂商api key
        llm_generator: LLMGenerator = self.generators_port.load_generate(generator_id)
        if llm_generator is None:
            raise BusinessException(error_code=GeneratorErrorCode.GENERATOR_NOT_FOUND, dynamics_message=generator_id)
        firm: GeneratorFirm = self.user_setting_port.load_firm_setting(llm_generator.firm)
        if self.generators_port.is_non_standard(firm.name):
            llm_generator.set_api_key_secret(firm.fields)
        else:
            llm_generator.set_api_key_secret(firm.api_key)
        llm_generator.check_firm_api_key()
        return llm_generator