from application.domain.agents.agent import Agent, AgentInfo, AgentState
from application.domain.conversation import DialogSegment, DialogSegmentMetadata, MetadataSource, MetadataType
from application.domain.events.event import Event, EventType, EventSubType
from application.domain.generators.firm import GeneratorFirm
from application.domain.generators.generator import LLMGenerator
from application.domain.tasks.task import TaskType, Task
from application.port.outbound.agent_port import AgentPort
from application.port.outbound.conversation_port import ConversationPort
from application.port.outbound.event_port import EventHandler
from application.port.outbound.generators_port import GeneratorsPort
from application.port.outbound.user_setting_port import UserSettingPort
from application.port.outbound.ws_message_port import WsMessagePort
from common.core.errors.business_error_code import GeneratorErrorCode
from common.core.errors.business_exception import BusinessException
from common.utils.time_utils import create_from_second_now_to_int
from common.core.container.annotate import component
from application.port.outbound.task_port import TaskPort
from common.core.logger import get_logger

import injector

logger = get_logger(__name__)

@component
class AgentCallEventHandler(EventHandler):

    @injector.inject
    def __init__(
            self,
            conversation_port: ConversationPort,
            agent_port: AgentPort,
            generators_port: GeneratorsPort,
            user_setting_port: UserSettingPort,
            ws_message_port: WsMessagePort,
    ):
        self.conversation_port = conversation_port
        self.agent_port = agent_port
        self.generators_port = generators_port
        self.user_setting_port = user_setting_port
        self.ws_message_port = ws_message_port

    def handle(self, event: Event) -> None:
        agent_instance_id = event.payload['agent_instance_id']
        dialog_segment_id = event.data['dialog_segment_id']
        conversation_id = event.data['conversation_id']
        generator_id = event.data['generator_id']
        agent_info: AgentInfo = self.agent_port.load_instance_info(instance_id=agent_instance_id, conversation_id=conversation_id)
        if agent_info.state == AgentState.INIT: # 首次运行agent，保存调用记录
            content = event.data['content']
            generator = self._llm_generator(generator_id=generator_id)
            # 创建agent开始记录
            # todo 暂时改变一些逻辑，agent开始结束事件暂时不记录日志
            # assistant_dialog_segment = DialogSegment.make_assistant_message(
            #     conversation_id=conversation_id, id=dialog_segment_id, content=content,
            #     model=generator.model, timestamp=create_from_second_now_to_int(),
            #     payload={"agent_instance_id": agent_instance_id},
            #     metadata=DialogSegmentMetadata(source=MetadataSource.ASSISTANT, type=MetadataType.AGENT_BEGIN))
            # self.conversation_port.conversation_add(dialog_segment=assistant_dialog_segment)
            #logger.info(f"保存Agent调用对话片段：[ID：{assistant_dialog_segment.id} - 内容：{content}]")
            logger.info(f"保存Agent调用对话片段：[ID：{dialog_segment_id} - 内容：{content}]")
            self.ws_message_port.send(event)

        if event.sub_type == EventSubType.AGENT_CALL:
            # 创建agent call任务
            task = Task.from_singleton(task_type=TaskType.AGENT_CALL, data=event.data, payload=event.payload, client_id=event.client_id)
            TaskPort.get_task_port().execute_task(task)

        if event.sub_type == EventSubType.AGENT_CALL_RESULT:
            # 创建agent反馈请求任务
            task = Task.from_singleton(task_type=TaskType.AGENT_CALL_RESULT, data=event.data, payload=event.payload, client_id=event.client_id)
            TaskPort.get_task_port().execute_task(task)

    def type(self) -> str:
        return EventType.AGENT.value

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