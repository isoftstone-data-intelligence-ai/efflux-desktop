from application.domain.events.event import EventType, Event, EventSubType, EventGroupStatus, EventSource
from application.domain.tasks.task import Task, TaskType
from application.port.inbound.event_handler import EventHandler
from application.port.outbound.task_port import TaskPort
from common.core.container.annotate import component
from application.port.outbound.ws_message_port import WsMessagePort
from application.port.outbound.tools_port import ToolsPort
from application.domain.events.event_collector import EventCollector
from application.port.outbound.conversation_port import ConversationPort
from application.domain.conversation import DialogSegment
from copy import deepcopy
from common.core.logger import get_logger
import injector
from typing import List, Dict, Any

from common.utils.common_utils import create_uuid

logger = get_logger(__name__)

@component
class AssistantMessageEventHandler(EventHandler):

    @injector.inject
    def __init__(self,
        ws_message_port: WsMessagePort,
        conversation_port: ConversationPort,
        tool_port: ToolsPort
        ):
        self.ws_message_port = ws_message_port
        self.conversation_port = conversation_port
        self.tool_port = tool_port

        # 确保事件收集器已初始化
        EventCollector.initialize(timeout_seconds=10)

        # self.aaa = ''

    def handle(self, event: Event) -> None:
        """
        处理接受LLM返回消息事件
        :param event:
        :return:
        """
        try:
            # 收集事件（如果是组事件）
            if event.group and event.group.id:
                # 如果是组开始事件，注册处理器
                if event.group.status == EventGroupStatus.STARTED:
                    EventCollector.register_group_handler(
                        event.group.id,
                        self._handle_message_group
                    )
                # # 组事件结尾是工具调用，手动处理为组事件结束
                if event.sub_type == EventSubType.TOOL_CALL:
                # if hasattr(event.data, 'type') and event.data.type == MessageEventDataType.TOOL_CALL:
                    event.group.status = EventGroupStatus.ENDED
                # 收集事件
                EventCollector.collect_event(event)

            # 如果是消息事件，发送到WebSocket
            if event.sub_type == EventSubType.MESSAGE:
                # self.aaa += event.data['content']
                # logger.warning(f"发送消息测试：{event}")
                self.ws_message_port.send(event)
        except Exception as e:
            logger.exception(f"[{EventType.ASSISTANT_MESSAGE.value}] 事件[{event.id}]处理异常")
            logger.error(f"[{EventType.ASSISTANT_MESSAGE.value}]事件[{event.id}]处理异常[{e}]")
        # 注意同步方法中的执行的异步方法，后续的逻辑无法保证事件的顺序性
    
    def _handle_message_group(self, group_id: str, events: List[Event]):
        """
        处理消息事件组
        :param group_id: 组ID
        :param events: 事件列表
        """
        # 按照消息ID分组，但保持每个消息ID内的事件顺序
        message_groups = {}
        for event in events:
            if event.sub_type == EventSubType.MESSAGE:
                message_id = event.data['id']
                if message_id not in message_groups:
                    message_groups[message_id] = []
                message_groups[message_id].append(event)
        
        # 处理每个消息组
        for message_id, message_events in message_groups.items():
            # 合并消息内容，按照事件的原始顺序
            full_content = ""
            full_reasoning_content = ""
            for event in message_events:
                if event.data['content']:
                    full_content += event.data['content']
                if event.data['reasoning_content']:
                    full_reasoning_content += event.data['reasoning_content']
            if len(message_events) > 0:
                copy_last_event = deepcopy(message_events[-1])
                copy_last_event.data['content'] = full_content
                copy_last_event.data['reasoning_content'] = full_reasoning_content
                # 保存完整消息到会话历史
                logger.info(f"组事件[{group_id}]结束，结果：{copy_last_event.group} - {copy_last_event.data['content']}")
                if copy_last_event.group.status == EventGroupStatus.ENDED: # 只保存正常结束的组消息
                    # if copy_last_event.data['content']: # 连续调用工具，可能消息内容为空
                    assistant_dialog_segment = DialogSegment.make_assistant_message(
                        conversation_id=copy_last_event.data['conversation_id'], id=copy_last_event.data['dialog_segment_id'],
                        content=copy_last_event.data['content'], reasoning_content=copy_last_event.data['reasoning_content'],
                        model=copy_last_event.data['model'], firm=copy_last_event.data['firm'], timestamp=copy_last_event.data['created'], payload=copy_last_event.payload)
                    agent_instance_id = copy_last_event.payload['agent_instance_id'] if 'agent_instance_id' in copy_last_event.payload else None
                    if agent_instance_id:
                        # TODO 暂不处理 agent调用的结果保存
                        # assistant_dialog_segment.payload = {"agent_instance_id": agent_instance_id}
                        # self.conversation_port.add_agent_record(dialog_segment=assistant_dialog_segment)
                        # 创建agent call任务
                        task = Task.from_singleton(task_type=TaskType.AGENT_CALL, data=copy_last_event.data,
                                                   payload=copy_last_event.payload,
                                                   client_id=copy_last_event.client_id)
                        TaskPort.get_task_port().execute_task(task)
                        logger.info(
                            f"组事件[{group_id}]JSON结果发送->Agent[{agent_instance_id}]")
                    else:
                        self.conversation_port.conversation_add(dialog_segment=assistant_dialog_segment)

    def type(self) -> str:
        return EventType.ASSISTANT_MESSAGE.value