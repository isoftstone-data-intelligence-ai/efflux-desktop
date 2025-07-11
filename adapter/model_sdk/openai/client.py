from typing import Optional, Dict, Any, Iterable, List, Generator, Literal
import os

from openai import OpenAI
from adapter.model_sdk.client import ModelClient
from application.domain.generators.generator import LLMGenerator
from common.utils.auth import Secret
from common.core.errors.system_exception import ThirdPartyServiceException, ThirdPartyServiceApiCode
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk, ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam
from application.domain.generators.tools import Tool
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.shared_params.response_format_text import ResponseFormatText
from openai.types.shared_params.response_format_json_object import ResponseFormatJSONObject
from common.core.logger import get_logger
logger = get_logger(__name__)

class OpenAIClient(ModelClient):

    def __init__(self):
        self.timeout = float(os.environ.get("OPENAI_TIMEOUT", 180.0)) # 接口超时时间
        self.max_retries = int(os.environ.get("OPENAI_MAX_RETRIES", 3)) # 接口最啊重试次数

        self.default_tool_choice: str = "auto" # 默认工具调用模式

    def model_list(self, api_key: str = None, base_url: str = None)-> List[LLMGenerator]:
        # openAI client 构建
        client: OpenAI = self._get_client(api_key=api_key,
                                          api_base_url=base_url)

        generators: List[LLMGenerator] = []
        for model in client.models.list():
            generator = LLMGenerator.from_disabled(
                firm="openai",
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
        client: OpenAI = self._get_client(api_key=api_secret.resolve_value(),
                                          api_base_url=base_url)
        # 转换为 openAI 接口风格的工具
        openai_tools: List[ChatCompletionToolParam] = self._convert_openai_tools(tools)

        try:
            if len(openai_tools) > 0:
                tool_choice: Literal["none", "auto", "required"] = self._tool_choice(
                    generation_kwargs=generation_kwargs)
                stream = client.chat.completions.create(
                    model=model,
                    messages=self._convert_openai_stream_chunk(message_list),
                    tools=openai_tools,
                    tool_choice=tool_choice,
                )
            else:
                stream = client.chat.completions.create(
                    model=model,
                    messages=self._convert_openai_stream_chunk(message_list),
                )
            return self._convert_chunk(stream)
        except Exception as exc:
            # 抛出三方调用异常
            raise ThirdPartyServiceException(error_code=ThirdPartyServiceApiCode.LLM_SERVICE_API_ERROR, dynamics_message=f"model:{model} - exception:{str(exc)}")


    @staticmethod
    def _convert_chunk(completion: ChatCompletion) -> ChatStreamingChunk:
        tool_calls: List[ChatCompletionMessageToolCall] = []
        if completion.choices[0].message.tool_calls:
            for openai_tool_call in completion.choices[0].message.tool_calls:
                tool_calls.append(
                    ChatCompletionMessageToolCall(id=openai_tool_call.id, name=openai_tool_call.function.name,
                                                  arguments=openai_tool_call.function.arguments))
        return ChatStreamingChunk.from_assistant(id=completion.id, model=completion.model, created=completion.created,
                                                 content=completion.choices[0].message.content,
                                                 finish_reason=completion.choices[0].finish_reason,
                                                 reasoning_content=None if not hasattr(completion.choices[0].message, "reasoning_content") else completion.choices[0].message.reasoning_content,
                                                 role=completion.choices[0].message.role,
                                                 tool_calls=tool_calls)

    def generate_test(self,
                      model: str = None,
                      message_list: Iterable[ChatStreamingChunk] = None,
                      api_secret: Secret = None,
                      base_url: str = None,
                      tools: Optional[List[Tool]] = None,
                      **generation_kwargs,
                      ):
        # openAI client 构建
        client: OpenAI = self._get_client(api_key=api_secret.resolve_value(),
                                          api_base_url=base_url)
        stream = client.chat.completions.create(
            model=model,
            messages=self._convert_openai_stream_chunk(message_list),
            stream=False,
        )
        logger.debug(stream)
        for event in stream:
            logger.debug("============================================================================================")
            logger.debug(f"原始chunk返回：{event}")
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
        # openAI client 构建
        client: OpenAI = self._get_client(api_key=api_secret.resolve_value(),
                                          api_base_url=base_url)
        # 转换为 openAI 接口风格的工具
        openai_tools: List[ChatCompletionToolParam] = self._convert_openai_tools(tools)

        response_format = ResponseFormatText(type="text")
        if "json_object" in generation_kwargs.keys() and generation_kwargs["json_object"]:
            response_format = ResponseFormatJSONObject(type="json_object")
        try:
            if len(openai_tools) > 0:
                tool_choice: Literal["none", "auto", "required"] = self._tool_choice(generation_kwargs=generation_kwargs)
                stream = client.chat.completions.create(
                    model=model,
                    messages=self._convert_openai_stream_chunk(message_list),
                    response_format=response_format,
                    tools=openai_tools,
                    tool_choice=tool_choice,
                    max_tokens=generation_kwargs["output_token_limit"] if "output_token_limit" in generation_kwargs else 4096,
                    stream=True,
                )
            else:
                stream = client.chat.completions.create(
                    model=model,
                    messages=self._convert_openai_stream_chunk(message_list),
                    response_format=response_format,
                    max_tokens=generation_kwargs["output_token_limit"] if "output_token_limit" in generation_kwargs else 4096,
                    stream=True,
                )
        except Exception as exc:
            # 抛出三方调用异常
            raise ThirdPartyServiceException(error_code=ThirdPartyServiceApiCode.LLM_SERVICE_API_ERROR, dynamics_message=f"model:{model} - exception:{str(exc)}")

        tool_calls: List[ChatCompletionMessageToolCall] = []
        current_role = ""
        # 记录是否已经开始返回流式事件
        started_event = False
        last_chunk = None
        for event in stream:
            if not started_event:
                started_event = True
            # logger.debug("============================================================================================")
            # logger.debug(f"原始chunk返回：{event}")
            # logger.debug("============================================================================================")
            if hasattr(event, "type") and event.type == 'ping': # claude sse ping 兼容
                logger.debug("LLM API SSE Pong")
            else:
                if len(event.choices) > 0:
                    # 补充每个chunk的role
                    if event.choices[0].delta.role:
                        current_role = event.choices[0].delta.role
                    else:
                        event.choices[0].delta.role = current_role

                chunk: ChatCompletionChunk = self._convert_stream_chunk_pretreatment(event, tool_calls, tools)
                if chunk is not None and self._is_none_chunk(chunk):
                    chat_streaming_chunk: ChatStreamingChunk = self._convert_stream_chunk(chunk)
                    if chat_streaming_chunk is not None:
                        # 发送stop事件
                        group_stop_chunk = self._set_group_stop(last_chunk=last_chunk, current_chunk=chat_streaming_chunk, started_event=started_event)
                        if group_stop_chunk:
                            yield group_stop_chunk
                        last_chunk = chat_streaming_chunk
                        yield chat_streaming_chunk

    def _is_none_chunk(self, chunk: ChatCompletionChunk) -> bool:
        """
        判断空的chunk
        :param chunk:
        :return:
        """
        return True if chunk.object else False

    def _set_group_stop(self, last_chunk: ChatStreamingChunk, current_chunk: ChatStreamingChunk, started_event: bool) -> Optional[ChatStreamingChunk]:
        """
        手动发送stop事件
        :param last_chunk:
        :param current_chunk:
        :param started_event:
        :return:
        """
        if started_event:
            #流事件已经开始，且上一个事件是普通消息未结束，当前消息是tools调用消息
            if (current_chunk.finish_reason == "tool_calls" and
                    last_chunk and last_chunk.finish_reason != "tool_calls" and last_chunk.finish_reason != "stop"):
                last_chunk.content = ""
                last_chunk.finish_reason = "stop"
                return last_chunk


    @staticmethod
    def _convert_openai_stream_chunk(chat_streaming_chunk_list: Iterable[ChatStreamingChunk]) -> List[ChatCompletionMessageParam]:
        """转换openai的chunk输入"""
        message_list: List[ChatCompletionMessageParam] = []
        for chat_streaming_chunk in chat_streaming_chunk_list:
            # 工具调用请求
            if chat_streaming_chunk.role == "assistant" and chat_streaming_chunk.finish_reason == "tool_calls":
                # 封装tool_calls集合
                tool_calls = []
                for tool_call in chat_streaming_chunk.tool_calls:
                    tool_calls.append(
                        {
                            "function": {
                                "arguments": tool_call.arguments,
                                "name": tool_call.name
                            },
                            "id": tool_call.id,
                            "type": "function"
                        }
                    )
                message_list.append({
                    "role": "assistant",
                    "tool_calls": tool_calls
                })
            # 工具调用结果
            elif chat_streaming_chunk.role == "tool":
                # 封装tool_calls结果集合
                message_list.append({
                    "role": "tool",
                    "tool_call_id": chat_streaming_chunk.tool_call_id,
                    # "content": [{
                    #     "type": "text",
                    #     "text": str(tool_call_result['result'])
                    # }]
                    "content": chat_streaming_chunk.content,
                })
            # 跳过用户确认信息
            elif chat_streaming_chunk.user_confirm and chat_streaming_chunk.user_confirm.id:
                continue
            # 一般消息
            else:
                message = {"role": chat_streaming_chunk.role, "content": chat_streaming_chunk.content}
                message_list.append(message)
        logger.debug(f"openai-api-message-list：{message_list}")
        return message_list


    def _convert_stream_chunk_pretreatment(
        self,
        completion_chunk: ChatCompletionChunk,
        tool_calls: List[ChatCompletionMessageToolCall],
        tools: List[Tool]
    ) -> Optional[ChatCompletionChunk]:
        """
        pretreatment of convert stream chunk to ChatStreamingChunk
        :param completion_chunk: openai api completion
        :param tool_calls: tools call list
        :param tools: efflux tools list
        :return:
        """
        # usage: Optional[CompletionUsage] = None
        # # 用量 部分聚合平台的chunk.choices[]为空数组的时候返回用量
        # if completion_chunk.usage:
        #     usage = CompletionUsage(prompt_tokens=completion_chunk.usage.prompt_tokens,
        #                             completion_tokens=completion_chunk.usage.completion_tokens,
        #                             total_tokens=completion_chunk.usage.total_tokens)
        if completion_chunk.usage:
            logger.debug(f"跳过用量统计-->{completion_chunk.usage}")
        # 工具，持续拼接tools_call的请求参数直到参数完整
        if len(completion_chunk.choices) > 0 and completion_chunk.choices[0].delta.tool_calls:


            # tool call 调用最后chunk中tool_calls=None且finish_reason='tool_calls'，所以不会进入此循环，而else的消息处理
            self._append_stream_tool_args(completion=completion_chunk, tool_calls=tool_calls, tools=tools)
        else:
            # 消息处理（此次如果有tool调用，则为拼接后的完整参数列表）
            if len(completion_chunk.choices) > 0 and tool_calls:
                completion_chunk.choices[0].delta.tool_calls = tool_calls
            return completion_chunk

    @staticmethod
    def _convert_stream_chunk(completion: ChatCompletionChunk) -> Optional[ChatStreamingChunk]:
        """
        convert openai stream chunk to ChatStreamingChunk
        :param completion:
        :return:
        """
        if len(completion.choices) > 0:
            return ChatStreamingChunk.from_assistant(id=completion.id, model=completion.model, created=completion.created,
                        content=completion.choices[0].delta.content, finish_reason=completion.choices[0].finish_reason,
                        reasoning_content=None if not hasattr(completion.choices[0].delta, "reasoning_content")
                            else completion.choices[0].delta.reasoning_content,
                        role=completion.choices[0].delta.role if completion.choices[0].delta.role else 'assistant',
                        tool_calls=completion.choices[0].delta.tool_calls)
        else:
            return None

    def _append_stream_tool_args(self, completion: ChatCompletionChunk, tool_calls: List[ChatCompletionMessageToolCall], tools: List[Tool]):
        """
        Call parameters for the tool that concatenates stream returns
        :param completion: stream chunk
        :param tool_calls:
        :return:
        """
        for openai_tool_call in completion.choices[0].delta.tool_calls:
            # If there is an ID, it means starting a tool parameter stream return
            if openai_tool_call.id:
                # create a tools_call chunk
                current_tool = ChatCompletionMessageToolCall(id=openai_tool_call.id,
                                                             name=openai_tool_call.function.name,
                                                             arguments=openai_tool_call.function.arguments)
                self._match_mcp_server_name(chunk_tools_call=current_tool, tools=tools)
                tool_calls.append(current_tool)
            else:
                # If there is no ID, it means that the streaming parameter is being returned
                if openai_tool_call.function.arguments:
                    tool_calls[openai_tool_call.index].arguments += openai_tool_call.function.arguments

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
    def _convert_openai_tools(tools: Iterable[Tool]) -> List[ChatCompletionToolParam]:
        """
        convert openai param tools into a list of efflux tools
        :param tools:
        :return:
        """
        openai_tools: List[ChatCompletionToolParam] = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {"name": tool.name, "description": tool.description, "parameters": tool.input_schema}
                }
            )
        return openai_tools

    @staticmethod
    def _tool_choice(**generation_kwargs) -> Literal["none", "auto", "required"]:
        tool_choice: Literal["none", "auto", "required"] = "auto"
        if "tool_choice" in generation_kwargs.keys():
            tool_choice = generation_kwargs["tool_choice"]
        return tool_choice

    def _get_client(
            self,
            api_key: str,
            api_base_url: str,
            organization: str = None,
            timeout: float = None,
            max_retries: int = None
    ) -> OpenAI:
        """
        get an OpenAI API client
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

        return OpenAI(
                api_key=api_key,
                organization=organization,
                base_url=api_base_url,
                timeout=self.timeout,
                max_retries=self.max_retries
            )