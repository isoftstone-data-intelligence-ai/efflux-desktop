from datetime import datetime
from typing import Dict, Any, List, Optional

from application.domain.agents.agent import Agent, AgentInfo, AgentState
from application.domain.events.event import Event, EventType, EventSubType, EventSource
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from application.domain.plan import PlanState, PlanStep, Plan
from application.domain.tasks.task import Task, TaskType, TaskState
from application.port.inbound.task_handler import TaskHandler
from application.port.outbound.cache_port import CachePort
from application.port.outbound.conversation_port import ConversationPort
from application.port.outbound.event_port import EventPort
from application.port.outbound.plan_port import PlanPort
from application.port.outbound.ws_message_port import WsMessagePort
from common.core.container.annotate import component
from application.port.outbound.agent_port import AgentPort
from application.port.outbound.tools_port import ToolsPort
from application.port.outbound.generators_port import GeneratorsPort
from application.domain.generators.generator import LLMGenerator
from application.port.outbound.user_setting_port import UserSettingPort
from application.domain.generators.firm import GeneratorFirm
from application.service.prompts.orchestration import ORCHESTRATOR_PROGRESS_LEDGER_PROMPT, ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION, INSTRUCTION_AGENT_FORMAT
from common.core.errors.business_error_code import GeneratorErrorCode
from common.core.errors.business_exception import BusinessException

from common.core.logger import get_logger
import injector

from common.utils.common_utils import create_uuid, CURRENT_CONVERSATION_AGENT_INSTANCE_ID

logger = get_logger(__name__)

@component
class AgentTaskResultHandler(TaskHandler):

    @injector.inject
    def __init__(
        self,
        cache_port: CachePort,
        agent_port: AgentPort,
        tools_port: ToolsPort,
        event_port: EventPort,
        conversation_port: ConversationPort,
        generators_port: GeneratorsPort,
        ws_message_port: WsMessagePort,
        user_setting_port: UserSettingPort,
        plan_port: PlanPort,
    ):
        self.agent_port = agent_port
        self.tools_port = tools_port
        self.event_port = event_port
        self.cache_port = cache_port
        self.generators_port = generators_port
        self.ws_message_port = ws_message_port
        self.user_setting_port = user_setting_port
        self.conversation_port = conversation_port
        self.plan_port = plan_port

    def execute(self, task: Task):
        print("AgentTaskResultHandler")
        agent_instance_id = task.data['agent_instance_id']
        conversation_id = task.data['conversation_id']
        generator_id = task.data['generator_id']
        dialog_segment_id = task.data['dialog_segment_id']
        client_id = task.client_id
        # 更新agent状态
        agent_info = self.agent_port.load_instance_info(instance_id=agent_instance_id, conversation_id=conversation_id)
        agent_info.state = task.payload['agent_state']
        self.agent_port.save_instance_info(instance_info=agent_info)
        if agent_info.state == AgentState.DONE:
            logger.info(f"当前Agent执行结束，清空当前对话的当前Agent id")
            self.cache_port.delete_from_cache(CURRENT_CONVERSATION_AGENT_INSTANCE_ID, conversation_id)
        # 如果agent是clarification类型,并且任务完成，调用plan agent
        if agent_info.name == "clarification" and agent_info.state == AgentState.DONE:
            # 根据重新规划的结果调用agent
            self._call_agent(agent_name='plan',
                             client_id=client_id,
                             conversation_id= conversation_id,
                             generator_id = generator_id,
                             payload = {'update': False})
            # 清除当前会话agent_instance_id
            logger.info(f"需求澄清结束，调用计划Agent")

        # 如果agent是plan类型
        if agent_info.name == "plan": # 更新计划状态
            self.plan_port.sava(task.payload['plan'])
            if agent_info.state == AgentState.DONE and task.payload['plan'].state == PlanState.RUNNING:
                # 获取运行第一个step
                self._execute_step(client_id=client_id, conversation_id=conversation_id, generator_id=generator_id, plan=task.payload['plan'])

        # 判读是否需要用户确认
        if 'confirm_data' in task.payload:
            print(f"需用户确认-》[{task.payload['confirm_data']}]")
            event = Event.from_init(
                client_id=task.client_id,
                event_type=EventType.INTERACTIVE,
                event_sub_type=EventSubType.CALL_USER,
                source=EventSource.AGENT,
                data=task.data,
                payload={
                    "confirm_data": task.payload['confirm_data'],
                    "confirm_type": task.payload['confirm_type'],
                    "agent_instance_id": agent_instance_id,
                },
            )
            EventPort.get_event_port().emit_event(event)

    def _execute_step(self, client_id: str, conversation_id: str, generator_id: str, plan: Plan):
        history_conversation = self.conversation_port.conversation_load(conversation_id=conversation_id)
        message_list = self._thread_to_context(history_message_list=history_conversation.convert_sort_memory())
        message_list.append(ChatStreamingChunk.from_system(
            message=self._redesign_step_prompt(plan=plan, step=plan.steps[plan.current_step])))
        # 检查当前的step
        llm_generator = self._llm_generator(generator_id=generator_id)
        result_dict = self._redesign_step(llm_generator=llm_generator, message_list=message_list)
        logger.info(f"\nTask[{plan.task}]-[{plan.conversation_id}]总任务数：[{len(plan.steps)}],当前任务index[{plan.current_step}] \n任务进展：[{result_dict["progress_summary"]}]")
        if result_dict["need_to_replan"]["answer"]:
            print(f"需要重新规划任务： 原因：[{result_dict["need_to_replan"]["reason"]}]")
            # TODO重新规划逻辑
        # 任务进行
        if result_dict["is_current_step_complete"]["answer"]: # step任务完成
            logger.info(f"当前任务完成：[{result_dict["is_current_step_complete"]["reason"]}]")
            if len(plan.steps) == plan.current_step + 1:
                logger.info(f"计划[{plan.task}]-[{plan.conversation_id}]全部完成")
            else:
                # 更新当前步骤
                plan.go_next_step()
                self.plan_port.sava(plan)
                logger.info(f"执行下一步任务[{plan.current_step}]。。。")
                self._execute_step(client_id, conversation_id, generator_id, plan)
        else:
            logger.info(f"当前任务未完成：[{result_dict["is_current_step_complete"]["reason"]}]，继续执行。。。")
            next_call_agent_name = result_dict["instruction_or_question"]["agent_name"]
            # 获取调用提示词
            new_instruction = self._agent_instruction(
                instruction=result_dict["instruction_or_question"]["answer"],
                agent_name=next_call_agent_name,
                plan=plan
            )
            logger.info(f"选择AGENT[{next_call_agent_name}]，任务：[{result_dict["instruction_or_question"]["answer"]}]")
            # 检查是否存在这个agent
            if not self.agent_port.check_agent_in_teams(agent_name=next_call_agent_name):
                print(f"未找到AI返回的Agent[{next_call_agent_name}]")
                # 异常处理
            # 调用agent
            self._call_agent(agent_name=next_call_agent_name, client_id=client_id,
                             conversation_id=conversation_id, generator_id=generator_id,
                             payload={'prompt': new_instruction, "plan": plan})


    def state(self) -> TaskState:
        pass

    def set_state(self, state: TaskState):
        pass

    def check_stop_flag(self) -> bool:
        pass



    def type(self) -> str:
        return TaskType.AGENT_CALL_RESULT.value

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

    def _call_agent(
        self,
        agent_name: str,
        client_id: str,
        conversation_id: str,
        generator_id: str,
        payload: Dict[str, Any],
        dialog_segment_id: Optional[str] = None,
    ):
        dialog_segment_id = dialog_segment_id if dialog_segment_id else create_uuid()
        """Agent 调用方法"""
        # 创建并保存agent instance info 实体
        agent: Agent = self.agent_port.load_by_name(agent_name=agent_name)
        agent_info: AgentInfo = agent.info(
            conversation_id=conversation_id,
            dialog_segment_id=dialog_segment_id,
            generator_id=generator_id,
            instance_id=create_uuid(),
        )
        # 默认负载值
        payload['agent_instance_id'] = agent_info.instance_id
        # 保存
        self.agent_port.save_instance_info(instance_info=agent_info)
        event = Event.from_init(
            client_id=client_id,
            event_type=EventType.AGENT,
            event_sub_type=EventSubType.AGENT_CALL,
            source=EventSource.AGENT,
            payload=payload,
            data={
                "id": create_uuid(),
                "dialog_segment_id": dialog_segment_id,
                "conversation_id": conversation_id,
                "generator_id": generator_id,
                "content": f"call {agent_info.name} agent",
            },
        )
        logger.info(f"[AgentTaskResultHandler]发起[{EventType.AGENT} - {EventSubType.AGENT_CALL}]事件：[ID：{event.id}]")
        EventPort.get_event_port().emit_event(event)

    def _redesign_step(self, llm_generator: LLMGenerator, message_list:List[ChatStreamingChunk]) -> Dict[str, Any]:
        """重新检查计划执行"""
        return self.generators_port.generate_json(llm_generator=llm_generator, validate_json=None, messages=message_list)

    def _redesign_step_prompt(self, step: PlanStep, plan: Plan):
        agents, team_desc = self.agent_port.load_agent_teams()
        names = [agent.name for agent in agents]
        return ORCHESTRATOR_PROGRESS_LEDGER_PROMPT.format(
            task=plan.task,
            plan=str(plan),
            step_index=step.index,
            step_title=step.title,
            step_details=step.details,
            agent_name=step.agent_name,
            team=team_desc,
            names=", ".join(names),
            additional_instructions="",
        )

    def _agent_instruction(self, instruction: str, agent_name: str, plan: Plan) -> str:
        """agent 执行提示词"""
        return INSTRUCTION_AGENT_FORMAT.format(
            step_index=plan.current_step + 1,
            step_title=plan.steps[plan.current_step].title,
            step_details=plan.steps[plan.current_step].details,
            agent_name=agent_name,
            instruction=instruction,
        )

    def _thread_to_context(self, history_message_list: List[ChatStreamingChunk]) -> List[ChatStreamingChunk]:
        """拼装基础system提示词和会话历史信息"""
        date_today = datetime.now().strftime("%Y-%m-%d")
        # 拼装系统提示词
        messages: List[ChatStreamingChunk] = [ChatStreamingChunk.from_system(
            message=ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION.format(
                date_today=date_today
            )
        )]
        # 拼装对话上下文
        messages.extend(history_message_list)
        return messages