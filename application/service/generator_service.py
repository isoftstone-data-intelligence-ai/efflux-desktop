from typing import List, Optional, Dict, Any

from application.domain.agents.agent import Agent, AgentInfo
from application.domain.generators.firm import GeneratorFirm
from application.domain.generators.generator import LLMGenerator
from application.domain.tasks.task import Task, TaskType
from application.port.outbound.agent_port import AgentPort
from application.port.outbound.generators_port import GeneratorsPort
from application.port.inbound.model_case import ModelCase
from application.domain.events.event import Event, EventType, EventSubType, EventSource
from application.domain.conversation import Conversation, DialogSegmentContent, DialogSegment
from application.port.outbound.task_port import TaskPort
from common.core.container.annotate import component
from common.core.errors.business_error_code import GeneratorErrorCode
from common.core.errors.business_exception import BusinessException
from common.core.errors.common_error_code import CommonErrorCode
from common.core.errors.common_exception import CommonException
from common.utils.common_utils import create_uuid, CONVERSATION_STOP_FLAG_KEY, CURRENT_CONVERSATION_AGENT_INSTANCE_ID
from common.utils.time_utils import create_from_second_now_to_int
from application.port.outbound.event_port import EventPort
from application.port.inbound.generators_case import GeneratorsCase
from application.port.outbound.user_setting_port import UserSettingPort
from application.port.outbound.conversation_port import ConversationPort
from application.port.outbound.cache_port import CachePort
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from application.port.outbound.tools_port import ToolsPort
from application.domain.generators.tools import Tool, ToolInstance, ToolType
from common.utils.markdown_util import read
from common.utils.file_util import open_and_base64
import injector
import asyncio
import json

from common.core.logger import get_logger

logger = get_logger(__name__)


@component
class GeneratorService(ModelCase, GeneratorsCase):

    @injector.inject
    def __init__(self,
                 generators_port: GeneratorsPort,
                 event_port: EventPort,
                 agent_port: AgentPort,
                 tools_port: ToolsPort,
                 user_setting_port: UserSettingPort,
                 conversation_port: ConversationPort,
                 cache_port: CachePort,
                 ):
        self.generators_port = generators_port
        self.event_port = event_port
        self.agent_port = agent_port
        self.tools_port = tools_port
        self.user_setting_port = user_setting_port
        self.conversation_port = conversation_port
        self.cache_port = cache_port

    async def firm_list(self) -> List[GeneratorFirm]:
        return self.generators_port.load_firm()

    async def model_list(self, firm: str) -> List[LLMGenerator]:
        if self.generators_port.is_non_standard(firm):
            return self.generators_port.load_model_by_other_firm(firm)
        return self.generators_port.load_model_by_firm(firm)

    async def enabled_model_list(self, firm: str) -> List[LLMGenerator]:
        if firm:
            return self.generators_port.load_enabled_model_by_firm(firm)
        return self.generators_port.load_enabled_model()

    async def enable_or_disable_model(
        self, firm: str, model: str, enabled: bool, model_type: str
    ) -> Optional[bool]:
        return self.generators_port.enable_or_disable_model(
            firm, model, enabled, model_type)

    async def generate_test(
            self,
            generator_id: str,
            query: str,
            conversation_id: str,
            mcp_name_list: List[str],
            tools_group_name_list: Optional[List[str]] = None,
            task_confirm: Optional[Dict[str, Any]] = None
    ) -> str:
        # 获取LLMGenerator
        llm_generator: LLMGenerator = self._llm_generator(generator_id)

        message_list = []
        # # Path to your image
        # image_path = "/Users/siyong/PycharmProjects/efflux_desktop/uploads/123.jpeg"
        #
        # # Getting the base64 string
        # base64_image = open_and_base64(image_path)
        #
        # user_msg = [
        #     {
        #         "text": query,
        #         "type": "text"
        #     },
        #     {
        #         "type": "image_url",
        #         "image_url": {
        #             "url": f"data:image/jpeg;base64,{base64_image}"
        #         }
        #     }
        # ]
        # message_list = [{'role': 'user', 'content': '从北京到新疆乌鲁木齐，自驾怎么走'}, {'role': 'assistant', 'content': '你想要从北京驾车前往乌鲁木齐啊！这可是一段壮观的旅程，跨越大半个中国！让我为你查询一下自驾路线信息。\n\n首先，我需要获取北京和乌鲁木齐的地理坐标来规划路线。'}, {'role': 'assistant', 'tool_calls': [{'function': {'arguments': '{"address": "\\u5317\\u4eac\\u5e02", "city": "\\u5317\\u4eac"}', 'name': 'maps_geo'}, 'id': 'toolu_bdrk_01DEB8hyC1bzHo4xdBvuChXu', 'type': 'function'}]}, {'role': 'tool', 'tool_call_id': 'toolu_bdrk_01DEB8hyC1bzHo4xdBvuChXu', 'content': '[\'{"type":"text","text":"{\\\\n  \\\\"return\\\\": [\\\\n    {\\\\n      \\\\"country\\\\": \\\\"中国\\\\",\\\\n      \\\\"province\\\\": \\\\"北京市\\\\",\\\\n      \\\\"city\\\\": \\\\"北京市\\\\",\\\\n      \\\\"citycode\\\\": \\\\"010\\\\",\\\\n      \\\\"district\\\\": [],\\\\n      \\\\"street\\\\": [],\\\\n      \\\\"number\\\\": [],\\\\n      \\\\"adcode\\\\": \\\\"110000\\\\",\\\\n      \\\\"location\\\\": \\\\"116.407387,39.904179\\\\",\\\\n      \\\\"level\\\\": \\\\"省\\\\"\\\\n    }\\\\n  ]\\\\n}","annotations":null}\']'}, {'role': 'assistant', 'tool_calls': [{'function': {'arguments': '{"address": "\\u4e4c\\u9c81\\u6728\\u9f50\\u5e02", "city": "\\u4e4c\\u9c81\\u6728\\u9f50"}', 'name': 'maps_geo'}, 'id': 'toolu_bdrk_01LS7yoGSEzWg9ngQwMSyZ87', 'type': 'function'}]}, {'role': 'tool', 'tool_call_id': 'toolu_bdrk_01LS7yoGSEzWg9ngQwMSyZ87', 'content': '[\'{"type":"text","text":"{\\\\n  \\\\"return\\\\": [\\\\n    {\\\\n      \\\\"country\\\\": \\\\"中国\\\\",\\\\n      \\\\"province\\\\": \\\\"新疆维吾尔自治区\\\\",\\\\n      \\\\"city\\\\": \\\\"乌鲁木齐市\\\\",\\\\n      \\\\"citycode\\\\": \\\\"0991\\\\",\\\\n      \\\\"district\\\\": [],\\\\n      \\\\"street\\\\": [],\\\\n      \\\\"number\\\\": [],\\\\n      \\\\"adcode\\\\": \\\\"650100\\\\",\\\\n      \\\\"location\\\\": \\\\"87.616824,43.825377\\\\",\\\\n      \\\\"level\\\\": \\\\"市\\\\"\\\\n    }\\\\n  ]\\\\n}","annotations":null}\']'}, {'role': 'assistant', 'content': ''}]
        message_list.append(ChatStreamingChunk.from_user(message=query))
        # ws = WebSurfer(generators_port=self.generators_port, name="test")
        #
        # await ws.on_messages_stream(chunk_list=message_list, generator=llm_generator)

        # for a in self.generators_port.generate_event(llm_generator=llm_generator, messages=message_list, tools=[]):
        #     print(a)

        # 工具装载
        tools: List[Tool] = []
        for mcp_name in mcp_name_list:
            tools.extend(await self.tools_port.load_tools(group_name=mcp_name, tool_type=ToolType.MCP))

        di = self.generators_port.generate_test(llm_generator=llm_generator, messages=message_list, tools=tools, json_object=False)
        print(di)

        return "ok"

    async def generate(
            self,
            generator_id: str,
            query: str,
            conversation_id: str,
            mcp_name_list: Optional[List[str]] = None,
            tools_group_name_list: Optional[List[str]] = None,
            task_confirm: Optional[Dict[str, Any]] = None,
    ) -> str:

        # 获取LLMGenerator
        llm_generator: LLMGenerator = self._llm_generator(generator_id)
        # 工具装载
        tools: List[Tool] = []
        for mcp_name in mcp_name_list:
            tools.extend(await self.tools_port.load_tools(group_name=mcp_name, tool_type=ToolType.MCP))
        message_list = []
        message_list.append(ChatStreamingChunk.from_system(message=read("test_prompt.md")))
        message_list.append(ChatStreamingChunk.from_user(message=query))

        # chunk: ChatStreamingChunk = self.generators_port.generate(llm_generator=llm_generator, messages=message_list, tools=tools)
        chunk: ChatStreamingChunk = await self._tool_call(chunk_list=message_list, llm_generator=llm_generator,
                                                          tools=tools)

        return chunk.content

    async def _tool_call(self, chunk_list: [ChatStreamingChunk], llm_generator: LLMGenerator,
                         tools: List[Tool]) -> ChatStreamingChunk:
        chunk: ChatStreamingChunk = self.generators_port.generate(llm_generator=llm_generator, messages=chunk_list,
                                                                  tools=tools)
        if chunk.finish_reason == "tool_calls":
            # 上下文加入工具调用请求消息
            chunk_list.append(chunk)
            tool_task_list = []
            for tool_call in chunk.tool_calls:
                tool_task_list.append(
                    self.tools_port.call_tools(
                        self._get_tool_instances(tool_call.id, tool_call.name, tool_call.arguments, tools)))
                logger.info(f"需要调用工具：{tool_call.id}-{tool_call.name}-{tool_call.arguments}")
            # 并行方法调用
            results = await asyncio.gather(*tool_task_list)
            logger.debug(f"工具调用结果：{results}")
            for tool_call_result in results:
                chunk_list.append(ChatStreamingChunk.from_tool_calls_result(content=str(tool_call_result['result']),
                                                                            tool_call_id=tool_call_result['id']))
                return await self._tool_call(chunk_list, llm_generator, tools)

        return chunk

    async def generate_stream(
            self,
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
        query_str = None
        if isinstance(query, List):
            for item in query:
                if item.type == 'text':
                    query_str = item.content
        else:
            query_str = query
        # 会话检查
        conversation_id = self._conversation_check(conversation_id=conversation_id, query_str=query_str)
        # 对话片段id
        dialog_segment_id = create_uuid()
        # 用户输入对话片段id
        user_dialog_segment_id = create_uuid()
        # 保存用户输入
        user_dialog_segment = DialogSegment.make_user_message(
            content=query, conversation_id=conversation_id, id=user_dialog_segment_id)
        self.conversation_port.conversation_add(dialog_segment=user_dialog_segment)
        logger.info(f"保存用户对话片段：[ID：{user_dialog_segment.id} - 内容：{user_dialog_segment.content}]")
        # 清除会话的停止状态
        self.cache_port.set_data(name=CONVERSATION_STOP_FLAG_KEY, key=conversation_id, value=False)
        if agent_name:
            agent = self.agent_port.load_by_name(agent_name=agent_name)
            self._call_agent(agent_id=agent.id,
                             client_id=client_id,
                             conversation_id=conversation_id,
                             dialog_segment_id=dialog_segment_id,
                             generator_id=generator_id,
                             payload={"json_type": agent_name})
        else:
            if artifacts:
                system = read("adapter/setting/artifacts_prompt.md")
            event = Event.from_init(
                event_type=EventType.USER_MESSAGE,
                event_sub_type=EventSubType.MESSAGE,
                client_id=client_id,
                source=EventSource.GENERATOR_SVC,
                data={
                    "id": create_uuid(),
                    "dialog_segment_id": dialog_segment_id,
                    "conversation_id": conversation_id,
                    "generator_id": generator_id,
                },
                payload={
                    "system": system,
                    "json_result": artifacts,
                    "json_type": "artifacts" if artifacts else None,
                    "mcp_name_list": mcp_name_list,
                    "tools_group_name_list": tools_group_name_list,
                }
            )
            logger.info(
                f"[GeneratorService]发起[{EventType.USER_MESSAGE} - {EventSubType.MESSAGE}]事件：[ID：{event.id}]")
            self.event_port.emit_event(event)
        return conversation_id, dialog_segment_id, user_dialog_segment_id

    async def stop_generate(self, conversation_id: str, client_id: str) -> str:
        self.cache_port.set_data(name=CONVERSATION_STOP_FLAG_KEY, key=conversation_id, value=True)
        return conversation_id

    async def confirm(self, client_id: str, generator_id: str,
                      conversation_id: str, agent_instance_id: str,
                      dialog_segment_id: str, confirm_type: str,
                      content: Dict[str, str], ) -> Optional[str]:

        if "tools_execute" == confirm_type:
            if content['option'] == 'agree':
                # event = Event.from_init(
                #     client_id=client_id,
                #     event_type=EventType.TOOL,
                #     event_sub_type=EventSubType.TOOL_CALL,
                #     payload={},
                #     source=EventSource.LLM_HANDLER,
                #     data={
                #         "id": create_uuid(),
                #         "conversation_id": conversation_id,
                #         "dialog_segment_id": dialog_segment_id,
                #         "generator_id": generator_id,
                #         "model": content['model'],
                #         "created": create_from_second_now_to_int(),
                #         "tool_calls": content['tool_calls'],
                #     }
                # )
                # EventPort.get_event_port().emit_event(event)
                # 构建TOOL_CALL任务
                task = Task.from_singleton(
                    task_type=TaskType.TOOL_CALL,
                    data={
                        "id": create_uuid(),
                        "conversation_id": conversation_id,
                        "dialog_segment_id": dialog_segment_id,
                        "generator_id": generator_id,
                        "model": content['model'],
                        "created": create_from_second_now_to_int(),
                        "tool_calls": content['tool_calls'],
                    },
                    payload={"option": content['option']},
                client_id=client_id)
                TaskPort.get_task_port().execute_task(task)
                logger.info(f"事件处理器[GeneratorService]发起[{TaskType.TOOL_CALL}]任务：[ID：{task.id}]")
            return dialog_segment_id

        # ppt确认的逻辑
        if "ppt" == confirm_type:
            conversation = self.conversation_port.conversation_load(conversation_id)
            if not conversation:
                raise ValueError(f"未找到 conversation_id = {conversation_id} 的对话记录")
            updated = False
            segments = conversation.dialog_segment_list
            # 遍历查找要修改的 DialogSegment
            for segment in segments:
                if segment.id == dialog_segment_id:
                    # 将修改后的 html_code 赋值给 content
                    segment.content = content['html_code']
                    updated = True
                    break

            if not updated:
                logger.error(f"未找到 id={dialog_segment_id} 的对话片段")
                raise CommonException(error_code=CommonErrorCode.DIALOG_SEGMENT_NOT_FOUND,
                                      dynamics_message="dialog_segment_id: " + dialog_segment_id)
            # 将更新后的对话记录保存回文件
            self.conversation_port.update_conversation_record(conversation_id=conversation_id, updated_segments=segments)
            return conversation_id

    async def update_agent_log(self, agent_instance_id, content, dialog_segment_id):
        # 加载该 agent 实例的全部对话记录
        dialog_segments: List[DialogSegment] = self.conversation_port.load_agent_record(agent_instance_id)
        if not dialog_segments:
            raise ValueError(f"未找到 agent_instance_id={agent_instance_id} 的对话记录")
        updated = False
        # 遍历查找要修改的 DialogSegment
        for segment in dialog_segments:
            if segment.id == dialog_segment_id:
                try:
                    # 将 content 字符串解析为 JSON 对象
                    content_dict = json.loads(segment.content)

                    # 修改 html_code 字段
                    content_dict['html_code'] = content['html_code']

                    # 将修改后的 dict 转回字符串并赋值给 content
                    segment.content = json.dumps(content_dict, ensure_ascii=False)

                    updated = True
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"解析 content 字段失败：{e}")
                    raise CommonException(error_code=CommonErrorCode.DIALOG_SEGMENT_CONTENT_JSON_DECODE_ERROR,
                                          dynamics_message="segment.content: " + segment.content)
        if not updated:
            logger.error(f"未找到 id={dialog_segment_id} 的对话片段")
            raise CommonException(error_code=CommonErrorCode.DIALOG_SEGMENT_NOT_FOUND,
                                  dynamics_message="dialog_segment_id: " + dialog_segment_id)
        # 将更新后的对话记录保存回文件
        self.conversation_port.update_agent_record(agent_instance_id, dialog_segments)

    def _conversation_check(self, conversation_id: str, query_str: str) -> str:
        # 创建会话
        if not conversation_id:
            conversation = Conversation.init(conversation_type="chat")
            conversation.theme = query_str
            conversation.dialog_segment_list = []
            self.conversation_port.conversation_save(conversation=conversation)
            conversation_id = conversation.id
            logger.info(f"首次发送消息创建会话：[ID：{conversation.id} - 主题：{conversation.theme}]")
        else:
            logger.info(f"历史会话消息：[ID：{conversation_id}]")
        return conversation_id

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
    def _get_tool_instances(call_id: str, name: str, arg: str, tools: List[Tool]) -> Optional[ToolInstance]:
        """
        根据tools名字转换tools实例对象
        :param call_id: tools call id
        :param name: tools 名字
        :param arg: tools 调用参数
        :return: 工具实例对象
        """
        for tool in tools:
            if tool.name == name:
                tool_instance: ToolInstance = tool.instance()
                tool_instance.arguments = json.loads(arg)
                tool_instance.tool_call_id = call_id
                return tool_instance
        return None

    def _call_agent(
            self,
            agent_id: str,
            client_id: str,
            conversation_id: str,
            dialog_segment_id: str,
            generator_id: str,
            payload: Dict[str, Any]
    ):
        """Agent 调用方法"""
        # 创建并保存agent instance info 实体
        agent: Agent = self.agent_port.load(agent_id=agent_id)
        instance_id = self.cache_port.get_from_cache(CURRENT_CONVERSATION_AGENT_INSTANCE_ID, conversation_id)
        if not instance_id:
            instance_id = create_uuid()
            self.cache_port.set_data(CURRENT_CONVERSATION_AGENT_INSTANCE_ID, conversation_id, instance_id)

        agent_info: AgentInfo = agent.info(
            conversation_id=conversation_id,
            dialog_segment_id=dialog_segment_id,
            generator_id=generator_id,
            instance_id=instance_id
        )
        # 默认负载值
        payload['agent_instance_id'] = agent_info.instance_id
        # 保存
        self.agent_port.save_instance_info(instance_info=agent_info)
        event = Event.from_init(
            client_id=client_id,
            event_type=EventType.AGENT,
            event_sub_type=EventSubType.AGENT_CALL,
            source=EventSource.GENERATOR_SVC,
            payload=payload,
            data={
                "id": create_uuid(),
                "dialog_segment_id": dialog_segment_id,
                "conversation_id": conversation_id,
                "generator_id": generator_id,
                "content": f"call {agent_info.name} agent",
            },
        )
        logger.info(f"[TeamsService]发起[{EventType.AGENT} - {EventSubType.AGENT_CALL}]事件：[ID：{event.id}]")
        EventPort.get_event_port().emit_event(event)
