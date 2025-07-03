import json

from application.domain.agents.agent import Agent, AgentInfo, AgentState
from application.domain.tasks.task import Task, TaskType, TaskState
from application.port.inbound.task_handler import TaskHandler
from application.port.outbound.conversation_port import ConversationPort
from application.port.outbound.event_port import EventPort
from application.port.outbound.ws_message_port import WsMessagePort
from common.core.container.annotate import component
from application.port.outbound.agent_port import AgentPort
from application.port.outbound.tools_port import ToolsPort
from application.port.outbound.generators_port import GeneratorsPort
from application.domain.generators.generator import LLMGenerator
from application.port.outbound.user_setting_port import UserSettingPort
from application.domain.generators.firm import GeneratorFirm
from common.core.errors.business_error_code import GeneratorErrorCode
from common.core.errors.business_exception import BusinessException

from common.core.logger import get_logger
import injector

logger = get_logger(__name__)

@component
class AgentTaskHandler(TaskHandler):

    @injector.inject
    def __init__(
        self,
        agent_port: AgentPort,
        tools_port: ToolsPort,
        event_port: EventPort,
        conversation_port: ConversationPort,
        generators_port: GeneratorsPort,
        ws_message_port: WsMessagePort,
        user_setting_port: UserSettingPort,
    ):
        self.agent_port = agent_port
        self.tools_port = tools_port
        self.event_port = event_port
        self.generators_port = generators_port
        self.ws_message_port = ws_message_port
        self.user_setting_port = user_setting_port
        self.conversation_port = conversation_port

    def execute(self, task: Task):
        print("AgentTaskHandler")
        agent_instance_id = task.payload["agent_instance_id"]
        conversation_id = task.data['conversation_id']
        dialog_segment_id = task.data['dialog_segment_id']
        generator_id = task.data['generator_id']

        # 查询会话历史
        history_conversation = self.conversation_port.conversation_load(conversation_id=conversation_id)
        if not history_conversation:
            raise BusinessException(error_code=GeneratorErrorCode.NO_CONVERSATION_FOUND,
                                    dynamics_message=conversation_id)
        # 获取 agent 实例，并保存调用记录
        agent_info: AgentInfo = self.agent_port.load_instance_info(instance_id=agent_instance_id, conversation_id=conversation_id)
        # 获取agent实例
        generator = self._llm_generator(generator_id=agent_info.generator_id if agent_info.generator_id else generator_id)
        # 创建可执行Agent实例
        agent_instance = self.agent_port.make_instance(
            agent_info=agent_info,
            generators_port=self.generators_port,
            llm_generator=generator,
            conversation_port=self.conversation_port,
            ws_message_port=self.ws_message_port,
            tools_port=self.tools_port,
        )
        agent_instance.init_info(agent_info=agent_info)
        # payload 设置
        if "json_result" in task.payload and "content" in task.data: # LLM返回的json结果
            # logger.info(f"task: {task}")
            if task.payload['json_result']:
                logger.info(f"agent接受json结果{task.data["content"]}")
                # task.payload['json_result_data'] = json.loads(task.data["content"])
                task.payload['json_result_data'] = task.data["content"]
            else:
                task.payload['content'] = task.data["content"]

        if agent_instance.get_info().state == AgentState.INIT:
            # 保存agent实例为运行状态
            agent_instance.run()
            self.agent_port.save_instance_info(agent_instance.get_info())
        # 执行agent
        agent_instance.execute(history_message_list=history_conversation.convert_sort_memory(), payload=task.payload, client_id=task.client_id)


    def state(self) -> TaskState:
        pass

    def set_state(self, state: TaskState):
        pass

    def check_stop_flag(self) -> bool:
        pass



    def type(self) -> str:
        return TaskType.AGENT_CALL.value

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