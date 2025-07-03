from application.domain.tasks.task import TaskType, Task, TaskState
from application.domain.events.event import Event, EventType, EventGroupStatus, EventSubType, EventGroup, EventSource
from application.port.inbound.task_handler import TaskHandler
from common.core.container.annotate import component
from common.core.errors.business_error_code import GeneratorErrorCode
from common.core.errors.business_exception import BusinessException
from common.utils.common_utils import create_uuid, CONVERSATION_STOP_FLAG_KEY
from common.utils.json_file_util import JSONFileUtil
from common.utils.time_utils import create_from_second_now_to_int
from application.port.outbound.event_port import EventPort
from application.domain.generators.firm import GeneratorFirm
from application.port.outbound.user_setting_port import UserSettingPort
from application.port.outbound.generators_port import GeneratorsPort
from application.port.outbound.tools_port import ToolsPort
from application.port.outbound.mcp_server_port import MCPServerPort
from application.port.outbound.cache_port import CachePort
from application.domain.generators.generator import LLMGenerator
from application.domain.generators.tools import Tool, ToolInstance, ToolType
from application.port.outbound.conversation_port import ConversationPort
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk, ChatCompletionMessageToolCall
from common.core.errors.common_exception import handle_exception
from typing import List, Dict, Any, Optional
import tiktoken
import asyncio
import injector
import json

from common.core.logger import get_logger

logger = get_logger(__name__)

@component
class LLMTaskHandler(TaskHandler):

    """
    默认chat模型调用
    """

    @injector.inject
    def __init__(
        self,
        user_setting_port: UserSettingPort,
        generators_port: GeneratorsPort,
        tools_port: ToolsPort,
        mcp_server_port: MCPServerPort,
        conversation_port: ConversationPort,
        cache_port: CachePort,
    ):
        self.user_setting_port = user_setting_port
        self.generators_port = generators_port
        self.tools_port = tools_port
        self.mcp_server_port = mcp_server_port
        self.conversation_port = conversation_port
        self.cache_port = cache_port

    # 动态计算 default 值的函数，接收异常对象
    @staticmethod
    def _calculate_default_value(*args, **kwargs):
        # 获取传入的 task 参数（假设 task 是第一个参数）
        task = args[1] if args else None
        exception = kwargs.get('exception')  # 获取异常对象
        event = Event.from_init(
            client_id=task.client_id,
            event_type=EventType.SYSTEM,
            event_sub_type=EventSubType.ERROR,
            source=EventSource.LLM_HANDLER,
            data={
                'code': "1",
                'message': f"{TaskType.LLM_CALL} 异常：{str(exception)}",
            }
        )
        EventPort.get_event_port().emit_event(event)

    @handle_exception(default_func=_calculate_default_value)
    def execute(self, task: Task):
        logger.info(f"LLM调用任务：[任务：{task.id}]")
        client_id = task.client_id
        tools_call_result = True if 'tools_call_result' in task.data.keys() else False
        conversation_id = task.data['conversation_id']
        dialog_segment_id = task.data['dialog_segment_id']
        generator_id = task.data['generator_id']

        mcp_name_list = task.payload['mcp_name_list'] if 'mcp_name_list' in task.payload else []
        tools_group_name_list = task.payload['tools_group_name_list'] if 'tools_group_name_list' in task.payload else []
        agent_instance_id = task.payload['agent_instance_id'] if 'agent_instance_id' in task.payload else None
        agent_name = task.payload['agent_name'] if 'agent_name' in task.payload else None
        json_result = task.payload['json_result'] if 'json_result' in task.payload else None
        json_type = task.payload['json_type'] if 'json_type' in task.payload else None
        message_list = task.payload['context_message_list']

        # 获取LLMGenerator
        llm_generator: LLMGenerator = self._llm_generator(generator_id)
        # 工具装载
        tools: List[Tool] = []
        for mcp_name in mcp_name_list:
            tools.extend(asyncio.run(self.tools_port.load_tools(group_name=mcp_name, tool_type=ToolType.MCP)))
        for tools_group_name in tools_group_name_list:
            tools.extend(asyncio.run(self.tools_port.load_tools(group_name=tools_group_name, tool_type=ToolType.LOCAL)))

        messages = []
        dialog_segment_id_list = []
        for history_message in message_list:
            messages.append(history_message)
            # 拼装工具调用历史
            if tools_call_result:
                if history_message.role != "assistant": # 排除非ai返回的消息，即非tool调用消息
                    continue
                if history_message.id in dialog_segment_id_list: # 避免多个相同的dialog_segment_id的工具调用查询
                    continue
                dialog_segment_id_list.append(history_message.id)
                tool_instance_list = self.tools_port.load_instance(conversation_id=conversation_id, dialog_segment_id=history_message.id)
                if tool_instance_list:
                    messages.extend(self._tool_calls_history(tool_instance_list))

        # 流式返回组id
        uuid = create_uuid()
        # 记录是否已经发送了STARTED状态的事件
        started_event_sent = False
        # 停止标记
        stop_flag = False
        # json 开始标识
        json_start_flag = False
        # json 结束标识
        json_end_flag = False
        # json 内容
        json_content = ""
        for chunk in self.generators_port.generate_event(
            llm_generator=llm_generator,
            messages=messages,
            tools=tools,
            json_object=json_result
        ):
            if chunk.usage: # 跳过用量chunk消息
                continue
            # 确定当前事件的组状态
            group_status = EventGroupStatus.SENDING
            if not started_event_sent:
                group_status = EventGroupStatus.STARTED
                started_event_sent = True
            elif chunk.finish_reason == 'stop':
                group_status = EventGroupStatus.ENDED
            # 停止检查
            if self.cache_port.get_from_cache(name=CONVERSATION_STOP_FLAG_KEY, key=conversation_id):
                group_status = EventGroupStatus.STOPPED
                stop_flag = True
            # 工具调用
            if chunk.finish_reason == 'tool_calls':
                if stop_flag:
                    break
                event = chunk.to_tool_calls_message_event(
                    id=uuid,
                    client_id=client_id,
                    conversation_id=conversation_id,
                    dialog_segment_id=dialog_segment_id,
                    generator_id=generator_id,
                    payload={
                        "agent_instance_id": agent_instance_id,
                        "agent_name": agent_name,
                        "mcp_name_list": mcp_name_list,
                        "tools_group_name_list": tools_group_name_list,
                        "json_result": json_result,
                        "json_type": json_type
                    }
                )
                logger.info(f"任务处理器[{self.type()}]发起[{event.type} - {event.sub_type}]事件：[ID：{event.id}]")
                EventPort.get_event_port().emit_event(event)
                continue
            # json 开始标识记录并截取字段
            if json_result and not json_start_flag:
                if chunk.content:
                    text = JSONFileUtil.process_string(chunk.content)
                    if text:
                        json_start_flag = True
                        chunk.content = text
                        group_status = EventGroupStatus.STARTED
            if json_result and not json_start_flag:
                logger.info(f"json结果，跳过开始chunk：{chunk.content}")
                continue
            # json 结束标记
            if json_result and json_start_flag and chunk.content:
                # 拼接json结果
                json_content += chunk.content
                if JSONFileUtil.find_json_end(json_content):
                    text = JSONFileUtil.process_string_reverse(chunk.content)
                    if text:
                        json_end_flag = True
                        chunk.content = text
                        group_status = EventGroupStatus.ENDED

            if json_result and json_start_flag and json_end_flag and chunk.content:
                if JSONFileUtil.process_string_reverse(chunk.content): # 判断最后“}”
                    logger.info(f"json结果，结束chunk拼接{chunk.content}")
                else:
                    logger.info(f"json结果，跳过结束chunk：{chunk.content}")
                    continue


            if json_result and json_start_flag and json_end_flag and not chunk.content:
                logger.info(f"json结果，跳过结束chunk：{chunk.content} - {chunk.finish_reason}")
                continue

            # 消息返回
            event = chunk.to_assistant_message_event(
                id=uuid,
                client_id=client_id,
                conversation_id=conversation_id,
                dialog_segment_id=dialog_segment_id,
                generator_id=generator_id,
                event_group=EventGroup(id=uuid, status=group_status),
                payload={
                    "agent_instance_id": agent_instance_id,
                    "agent_name": agent_name,
                    "mcp_name_list": mcp_name_list,
                    "tools_group_name_list": tools_group_name_list,
                    "json_result": json_result,
                    "json_type": json_type,
                }
            )
            EventPort.get_event_port().emit_event(event)
            if stop_flag:
                self._send_system_stop_event(uuid=uuid, agent_id=agent_instance_id, conversation_id=conversation_id, client_id=client_id)
                break

    def _send_system_stop_event(self, uuid: str, conversation_id: str, agent_id: str, client_id: str):
        """
        发起系统停止事件
        :param uuid:
        :param conversation_id:
        :param agent_id:
        :return:
        """
        event = Event.from_stop(
            client_id=client_id,
            data={
                "id": uuid,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
            },
            # group=EventGroup(id=group_event_id, status=group_status),
        )
        logger.info(f"任务处理器[{self.type()}]发起[{event.type} - {event.sub_type}]事件：[ID：{event.id}]")
        EventPort.get_event_port().emit_event(event)

    def type(self) -> str:
        return TaskType.LLM_CALL.value

    def state(self) -> TaskState:
        pass

    def set_state(self, state: TaskState):
        pass

    def check_stop_flag(self) -> bool:
        return self.cache_port.get_from_cache(name=CONVERSATION_STOP_FLAG_KEY, key=conversation_id)


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

    @staticmethod
    def _tool_calls_history(tool_instance_list: List[ToolInstance]) -> List[ChatStreamingChunk]:
        chunk_list: List[ChatStreamingChunk] = []
        # 拼装方法调用请求
        for tool_instance in tool_instance_list:
            tool_calls = [ChatCompletionMessageToolCall(
                id=tool_instance.tool_call_id, mcp_server_name=tool_instance.mcp_server_name, name=tool_instance.name,
                description=tool_instance.description, arguments=json.dumps(tool_instance.arguments))]
            chunk_list.append(ChatStreamingChunk.from_tool_calls(tool_calls=tool_calls))
            # 拼装方法调用结果
            chunk_list.append(
                ChatStreamingChunk.from_tool_calls_result(content=json.dumps(tool_instance.result),
                                                          tool_call_id=tool_instance.tool_call_id,
                                                          tool_calls=tool_calls))
        return chunk_list

    # @staticmethod
    # def _tool_calls_history(tool_instance_list: List[ToolInstance]) -> List[ChatStreamingChunk]:
    #     chunk_list: List[ChatStreamingChunk] = []
    #     chunk_call_list: List[ChatCompletionMessageToolCall] = []
    #     # 拼装方法调用请求
    #     for tool_instance in tool_instance_list:
    #         chunk_call_list.append(ChatCompletionMessageToolCall(
    #             id=tool_instance.tool_call_id, mcp_server_name=tool_instance.mcp_server_name, name=tool_instance.name,
    #             description=tool_instance.description, arguments=json.dumps(tool_instance.arguments)))
    #     chunk_list.append(ChatStreamingChunk.from_tool_calls(tool_calls=chunk_call_list))
    #
    #     for tool_instance in tool_instance_list:
    #         # 拼装方法调用结果
    #         chunk_list.append(
    #             ChatStreamingChunk.from_tool_calls_result(content=str(tool_instance.result), tool_call_id=tool_instance.tool_call_id))
    #     return chunk_list