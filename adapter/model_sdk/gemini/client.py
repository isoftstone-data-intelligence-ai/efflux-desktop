from typing import Iterable, Optional, List, Generator, Iterator

from google.genai import types, Client
from google.genai.types import Content, Part, FunctionDeclaration, GenerateContentResponse, Candidate

from adapter.model_sdk.client import ModelClient
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk, ChatCompletionContentPartParam, \
    ChatCompletionMessageToolCall
from application.domain.generators.generator import LLMGenerator
from application.domain.generators.tools import Tool
from common.utils.auth import Secret
from common.utils.common_utils import create_uuid
from common.utils.time_utils import create_from_timestamp_to_int, create_from_second_now_to_int
import re
import json

from common.core.logger import get_logger

logger = get_logger(__name__)


class GeminiClient(ModelClient):
    def generate(
        self,
        model: str = None,
        message_list: Iterable[ChatStreamingChunk] = None,
        api_secret: Secret = None,
        base_url: str = None,
        tools: Optional[List[Tool]] = None,
        **generation_kwargs) -> ChatStreamingChunk:
        pass

    def generate_stream(
        self,
        model: str = None,
        message_list: Iterable[ChatStreamingChunk] = None,
        api_secret: Secret = None,
        base_url: str = None,
        tools: Optional[List[Tool]] = None,
        **generation_kwargs) -> Generator[ChatStreamingChunk, None, None]:

        client = self._get_client(api_key=api_secret.resolve_value(), base_url=base_url)

        system_instruction = self._convert_gemini_system_instruction(chat_streaming_chunk_list=message_list)
        if system_instruction:
            logger.debug(f"system_instruction: {system_instruction}")
        gemini_tools = None
        if tools:
            gemini_tools = self._convert_gemini_tools(tools=tools)

        response_mime_type = "text/plain"
        if "json_object" in generation_kwargs.keys() and generation_kwargs["json_object"]:
            response_mime_type = "application/json"

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_budget=2048,  # 范围 0-16384。默认 1024，最佳边际效果 16000
            ),
            max_output_tokens=generation_kwargs["output_token_limit"] if "output_token_limit" in generation_kwargs else 8192,
            response_mime_type=response_mime_type,
            system_instruction=system_instruction if system_instruction else None,
            tools=[gemini_tools] if gemini_tools else None,
        )

        content_list = self._convert_gemini_stream_chunk(chat_streaming_chunk_list=message_list)

        if tools:
            self._convert_gemini_tools(tools=tools)

        response: Iterator[GenerateContentResponse] = client.models.generate_content_stream(
            model=model,
            contents=content_list,
            config=generate_content_config,
        )

        for chunk in response:
            logger.debug(f"原始chunk返回：{chunk}")
            logger.debug("============================================================================================")
            # if chunk.usage_metadata:
            #     logger.debug(f"跳过用量：{chunk.usage_metadata}")
            #     continue
            if chunk.function_calls: # tools调用要先返回一个空的stop标识chunk
                yield self._convert_efflux_stream_chunk(model=model, stop_flag=True)
                yield self._convert_efflux_stream_chunk(content_response=chunk, tools=tools)
            else:
                yield  self._convert_efflux_stream_chunk(content_response=chunk)


    def generate_test(self, model: str = None, message_list: Iterable[ChatStreamingChunk] = None,
                      api_secret: Secret = None, base_url: str = None, tools: Optional[List[Tool]] = None,
                      **generation_kwargs):
        client = self._get_client(api_key=api_secret.resolve_value(), base_url=base_url)

        system_instruction = self._convert_gemini_system_instruction(chat_streaming_chunk_list=message_list)
        if system_instruction:
            logger.debug(f"system_instruction: {system_instruction}")
        gemini_tools = None
        if tools:
            gemini_tools = self._convert_gemini_tools(tools=tools)

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_budget=2048,  # 范围 0-16384。默认 1024，最佳边际效果 16000
            ),
            response_mime_type="text/plain",
            system_instruction=system_instruction if system_instruction else None,
            tools=[gemini_tools] if gemini_tools else None,
        )

        content_list = self._convert_gemini_stream_chunk(chat_streaming_chunk_list=message_list)

        if tools:
            self._convert_gemini_tools(tools=tools)

        rs = ""

        response: Iterator[GenerateContentResponse] = client.models.generate_content_stream(
                model=model,
                contents=content_list,
                config=generate_content_config,
        )
        for chunk in response:
            print(chunk)
            self._convert_efflux_stream_chunk(chunk)
            if chunk.text:
                rs += chunk.text
        print(rs)

    def model_list(
        self,
        api_key: str = None,
        base_url: str = None
    )-> List[LLMGenerator]:
        client: Client = self._get_client(api_key=api_key, base_url=base_url)
        generators: List[LLMGenerator] = []
        for model in client.models.list():
            generator = LLMGenerator.from_disabled(
                firm="google",
                model=model.name.replace('models/', '', 1),
                metadata={
                    #"input_token_limit": model.input_token_limit,
                    "output_token_limit": model.output_token_limit
                }
            )
            ttt = {
                model.name.replace('models/', '', 1): model.output_token_limit
            }
            print(ttt)
            generators.append(generator)
        return generators

    @staticmethod
    def _convert_gemini_system_instruction(chat_streaming_chunk_list: Iterable[ChatStreamingChunk]) -> Optional[str]:
        """转换gemini的system_instruction"""
        system_instruction = ""
        for chat_streaming_chunk in chat_streaming_chunk_list:
            if chat_streaming_chunk.role == "system":
                system_instruction += chat_streaming_chunk.content
        return system_instruction

    @staticmethod
    def _convert_gemini_tools(tools: Iterable[Tool]) -> types.Tool:
        """
        convert gemini param tools into a list of efflux tools
        :param tools:
        :return:
        """
        gemini_tools: List[FunctionDeclaration] = []
        for tool in tools:
            tool_dist = tool.model_dump()
            if "mcp_server_name" in tool_dist:
                del tool_dist["mcp_server_name"]
            if "group_name" in tool_dist:
                del tool_dist["group_name"]
            if "type" in tool_dist:
                del tool_dist["type"]
            if "input_schema" in tool_dist:
                tool_dist["parameters"] = tool_dist["input_schema"]
                del tool_dist["input_schema"]
            gemini_tools.append(
                FunctionDeclaration.model_validate(tool_dist)
                # {
                #     "name": tool.name,
                #     "description": tool.description,
                #     "parameters": {
                #         "type": "object",
                #         "properties": {
                #             "brightness": {
                #                 "type": "integer",
                #                 "description": "Light level from 0 to 100. Zero is off and 100 is full brightness",
                #             },
                #             "color_temp": {
                #                 "type": "string",
                #                 "enum": ["daylight", "cool", "warm"],
                #                 "description": "Color temperature of the light fixture, which can be `daylight`, `cool` or `warm`.",
                #             },
                #         },
                #         "required": ["brightness", "color_temp"],
                #     }
                # }
            )
        return types.Tool(function_declarations=gemini_tools)

    def _convert_efflux_stream_chunk(
            self,
            content_response: Optional[GenerateContentResponse] = None,
            tools: Optional[List[Tool]] = None,
            model: Optional[str] = None,
            stop_flag: Optional[bool] = False
    ) -> Optional[ChatStreamingChunk]:
        chunk_finish_reason = None
        if stop_flag:
            return ChatStreamingChunk.from_assistant(
                id=create_uuid(),
                model=model,
                created=create_from_second_now_to_int(),
                finish_reason="stop",
                role="assistant",
                content='',
                reasoning_content='',
            )
        else:
            if content_response.function_calls:
                print(f"====={content_response.function_calls}")
                chunk_tools: List[ChatCompletionMessageToolCall] = []
                for function_call in content_response.function_calls:
                    chunk_tools_call = ChatCompletionMessageToolCall(
                        id=function_call.id,
                        name=function_call.name,
                        arguments=json.dumps(function_call.args),
                    )
                    # 匹配mcp-server-name
                    self._match_mcp_server_name(chunk_tools_call=chunk_tools_call, tools=tools)
                    chunk_tools.append(chunk_tools_call)
                return ChatStreamingChunk.from_assistant(
                    id=content_response.response_id if content_response.response_id else create_uuid(),
                    model=content_response.model_version,
                    created=create_from_timestamp_to_int(
                        content_response.create_time) if content_response.create_time else create_from_second_now_to_int(),
                    finish_reason="tool_calls",
                    role="assistant",
                    content="",
                    reasoning_content="",
                    tool_calls=chunk_tools
                )
            else:
                candidate: Candidate = content_response.candidates[0]
                if candidate.content.parts:
                    part: Part = candidate.content.parts[0]
                    if candidate.finish_reason:
                        chunk_finish_reason = candidate.finish_reason.name.lower()
                    return ChatStreamingChunk.from_assistant(
                        id=content_response.response_id if content_response.response_id else create_uuid(),
                        model=content_response.model_version,
                        created=create_from_timestamp_to_int(content_response.create_time) if content_response.create_time else create_from_second_now_to_int(),
                        finish_reason=chunk_finish_reason,
                        role="assistant" if candidate.content.role == "model" else content_response.role,
                        content=part.text if not part.thought else None,
                        reasoning_content=part.text if part.thought else None,
                    )
                else:
                    if candidate.finish_reason:
                        chunk_finish_reason = candidate.finish_reason.name.lower()
                    return ChatStreamingChunk.from_assistant(
                        id=content_response.response_id if content_response.response_id else create_uuid(),
                        model=content_response.model_version,
                        created=create_from_timestamp_to_int(content_response.create_time) if content_response.create_time else create_from_second_now_to_int(),
                        finish_reason=chunk_finish_reason,
                        role="assistant" if candidate.content.role == "model" else content_response.role,
                        content="",
                        reasoning_content="",
                    )


    def _convert_gemini_stream_chunk(self, chat_streaming_chunk_list: Iterable[ChatStreamingChunk]) -> List[Content]:
        """转换gemini的chunk输入"""
        message_list: List[Content] = []
        for chat_streaming_chunk in chat_streaming_chunk_list:
            role = ""
            if chat_streaming_chunk.role == "user":
                role = "user"
            if chat_streaming_chunk.role == "assistant":
                role = "model"
            if chat_streaming_chunk.role == "system":
                continue
            # 工具调用请求
            if chat_streaming_chunk.role == "assistant" and chat_streaming_chunk.finish_reason == "tool_calls":
                continue
            #     # 封装tool_calls集合
            #     tool_calls = []
            #     for tool_call in chat_streaming_chunk.tool_calls:
            #         tool_calls.append(
            #             {
            #                 "function": {
            #                     "arguments": tool_call.arguments,
            #                     "name": tool_call.name
            #                 },
            #                 "id": tool_call.id,
            #                 "type": "function"
            #             }
            #         )
            #     message_list.append({
            #         "role": "assistant",
            #         "tool_calls": tool_calls
            #     })
            # 工具调用结果
            if chat_streaming_chunk.role == "tool":
                parts = []
                for tool_call in chat_streaming_chunk.tool_calls:
                    function_response_part = types.Part.from_function_response(
                        name=tool_call.name,
                        response={"result": chat_streaming_chunk.content},
                    )
                    parts.append(function_response_part)
                message_list.append(types.Content(role="user", parts=parts))
            # 一般消息
            else:
                if not isinstance(chat_streaming_chunk.content, str): # 包含图片
                    message = types.Content(
                        role=role,
                        parts=self._convert_chunk_content_part(chat_streaming_chunk.content)
                    )
                else:
                    message = types.Content(
                        role = role,
                        parts=[
                            types.Part.from_text(text=chat_streaming_chunk.content),
                        ],
                    )
                message_list.append(message)
        logger.debug(f"gemini-api-message-list：{message_list}")
        return message_list

    @staticmethod
    def _convert_chunk_content_part(content_part: Iterable[ChatCompletionContentPartParam]) -> List[Part]:
        part_list = []
        for item in content_part:
            if item.type == "text":
                part_list.append(types.Part.from_text(text=item.text))
            if item.type == "image_url":
                # 使用正则表达式提取图片格式和 base64 编码的部分
                match = re.match(r"^data:image/([^;]+);base64,(.+)$", item.image_url.url)
                if match:
                    # 提取图片格式（例如 png、jpeg）
                    image_format = match.group(1)
                    # 提取 base64 编码部分
                    base64_data = match.group(2)

                    part_list.append(types.Part.from_bytes(
                        data=base64_data,
                        mime_type=f'image/{image_format}',
                    ))

                else:
                    print("输入的字符串不是有效的 data:image/{format};base64 格式")
        return part_list

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

    def _get_client(self, api_key: str, base_url: str) -> Client:
        return Client(
            api_key=api_key,
            http_options={
                "base_url": base_url,
                "timeout": 30000,
                "retry_options": {
                    "max_delay": 2.0,
                    "attempts": 3
                }
            },
        )