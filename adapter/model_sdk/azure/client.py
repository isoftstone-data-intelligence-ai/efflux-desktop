import json
from openai import AzureOpenAI, NotFoundError
import re
import traceback
from typing import Iterable, Optional, List, Generator

from adapter.model_sdk.client import ModelClient
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk, \
    ChatCompletionContentPartParam, ChatCompletionMessageToolCall
from application.domain.generators.tools import Tool
from common.core.errors.business_exception import BusinessException
from common.core.errors.common_error_code import CommonErrorCode
from common.core.errors.system_exception import ThirdPartyServiceException, ThirdPartyServiceApiCode
from common.core.logger import get_logger
from common.utils.auth import OtherSecret
from common.utils.common_utils import create_uuid
from common.utils.time_utils import create_from_second_now_to_int

logger = get_logger(__name__)


class AzureClient(ModelClient):
    def __init__(self):
        self.client = None
        self.deployment = None

    def _init_azure(self, api_secret: OtherSecret, model_id: str = None):
        try:
            endpoint = api_secret.get('endpoint')
            subscription_key = api_secret.get('subscription_key')
            api_version = api_secret.get('api_version')
            self.deployment = model_id

            self.client = AzureOpenAI(
                api_version=api_version,
                azure_endpoint=endpoint,
                api_key=subscription_key,
            )
            logger.info(f"Initialized Azure OpenAI client for endpoint: {endpoint}")
            logger.info(f"Using deployment: {self.deployment}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            raise

    def generate(
        self,
        model: str = None,
        message_list: Iterable[ChatStreamingChunk] = None,
        api_secret: Optional[OtherSecret] = None,
        base_url: str = None,
        tools: Optional[List[Tool]] = None,
        **generation_kwargs
    ) -> ChatStreamingChunk:
        """Non-streaming generation with tools support"""
        logger.info("Starting non-streaming generation with Azure OpenAI")
        self._init_azure(api_secret, model)

        messages = self._convert_azure_messages(message_list)
        azure_tools = None
        if tools:

            azure_tools = self._convert_azure_tools(tools)

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                tools=azure_tools,
                tool_choice="auto" if azure_tools else None,
                max_tokens=generation_kwargs.get('max_tokens', 4096),
                temperature=generation_kwargs.get('temperature', 1.0),
                top_p=generation_kwargs.get('top_p', 1.0),
            )

            response_message = response.choices[0].message

            # Handle tool calls
            if response_message.tool_calls:
                chunk_tools = []
                for tool_call in response_message.tool_calls:
                    chunk_tool_call = ChatCompletionMessageToolCall(
                        id=tool_call.id,
                        name=tool_call.function.name,
                        arguments=tool_call.function.arguments,
                    )
                    # Match mcp server name
                    self._match_mcp_server_name(chunk_tool_call, tools)
                    chunk_tools.append(chunk_tool_call)

                return ChatStreamingChunk.from_assistant(
                    id=create_uuid(),
                    model=self.deployment,
                    created=create_from_second_now_to_int(),
                    finish_reason="tool_calls",
                    role="assistant",
                    content="",
                    reasoning_content="",
                    tool_calls=chunk_tools
                )
            else:
                return ChatStreamingChunk.from_assistant(
                    id=create_uuid(),
                    model=self.deployment,
                    created=create_from_second_now_to_int(),
                    finish_reason=response.choices[0].finish_reason,
                    role="assistant",
                    content=response_message.content or "",
                    reasoning_content="",
                )

        except Exception as e:
            logger.error(f"Unexpected error during generation: {e}")
            logger.error(traceback.format_exc())
            raise

    def generate_stream(
        self,
        model: str = None,
        message_list: Iterable[ChatStreamingChunk] = None,
        api_secret: Optional[OtherSecret] = None,
        base_url: str = None,
        tools: Optional[List[Tool]] = None,
        **generation_kwargs
    ) -> Generator[ChatStreamingChunk, None, None]:
        logger.info("Starting stream generation with Azure OpenAI")
        self._init_azure(api_secret, model)

        messages = self._convert_azure_messages(message_list)
        azure_tools = None
        if tools:
            azure_tools = self._convert_azure_tools(tools)

        response_format = {}
        if generation_kwargs.get("json_object"):
            response_format = {"type": "json_object"}
        # 最大token数
        max_tokens = 4096
        if generation_kwargs.get("output_token_limit"):
            max_tokens = generation_kwargs["output_token_limit"]
        try:
            params = dict(
                stream=True,
                model=self.deployment,
                messages=messages,
                tools=azure_tools,
                tool_choice="auto" if azure_tools else None,
                max_tokens=max_tokens,
                # temperature=generation_kwargs.get('temperature', 1.0),
                # top_p=generation_kwargs.get('top_p', 1.0),
            )
            if response_format:
                params["response_format"] = response_format
            logger.info(f"Starting streaming request with params: {params}")
            response = self.client.chat.completions.create(**params)

            current_tool_calls = []
            current_tool_id = None
            current_tool_name = None
            current_tool_input = ""

            for update in response:
                logger.debug(f"Received update: {update}")
                '''
                update
                {
                    'id': 'chatcmpl-BnpwxTZMjr7OE1vJvSR5hPW3aEDS7',
                    'choices': [
                        Choice(delta=ChoiceDelta(content=None, function_call=None, refusal=None, role=None,
                            tool_calls=[
                                ChoiceDeltaToolCall(index=0, id=None,
                                    function=ChoiceDeltaToolCallFunction(
                                        arguments='北京', name=None), type=None)]), finish_reason=None, index=0, logprobs=None, content_filter_results={})],
                    'created': 1751217467,
                    'model': 'gpt-4o-2024-11-20',
                    'object': 'chat.completion.chunk',
                    'service_tier': None,
                    'system_fingerprint': 'fp_ee1d74bde0',
                    'usage': None}
                '''

                if update.choices:
                    choice = update.choices[0]
                    delta = choice.delta
                    finish_reason = choice.finish_reason

                    # Check if tool calls are completed
                    if finish_reason == "tool_calls":
                        try:
                            tool_arguments = json.loads(current_tool_input) if current_tool_input else {}
                        except json.JSONDecodeError:
                            tool_arguments = {}
                            logger.error(f"解析工具参数失败: {current_tool_input}")
                        chunk_tools_call = ChatCompletionMessageToolCall(
                            id=current_tool_id,
                            name=current_tool_name,
                            arguments=json.dumps(tool_arguments),
                        )

                        # 匹配mcp-server-name
                        self._match_mcp_server_name(chunk_tools_call=chunk_tools_call, tools=tools)
                        current_tool_calls.append(chunk_tools_call)

                        # 重置工具调用状态
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_input = ""
                        continue

                    # Handle tool calls in streaming
                    if delta.tool_calls and delta.tool_calls[0] and delta.tool_calls[0].id:
                        current_tool_id = delta.tool_calls[0].id
                    if delta.tool_calls and delta.tool_calls[0] and delta.tool_calls[0].function and delta.tool_calls[0].function.name:
                        current_tool_name = delta.tool_calls[0].function.name
                    if delta.tool_calls and delta.tool_calls[0] and delta.tool_calls[0].function and delta.tool_calls[0].function.arguments:
                        current_tool_input += delta.tool_calls[0].function.arguments

                    # Handle regular content (only if not in tool call mode)
                    elif delta.content or finish_reason:
                        content = delta.content or ""
                        yield ChatStreamingChunk.from_assistant(
                            id=create_uuid(),
                            model=self.deployment,
                            created=create_from_second_now_to_int(),
                            finish_reason=finish_reason,
                            role="assistant",
                            content=content,
                            reasoning_content='',
                        )
            if current_tool_calls:
                # 先返回一个空的stop标识chunk（与Gemini保持一致）
                yield ChatStreamingChunk.from_assistant(
                    id=create_uuid(),
                    model=self.deployment,
                    created=create_from_second_now_to_int(),
                    finish_reason="stop",
                    role="assistant",
                    content='',
                    reasoning_content='',
                )

                # 然后返回工具调用chunk
                yield ChatStreamingChunk.from_assistant(
                    id=create_uuid(),
                    model=self.deployment,
                    created=create_from_second_now_to_int(),
                    finish_reason="tool_calls",
                    role="assistant",
                    content="",
                    reasoning_content="",
                    tool_calls=current_tool_calls
                )
            else:
                # 普通消息结束
                yield ChatStreamingChunk.from_assistant(
                    id=create_uuid(),
                    model=self.deployment,
                    created=create_from_second_now_to_int(),
                    finish_reason="stop",
                    role="assistant",
                    content='',
                    reasoning_content='',
                )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            # 抛出三方调用异常
            raise ThirdPartyServiceException(
                error_code=ThirdPartyServiceApiCode.LLM_SERVICE_API_ERROR,
                dynamics_message=f"model:{model} - exception:{str(e)}"
            )

    def generate_test(self, *args, **kwargs):
        logger.info("generate_test method is called")
        return None

    def model_list(self, *args, **kwargs):
        logger.info("model_list method is called")
        try:
            self._init_azure(args[0])
            response = self.client.models.list()
            model_obj_list = response.data
            '''
            [
                Model(
                    id='dall-e-3-3.0',
                    created=None,
                    object='model',
                    owned_by=None,
                    status='succeeded',
                    capabilities={
                        'fine_tune': False,
                        'inference': True,
                        'completion': False,
                        'chat_completion': False,
                        'embeddings': False
                    },
                    lifecycle_status='generally-available',
                    deprecation={'inference': 1751241600},
                    created_at=1691712000
                ),
            ]
            '''
            return list(set([model_obj.id for model_obj in model_obj_list]))
        except NotFoundError as e:
            raise BusinessException(
                error_code=CommonErrorCode.INVALID_TOKEN,
                dynamics_message='The configured model firm is invalid. Please check the configuration.'
            )
        except Exception as e:
            logger.error("Failed to get model list: ")
            logger.error(traceback.format_exc())
            return []

    def _convert_azure_messages(self, message_list: Iterable[ChatStreamingChunk]) -> List[dict]:
        """Convert ChatStreamingChunk list to Azure OpenAI message format"""
        messages = []

        for chunk in message_list:
            if chunk.role in ["system", "user"]:
                messages.append(chunk)
            elif chunk.role == "assistant":
                if chunk.finish_reason == "tool_calls" and chunk.tool_calls:
                    # Convert tool calls to Azure format
                    tool_calls = []
                    for tool_call in chunk.tool_calls:
                        tool_calls.append({
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": tool_call.arguments
                            }
                        })
                    messages.append({
                        "role": "assistant",
                        "tool_calls": tool_calls
                    })
                else:
                    messages.append({
                        "role": "assistant",
                        "content": chunk.content
                    })
            elif chunk.role == "tool":
                # Handle tool response messages
                for tool_call in chunk.tool_calls:
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_call.name,
                        "content": chunk.content,
                    })

        logger.debug(f"azure-api-message-list: {messages}")
        return messages

    @staticmethod
    def _convert_azure_tools(tools: Iterable[Tool]) -> List[dict]:
        """Convert Tool objects to Azure OpenAI tools format"""
        azure_tools = []

        for tool in tools:
            tool_dict = tool.model_dump()

            # Remove fields that are not part of Azure OpenAI tools spec
            for field in ["mcp_server_name", "group_name", "type"]:
                if field in tool_dict:
                    del tool_dict[field]

            # Convert input_schema to parameters if needed
            if "input_schema" in tool_dict:
                tool_dict["parameters"] = tool_dict["input_schema"]
                del tool_dict["input_schema"]

            azure_tool = {
                "type": "function",
                "function": {
                    "name": tool_dict["name"],
                    "description": tool_dict["description"],
                    "parameters": tool_dict.get("parameters", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
            }
            azure_tools.append(azure_tool)

        logger.debug(f"azure-tools: {azure_tools}")
        return azure_tools

    @staticmethod
    def _match_mcp_server_name(chunk_tools_call: ChatCompletionMessageToolCall, tools: Iterable[Tool]) -> None:
        """
        匹配mcp服务器名称和描述

        Args:
            chunk_tools_call: 工具调用对象
            tools: 工具列表
        """
        for tool in tools:
            if chunk_tools_call.name == tool.name:
                chunk_tools_call.mcp_server_name = tool.mcp_server_name
                chunk_tools_call.group_name = tool.group_name
                chunk_tools_call.description = tool.description
                break