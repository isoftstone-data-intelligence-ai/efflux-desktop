from typing import Optional, Dict, Any, Iterable, List, Generator, Literal, get_origin
import os
import re
import json
from anthropic import Anthropic
from anthropic.types import MessageParam, ToolUnionParam, Message
import anthropic
from adapter.model_sdk.client import ModelClient
from application.domain.generators.generator import LLMGenerator
from common.utils.auth import Secret
from common.utils.time_utils import create_from_second_now_to_int
from common.core.errors.system_exception import ThirdPartyServiceException, ThirdPartyServiceApiCode
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk, ChatCompletionMessageToolCall
from application.domain.generators.tools import Tool

from common.core.logger import get_logger
logger = get_logger(__name__)

class AnthropicClient(ModelClient):

    def __init__(self):
        self.timeout = float(os.environ.get("ANTHROPIC_TIMEOUT", 180.0)) # 接口超时时间
        self.max_retries = int(os.environ.get("ANTHROPIC_MAX_RETRIES", 3)) # 接口最啊重试次数

        self.default_tool_choice: str = "auto" # 默认工具调用模式

    def model_list(self, api_key: str = None, base_url: str = None)-> List[LLMGenerator]:
        # Anthropic client 构建
        client: Anthropic = self._get_client(api_key=api_key,
                                          api_base_url=base_url)

        generators: List[LLMGenerator] = []
        for model in client.models.list():
            generator = LLMGenerator.from_disabled(
                firm="anthropic",
                model=model.id
            )
            generators.append(generator)
        return generators


    def generate(
            self,
            model: str = None,
            message_list: Iterable[ChatStreamingChunk] = None,
            api_secret: Secret = None,
            base_url: str = None,
            tools: Optional[Iterable[Tool]] = None,
            **generation_kwargs,
    ) -> ChatStreamingChunk:
        # openAI client 构建
        client: Anthropic = self._get_client(api_key=api_secret.resolve_value(),
                                          api_base_url=base_url)
        # 转换为 Anthropic 接口风格的工具
        anthropic_tools: List[ToolUnionParam] = self._convert_openai_tools(tools)

        system_instruction = self._convert_anthropic_system_instruction(chat_streaming_chunk_list=message_list)
        if system_instruction:
            logger.debug(f"system_instruction: {system_instruction}")

        try:
            if len(anthropic_tools) > 0:
                tool_choice = self._tool_choice(generation_kwargs=generation_kwargs)
                response = client.messages.create(
                    model=model,
                    max_tokens=128000,
                    messages=self._convert_claude_stream_chunk(message_list),
                    system=system_instruction if system_instruction else None,
                    tools=anthropic_tools,
                    tool_choice={"type": tool_choice},
                )
            else:
                response = client.messages.create(
                    model=model,
                    max_tokens=128000,
                    messages=self._convert_claude_stream_chunk(message_list),
                    system=system_instruction if system_instruction else None,
                )
            return self._convert_chunk(response)
        except Exception as exc:
            # 抛出三方调用异常
            raise ThirdPartyServiceException(error_code=ThirdPartyServiceApiCode.LLM_SERVICE_API_ERROR, dynamics_message=f"model:{model} - exception:{str(exc)}")


    @staticmethod
    def _convert_chunk(completion: Message) -> ChatStreamingChunk:

        return ChatStreamingChunk.from_assistant(id=completion.id, model=completion.model, created=completion.created,
                                                 content=completion.choices[0].message.content,
                                                 finish_reason=completion.choices[0].finish_reason,
                                                 reasoning_content=None if not hasattr(completion.choices[0].message, "reasoning_content") else completion.choices[0].message.reasoning_content,
                                                 role=completion.choices[0].message.role,
                                                 tool_calls=[])

    def generate_test(self,
                      model: str = None,
                      message_list: Iterable[ChatStreamingChunk] = None,
                      api_secret: Secret = None,
                      base_url: str = None,
                      tools: Optional[List[Tool]] = None,
                      **generation_kwargs,
                      ):
        # Anthropic client 构建
        client: Anthropic = self._get_client(api_key=api_secret.resolve_value(),
                                          api_base_url=base_url)

        # 转换为 Anthropic 接口风格的工具
        # anthropic_tools: List[ToolUnionParam] = self._convert_openai_tools(tools)

        with client.messages.stream(
            model=model,
            max_tokens=128000,
            messages=self._convert_openai_stream_chunk(message_list),
            # tools=anthropic_tools,
            # tool_choice={"type": "none"},
        ) as stream:
            for event in stream:
                logger.debug("============================================================================================")
                logger.debug(f"原始chunk - {event.type} 返回：{event}")

                logger.debug("============================================================================================")

    def generate_stream(
            self,
            model: str = None,
            message_list: Iterable[ChatStreamingChunk] = None,
            api_secret: Secret = None,
            base_url: str = None,
            tools: Optional[List[Tool]] = None,
            **generation_kwargs,
    ) -> Generator[ChatStreamingChunk, None, None]:
        # Anthropic client 构建
        client: Anthropic = self._get_client(api_key=api_secret.resolve_value(),
                                          api_base_url=base_url)
        # 转换为 Anthropic 接口风格的工具
        anthropic_tools: List[ToolUnionParam] = self._convert_openai_tools(tools)

        system_instruction = self._convert_anthropic_system_instruction(chat_streaming_chunk_list=message_list)
        if system_instruction:
            logger.debug(f"system_instruction: {system_instruction}")

        try:
            if len(anthropic_tools) > 0:
                tool_choice = self._tool_choice(generation_kwargs=generation_kwargs)
                response = client.messages.stream(
                        model=model,
                        max_tokens=generation_kwargs["output_token_limit"] if "output_token_limit" in generation_kwargs else 8192,
                        stop_sequences=['end_turn'],
                        messages=self._convert_claude_stream_chunk(message_list),
                        system=system_instruction if system_instruction else None,
                        tools=anthropic_tools,
                        tool_choice={"type": tool_choice},
                )
            else:
                response = client.messages.stream(
                    model=model,
                    max_tokens=generation_kwargs["output_token_limit"] if "output_token_limit" in generation_kwargs else 8192,
                    messages=self._convert_claude_stream_chunk(message_list),
                    system=system_instruction if system_instruction else None,
                )
            with response as stream:
                message_id = None
                model_name = None
                role = None
                for event in stream:
                    logger.debug(f"原始chunk返回：{event}")
                    logger.debug("============================================================================================")
                    if event.type == 'message_start':
                        message_id = event.message.id
                        model_name = event.message.model
                        role = event.message.role
                    if event.type == 'text':
                        chat_streaming_chunk: ChatStreamingChunk = ChatStreamingChunk.from_assistant(
                            id=message_id, model=model_name, created=create_from_second_now_to_int(),
                            content=event.text, finish_reason=None, reasoning_content="", role=role, tool_calls=[])
                        yield chat_streaming_chunk
                    if event.type == 'content_block_stop' and event.content_block.type == 'text': #文本结束标识
                        chat_streaming_chunk: ChatStreamingChunk = ChatStreamingChunk.from_assistant(
                            id=message_id, model=model_name, created=create_from_second_now_to_int(),
                            content="", finish_reason="stop", reasoning_content="", role=role, tool_calls=[])
                        yield chat_streaming_chunk
                    if event.type == 'content_block_stop' and event.content_block.type == 'tool_use': #工具调用结束标识
                        current_tool = ChatCompletionMessageToolCall(id=event.content_block.id,
                                                                     name=event.content_block.name,
                                                                     arguments=json.dumps(event.content_block.input))
                        self._match_mcp_server_name(chunk_tools_call=current_tool, tools=tools)
                        chat_streaming_chunk: ChatStreamingChunk = ChatStreamingChunk.from_tool_calls(tool_calls=[current_tool])
                        yield chat_streaming_chunk
                    if event.type == 'message_stop' and event.message.stop_reason == 'stop_sequence' and event.message.stop_sequence == '<antml:function_calls>':
                        logger.error(f"意外中断")
                        # yield from self.generate_stream(model=model, message_list=message_list, api_secret=api_secret, base_url=base_url, tools=tools, **generation_kwargs)
        except Exception as exc:
            # 抛出三方调用异常
            raise ThirdPartyServiceException(error_code=ThirdPartyServiceApiCode.LLM_SERVICE_API_ERROR, dynamics_message=f"model:{model} - exception:{str(exc)}")


    @staticmethod
    def _convert_anthropic_system_instruction(chat_streaming_chunk_list: Iterable[ChatStreamingChunk]) -> Optional[str]:
        """转换gemini的system_instruction"""
        system_instruction = ""
        for chat_streaming_chunk in chat_streaming_chunk_list:
            if chat_streaming_chunk.role == "system":
                system_instruction += chat_streaming_chunk.content
        return system_instruction


    def _convert_claude_stream_chunk(self, chat_streaming_chunk_list: Iterable[ChatStreamingChunk]) -> List[MessageParam]:
        """转换claude的chunk输入"""
        message_list: List[MessageParam] = []
        for chat_streaming_chunk in chat_streaming_chunk_list:
            if chat_streaming_chunk.role == "system":
                continue
            # 工具调用请求
            if chat_streaming_chunk.role == "assistant" and chat_streaming_chunk.finish_reason == "tool_calls":
                # 封装tool_calls集合
                tool_calls = []
                for tool_call in chat_streaming_chunk.tool_calls:
                    tool_calls.append(
                        {
                            "input": json.loads(tool_call.arguments),
                            "name": tool_call.name,
                            "id": tool_call.id,
                            "type": "tool_use"
                        }
                    )
                message_list.append({
                    "role": "assistant",
                    "content": tool_calls
                })
            # 工具调用结果
            elif chat_streaming_chunk.role == "tool":
                dict_array = json.loads(chat_streaming_chunk.content)
                results = []
                for dict_str in dict_array:
                    result_dict = json.loads(dict_str)
                    if 'annotations' in result_dict:
                        del result_dict['annotations']
                    results.append(result_dict)
                message_list.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": chat_streaming_chunk.tool_call_id,
                                "content": results
                            }
                        ]
                    }
                )
            # 一般消息
            else:
                if not isinstance(chat_streaming_chunk.content, str):  # 包含图片
                    content = []
                    for content_part in chat_streaming_chunk.content:
                        if content_part.type == "text":
                            content.append({"type": "text", "text": content_part.text})
                        if content_part.type == "image_url":
                            mime_type, encoding, base64_data = self._get_base64_meta(content_part.image_url.url)
                            content.append({
                                "type": "image",
                                "source": {
                                    "type": encoding,
                                    "media_type": mime_type,
                                    "data": base64_data
                                }
                            })
                    message = {"role": chat_streaming_chunk.role, "content": content}
                else:
                    message = {"role": chat_streaming_chunk.role, "content": chat_streaming_chunk.content}
                message_list.append(message)
        logger.debug(f"claude-api-message-list：{message_list}")
        return message_list


    @staticmethod
    def _match_mcp_server_name(chunk_tools_call: ChatCompletionMessageToolCall, tools: Iterable[Tool]) -> None:
        """
        match mcp.server name and description
        :param chunk_tools_call: the call tools
        :param tools: mcp server tools
        :return:
        """
        for tool in tools:
            if chunk_tools_call.name == tool.name:
                chunk_tools_call.mcp_server_name = tool.mcp_server_name
                chunk_tools_call.group_name = tool.group_name
                chunk_tools_call.description = tool.description

    @staticmethod
    def _convert_openai_tools(tools: Iterable[Tool]) -> List[ToolUnionParam]:
        """
        convert anthropic param tools into a list of efflux tools
        :param tools:
        :return:
        """
        openai_tools: List[ToolUnionParam] = []
        for tool in tools:
            tool_dist = tool.model_dump()
            if "mcp_server_name" in tool_dist:
                del tool_dist["mcp_server_name"]
            if "group_name" in tool_dist:
                del tool_dist["group_name"]
            if "type" in tool_dist:
                del tool_dist["type"]
            # if "input_schema" in tool_dist:
            #     tool_dist["parameters"] = tool_dist["input_schema"]
            #     del tool_dist["input_schema"]
            openai_tools.append(tool_dist)

        return openai_tools

    @staticmethod
    def _tool_choice(**generation_kwargs) -> Literal["none", "auto", "any"]:
        tool_choice: Literal["none", "auto", "any"] = "auto"
        if "tool_choice" in generation_kwargs.keys():
            tool_choice = generation_kwargs["tool_choice"]
        return tool_choice

    @staticmethod
    def _get_base64_meta(data_url: str):
        # 使用正则表达式提取 MIME 类型, 编码方式和 Base64 数据
        pattern = r"data:(?P<mime_type>.*?);(?P<encoding>.*?),(?P<data>.*)"
        match = re.match(pattern, data_url)

        if match:
            mime_type = match.group("mime_type")
            encoding = match.group("encoding")
            base64_data = match.group("data")

            # 输出提取结果
            print("MIME Type:", mime_type)
            print("Encoding:", encoding)
            print("Base64 Data:", base64_data)
            return mime_type, encoding, base64_data
        else:
            print("Invalid data URL format.")

    def _get_client(
            self,
            api_key: str,
            api_base_url: str,
            organization: str = None,
            timeout: float = None,
            max_retries: int = None
    ) -> Anthropic:
        """
        get an Anthropic API client
        :param api_key: api key
        :param api_base_url: api base url
        :param organization: organization
        :param timeout: timeout
        :param max_retries: max retries
        :return:
        """
        if timeout is not None:
            self.timeout = timeout
        if max_retries is not None:
            self.max_retries = max_retries

        return anthropic.Anthropic(
            api_key=api_key,
            base_url=api_base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )