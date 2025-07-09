import base64
import boto3
from botocore.exceptions import SSLError
import json
import os
import re
import traceback
from typing import Iterable, Optional, List, Generator, Iterator

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
from common.utils.time_utils import create_from_timestamp_to_int, create_from_second_now_to_int

logger = get_logger(__name__)


class AmazonClient(ModelClient):
    def __init__(self):
        self.bedrock_runtime = None
        self.model_id = None

    def _init_env(self, api_secret: OtherSecret):
        # 临时设置环境变量
        aws_access_key_id = api_secret.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = api_secret.get('AWS_SECRET_ACCESS_KEY')
        if aws_access_key_id:
            os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key_id
        if aws_secret_access_key:
            os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_access_key

    def _init_bedrock(self, api_secret: OtherSecret, model_id: str):
        try:
            self._init_env(api_secret)
            region_name = api_secret.get('AWS_REGION')
            self.model_id = model_id
            self.bedrock_runtime = boto3.client(
                service_name='bedrock-runtime',
                region_name=region_name
            )
            logger.info(f"Initialized Bedrock client for region: {region_name}")
            logger.info(f"Using model: {self.model_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            raise

    def generate(
        self,
        model: str = None,
        message_list: Iterable[ChatStreamingChunk] = None,
        api_secret: Optional[OtherSecret] = None,
        base_url: str = None,
        tools: Optional[List[Tool]] = None,
        **generation_kwargs) -> ChatStreamingChunk:
        pass

    def generate_stream(
        self,
        model: str = None,
        message_list: Iterable[ChatStreamingChunk] = None,
        api_secret: Optional[OtherSecret] = None,
        base_url: str = None,
        tools: Optional[List[Tool]] = None,
        **generation_kwargs) -> Generator[ChatStreamingChunk, None, None]:

        self._init_bedrock(api_secret, model)

        # 转换消息格式
        bedrock_messages = self._convert_bedrock_messages(message_list)
        # 工具
        bedrock_tools = None
        if tools:
            bedrock_tools = self._convert_bedrock_tools(tools)
        # 通用JSON工具配置
        tool_config = {}
        if generation_kwargs.get("json_object"):
            # 定义一个通用的JSON工具
            tool_config = {
                "tools": [
                    {
                        "name": "json_output",
                        "description": "输出JSON格式的结果",
                        "input_schema": {
                            "type": "object",
                            "description": "任意JSON对象",
                            "additionalProperties": True
                        }
                    }
                ],
                "tool_choice": {
                    "type": "tool",
                    "name": "json_output"
                }
            }
        # 最大token数
        max_tokens = 4000
        if generation_kwargs.get("output_token_limit"):
            max_tokens = generation_kwargs["output_token_limit"]
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": 0.1,
                "messages": bedrock_messages
            }

            # 如果有工具，添加到请求中
            if bedrock_tools:
                body["tools"] = bedrock_tools
            if tool_config:
                if body.get("tools"):
                    body["tools"].extend(bedrock_tools)
                else:
                    body["tools"] = tool_config["tools"]
                body["tool_choice"] = tool_config["tool_choice"]
            logger.info('body --------------------------------------------')
            logger.info(json.dumps(body))

            response = self.bedrock_runtime.invoke_model_with_response_stream(
                body=json.dumps(body),
                modelId=self.model_id,
                accept='application/json',
                contentType='application/json'
            )

            current_tool_calls = []
            current_tool_id = None
            current_tool_name = None
            current_tool_input = ""

            for event in response.get('body'):
                chunk = event.get('chunk')
                if not chunk:
                    break

                # 解析每个数据块
                chunk_data = json.loads(chunk.get('bytes').decode())
                logger.debug(f"原始chunk返回：{chunk_data}")

                # 处理工具调用开始
                if chunk_data.get('type') == 'content_block_start':
                    content_block = chunk_data.get('content_block', {})
                    if content_block.get('type') == 'tool_use':
                        current_tool_id = content_block.get('id')
                        current_tool_name = content_block.get('name')
                        current_tool_input = ""
                        logger.debug(f"开始工具调用: {current_tool_name}, ID: {current_tool_id}")

                # 处理工具调用参数增量
                elif chunk_data.get('type') == 'content_block_delta':
                    delta = chunk_data.get('delta', {})
                    if delta.get('type') == 'input_json_delta' and current_tool_name != 'json_output':
                        # 累积工具调用参数
                        partial_json = delta.get('partial_json', '')
                        current_tool_input += partial_json
                    elif delta.get('type') == 'text_delta' or current_tool_name == 'json_output':
                        # 处理普通文本响应
                        if delta.get('type') == 'text_delta':
                            text = delta.get('text', '')
                        else:
                            text = delta.get('partial_json', '')
                        if text:
                            yield ChatStreamingChunk.from_assistant(
                                id=create_uuid(),
                                model=self.model_id,
                                created=create_from_second_now_to_int(),
                                finish_reason=None,
                                role="assistant",
                                content=text,
                                reasoning_content='',
                            )

                # 处理工具调用结束
                elif chunk_data.get('type') == 'content_block_stop':
                    if current_tool_id and current_tool_name:
                        if current_tool_name == 'json_output':
                            # 普通消息结束
                            yield ChatStreamingChunk.from_assistant(
                                id=create_uuid(),
                                model=self.model_id,
                                created=create_from_second_now_to_int(),
                                finish_reason="stop",
                                role="assistant",
                                content='',
                                reasoning_content='',
                            )
                        else:
                            # 创建工具调用对象
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

                # 检查是否是消息结束
                elif chunk_data.get('type') == 'message_stop':
                    if current_tool_calls:
                        # 先返回一个空的stop标识chunk（与Gemini保持一致）
                        yield ChatStreamingChunk.from_assistant(
                            id=create_uuid(),
                            model=self.model_id,
                            created=create_from_second_now_to_int(),
                            finish_reason="stop",
                            role="assistant",
                            content='',
                            reasoning_content='',
                        )

                        # 然后返回工具调用chunk
                        yield ChatStreamingChunk.from_assistant(
                            id=create_uuid(),
                            model=self.model_id,
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
                            model=self.model_id,
                            created=create_from_second_now_to_int(),
                            finish_reason="stop",
                            role="assistant",
                            content='',
                            reasoning_content='',
                        )
                    break

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            # 抛出三方调用异常
            raise ThirdPartyServiceException(
                error_code=ThirdPartyServiceApiCode.LLM_SERVICE_API_ERROR,
                dynamics_message=f"model:{model} - exception:{str(e)}"
            )

    @staticmethod
    def _convert_bedrock_tools(tools: Iterable[Tool]) -> List[dict]:
        """
        将工具列表转换为Bedrock格式

        Args:
            tools: 工具列表

        Returns:
            Bedrock格式的工具定义列表
        """
        bedrock_tools = []
        for tool in tools:
            tool_dict = tool.model_dump()

            # 移除非Bedrock字段
            bedrock_tool = {
                "name": tool_dict.get("name"),
                "description": tool_dict.get("description"),
                "input_schema": tool_dict.get("input_schema", {})
            }

            bedrock_tools.append(bedrock_tool)

        logger.debug(f"转换后的Bedrock工具: {bedrock_tools}")
        return bedrock_tools

    def _convert_bedrock_messages(self, chat_streaming_chunk_list: Iterable[ChatStreamingChunk]) -> List[dict]:
        """
        转换消息格式为Bedrock所需格式

        Args:
            chat_streaming_chunk_list: 聊天流式块列表

        Returns:
            Bedrock格式的消息列表
        """
        messages = []
        system_message = ""

        for chunk in chat_streaming_chunk_list:
            if chunk.role == "system":
                system_message += chunk.content
            elif chunk.role == "user":
                if isinstance(chunk.content, str):
                    '''
                    文字+文件消息类型
                    {
                        "role": "user",
                        "content": [
                            {"text": "中文总结一下这份文档的内容，20字左右。"},
                            {
                                "document": {
                                    # Available formats: html, md, pdf, doc/docx, xls/xlsx, csv, and txt
                                    "format": "txt",
                                    "name": "README",
                                    "source": {"bytes": document_bytes},
                                }
                            },
                        ],
                    }
                    '''
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text": chunk.content}]
                    })
                else:
                    '''
                    文字+base64图片类型
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": f"image/{image_format}",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                    '''
                    # 处理多模态内容
                    content = self._convert_multimodal_content(chunk.content)
                    messages.append({
                        "role": "user",
                        "content": content
                    })
            elif chunk.role == "assistant":
                if chunk.finish_reason == "tool_calls" and chunk.tool_calls:
                    # 处理工具调用消息
                    content = []
                    for tool_call in chunk.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tool_call.id,
                            "name": tool_call.name,
                            "input": json.loads(tool_call.arguments) if tool_call.arguments else {}
                        })
                    messages.append({
                        "role": "assistant",
                        "content": content
                    })
                else:
                    # 普通助手消息
                    if chunk.content:
                        messages.append({
                            "role": "assistant",
                            "content": [{"type": "text", "text": chunk.content}]
                        })
            elif chunk.role == "tool":
                # 处理工具结果
                content = []
                for tool_call in chunk.tool_calls:
                    content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": chunk.content
                    })
                messages.append({
                    "role": "user",
                    "content": content
                })

        # 如果有系统消息，将其插入到第一条用户消息中
        if system_message and messages and messages[0]["role"] == "user":
            if isinstance(messages[0]["content"], list):
                messages[0]["content"].insert(0, {"type": "text", "text": system_message + "\n\n"})
            else:
                messages[0]["content"] = system_message + "\n\n" + messages[0]["content"]

        logger.debug(f"转换后的Bedrock消息: {messages}")
        return messages

    @staticmethod
    def _convert_multimodal_content(content_parts: Iterable[ChatCompletionContentPartParam]) -> List[dict]:
        """
        转换多模态内容为Bedrock格式

        Args:
            content_parts: 内容部分列表

        Returns:
            Bedrock格式的内容列表
        """
        bedrock_content = []

        for part in content_parts:
            if part.type == "text":
                bedrock_content.append({
                    "type": "text",
                    "text": part.text
                })
            elif part.type == "image_url":
                mime_type, encoding, base64_data = AmazonClient._get_base64_meta(part.image_url.url)
                bedrock_content.append({
                    "type": "image",
                    "source": {
                        "type": encoding,
                        "media_type": mime_type,
                        "data": base64_data
                    }
                })
        return bedrock_content

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

    # 实现 generate_test 方法
    def generate_test(
        self,
        model: str = None,
        message_list: Iterable[ChatStreamingChunk] = None,
        api_secret: Optional[OtherSecret] = None,
        base_url: str = None,
        tools: Optional[List[Tool]] = None,
        **generation_kwargs
    ):
        """
        测试方法，用于调试
        """
        self._init_bedrock(api_secret, model)

        # 转换消息格式
        bedrock_messages = self._convert_bedrock_messages(message_list)
        bedrock_tools = None
        if tools:
            bedrock_tools = self._convert_bedrock_tools(tools)

        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.1,
                "messages": bedrock_messages
            }

            if bedrock_tools:
                body["tools"] = bedrock_tools

            logger.info(f"测试请求体: {json.dumps(body, indent=2, ensure_ascii=False)}")

            response = self.bedrock_runtime.invoke_model(
                body=json.dumps(body),
                modelId=self.model_id,
                accept='application/json',
                contentType='application/json'
            )

            response_body = json.loads(response['body'].read())
            logger.info(f"测试响应: {json.dumps(response_body, indent=2, ensure_ascii=False)}")

            return response_body

        except Exception as e:
            logger.error(f"测试失败: {e}")
            logger.error(traceback.format_exc())
            return None

    # 实现 model_list 方法
    def model_list(self, *args, **kwargs):
        # 这里可以添加获取模型列表的逻辑
        try:
            self._init_env(args[0])
            bedrock_client = boto3.client(
                service_name="bedrock",
                region_name=args[0].get('AWS_REGION'))
            response = bedrock_client.list_foundation_models()
            models = response["modelSummaries"]
            '''
            {
                "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/mistral.pixtral-large-2502-v1:0",
                "modelId": "mistral.pixtral-large-2502-v1:0",
                "modelName": "Pixtral Large (25.02)",
                "providerName": "Mistral AI",
                "inputModalities": [
                    "TEXT",
                    "IMAGE"
                ],
                "outputModalities": [
                    "TEXT"
                ],
                "responseStreamingSupported": true,
                "customizationsSupported": [],
                "inferenceTypesSupported": [
                    "INFERENCE_PROFILE"
                ],
                "modelLifecycle": {
                    "status": "ACTIVE"
                }
                }
            ]
            '''
            return list(set([i.get('modelName') for i in models]))
        except SSLError as e:
            raise BusinessException(
                error_code=CommonErrorCode.INVALID_TOKEN,
                dynamics_message='无效的模型厂商配置，请检查配置'
            )
        except Exception as e:
            logger.error("Failed to get model list: ")
            logger.error(traceback.format_exc())
            return []

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
