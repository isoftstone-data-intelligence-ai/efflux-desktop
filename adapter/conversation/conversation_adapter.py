from pydantic import BaseModel
from typing import List, Dict, Optional
import jsonlines
from common.utils.file_util import check_file_and_create, del_file, check_file
from common.core.container.annotate import component
from application.domain.conversation import Conversation, DialogSegment
from application.port.outbound.conversation_port import ConversationPort

@component
class ConversationAdapter(ConversationPort):

    def conversation_update(self, conversation: Conversation) -> Optional[Conversation]:
        conversation_file = f'conversations/conversations_list.jsonl'
        updated = False
        updated_conversations = []  # 用于存储更新后的会话对象
        with jsonlines.open(conversation_file, mode='r') as reader:
            # 读取所有现有的会话对象
            for obj in reader:
                old_conversation = Conversation.model_validate(obj)
                if old_conversation and conversation.id == old_conversation.id:
                    # 更新目标会话对象
                    old_conversation.theme = conversation.theme
                    updated = True
                # 将修改后的会话对象添加到列表中
                updated_conversations.append(old_conversation)
        # 如果找到了匹配的会话并进行了更新
        if updated:
            # 将所有更新后的会话重新写入到 JSONL 文件
            with jsonlines.open(conversation_file, mode='w') as writer:
                for updated_conversation in updated_conversations:
                    writer.write(updated_conversation.model_dump())  # 将对象写为字典
            return conversation  # 返回更新后的会话对象
        else:
            return None  # 如果没有找到匹配的会话对象，则返回 None


    def conversation_add(self, dialog_segment: DialogSegment) -> DialogSegment:
        dialog_segment_file = f'conversations/{dialog_segment.conversation_id}.jsonl'
        check_file_and_create(dialog_segment_file)
        with jsonlines.open(dialog_segment_file, mode='a') as writer:
            writer.write(dialog_segment.model_dump())
        return dialog_segment

    def conversation_insert(self, dialog_segment: DialogSegment, index: int) -> DialogSegment:
        dialog_segment_file = f'conversations/{dialog_segment.conversation_id}.jsonl'
        # 读取原文件所有行
        with jsonlines.open(dialog_segment_file, mode='r') as reader:
            data = list(reader)  # data 是一个包含所有 JSON 对象的列表
        # 插入到倒数第二行
        data.insert(index, dialog_segment.model_dump())  # 插入到倒数第二行
        # 重新写入整个文件（覆盖）
        with jsonlines.open(dialog_segment_file, mode='w') as writer:
            writer.write_all(data)
        return dialog_segment


    def dialog_segment_remove(self, conversation_id: str, dialog_segment_id: str) -> str:
        dialog_segment_file = f'conversations/{conversation_id}.jsonl'
        segments = []

        # 读取现有对话段
        with jsonlines.open(dialog_segment_file, mode='r') as reader:
            for obj in reader:
                # 将对象转换为 DialogSegment
                history_dialog_segment = DialogSegment.model_validate(obj)
                # 检查 ID，跳过待删除的段
                if history_dialog_segment.id != dialog_segment_id:
                    segments.append(history_dialog_segment)

        # 重写文件，排除待删除的段
        with jsonlines.open(dialog_segment_file, mode='w') as writer:
            if len(segments) == 1: # 对话片段仅为一条的时候删除会话
                self.conversation_remove(conversation_id=conversation_id)
            else:
                for segment in segments:
                    writer.write(segment.model_dump())  # 写入更新后的数据

        return dialog_segment_id

    def dialog_segment_find(self, conversation_id: str, dialog_segment_id) -> Optional[DialogSegment]:
        dialog_segment_file = f'conversations/{conversation_id}.jsonl'

        # 读取现有对话段
        with jsonlines.open(dialog_segment_file, mode='r') as reader:
            for obj in reader:
                # 将对象转换为 DialogSegment
                history_dialog_segment = DialogSegment.model_validate(obj)
                # 检查 ID，跳过待删除的段
                if history_dialog_segment.id == dialog_segment_id:
                    return history_dialog_segment

        return None

    def update_conversation_record(self, conversation_id: str, updated_segments: List[DialogSegment]):
            dialog_segment_file = f'conversations/{conversation_id}.jsonl'
            # 写入更新后的记录
            with jsonlines.open(dialog_segment_file, mode='w') as writer:
                for segment in updated_segments:
                    writer.write(segment.model_dump())

    def load_agent_record(self, agent_instance_id: str) -> List[DialogSegment]:
        dialog_segment_list = []
        dialog_segment_file = f'conversations/agent/{agent_instance_id}.jsonl'
        if not check_file(dialog_segment_file): # 不存在，返回空列表
            return dialog_segment_list
        with jsonlines.open(dialog_segment_file, mode='r') as reader:
            for obj in reader:
                dialog_segment_list.append(DialogSegment.model_validate(obj))
        return dialog_segment_list

    def update_agent_record(self, agent_instance_id: str, updated_segments: List[DialogSegment]):
            dialog_segment_file = f'conversations/agent/{agent_instance_id}.jsonl'
            # 写入更新后的记录
            with jsonlines.open(dialog_segment_file, mode='w') as writer:
                for segment in updated_segments:
                    writer.write(segment.model_dump())

    def add_agent_record(self, dialog_segment: DialogSegment) -> DialogSegment:
        dialog_segment_file = f'conversations/agent/{dialog_segment.payload['agent_instance_id']}.jsonl'
        check_file_and_create(dialog_segment_file)
        with jsonlines.open(dialog_segment_file, mode='a') as writer:
            for key, value in dialog_segment.payload.items():
                if isinstance(value, BaseModel):
                    dialog_segment.payload[key] = value.model_dump()
            writer.write(dialog_segment.model_dump())
        return dialog_segment

    def conversation_save(self, conversation: Conversation) -> Conversation:
        conversation_file = f'conversations/conversations_list.jsonl'
        check_file_and_create(conversation_file)
        with jsonlines.open(conversation_file, mode='a') as writer:
            writer.write(conversation.model_dump())
        return conversation

    def conversation_load(self, conversation_id: str) -> Optional[Conversation]:
        conversation_file = f'conversations/conversations_list.jsonl'
        conversation: Optional[Conversation] = None
        with jsonlines.open(conversation_file, mode='r') as reader:
            for obj in reader:
                if obj.get("id") == conversation_id:
                    conversation = Conversation.model_validate(obj)
        if not conversation:
            return None

        dialog_segment_file = f'conversations/{conversation_id}.jsonl'
        with jsonlines.open(dialog_segment_file, mode='r') as reader:
            for obj in reader:
                conversation.dialog_segment_list.append(DialogSegment.model_validate(obj))
        return conversation


    def conversation_load_list(self) -> List[Conversation]:
        conversation_file = f'conversations/conversations_list.jsonl'
        conversation_list: List[Conversation] = []
        check_file_and_create(conversation_file)
        with jsonlines.open(conversation_file, mode='r') as reader:
            for obj in reader:
                conversation = Conversation.model_validate(obj)
                if conversation:
                    # 获取最后一条片段,用于列表展示
                    dialog_segment_file = f'conversations/{conversation.id}.jsonl'
                    if check_file(dialog_segment_file):
                        with jsonlines.open(dialog_segment_file, mode='r') as sub_reader:
                            dialog_segment_obj = None
                            for sub_obj in sub_reader:
                                dialog_segment_obj = sub_obj
                            if dialog_segment_obj:
                                conversation.last_dialog_segment = DialogSegment.model_validate(dialog_segment_obj)
                        conversation_list.append(conversation)
        return conversation_list

    def conversation_remove(self, conversation_id: str) -> str:
        conversation_file = f'conversations/conversations_list.jsonl'
        conversations = []
        # 读取 conversations_list.jsonl 文件并过滤掉指定的 conversation_id
        with jsonlines.open(conversation_file, mode='r') as reader:
            for obj in reader:
                conversation = Conversation.model_validate(obj)
                if conversation.id != conversation_id:
                    conversations.append(conversation)
        # 写回更新后的 conversations_list.jsonl 文件
        with jsonlines.open(conversation_file, mode='w') as writer:
            for conversation in conversations:
                writer.write(conversation.model_dump())
        dialog_segment_file = f'conversations/{conversation_id}.jsonl'
        # 删除 dialog_segment_file 文件
        del_file(dialog_segment_file)
        return conversation_id
