from adapter.model_sdk.anthropic.client import AnthropicClient
from adapter.model_sdk.aws.client import AmazonClient
from adapter.model_sdk.azure.client import AzureClient
from adapter.model_sdk import NON_STANDARD_FIRM_SUPPORT_LIST
from adapter.model_sdk.gemini.client import GeminiClient
from application.port.outbound.generators_port import GeneratorsPort
from application.domain.generators.tools import Tool
from application.domain.generators.generator import LLMGenerator
from application.domain.generators.firm import GeneratorFirm
from common.core.container.annotate import component
from typing import Iterable, Dict, AsyncGenerator, Any, List, Optional, Generator, Callable
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from common.utils.yaml_util import load_yaml
from adapter.model_sdk.client import ModelClient
from adapter.model_sdk.openai.client import OpenAIClient
from common.utils.json_file_util import JSONFileUtil
import asyncio
import json
import re
from common.core.logger import get_logger

logger = get_logger(__name__)


@component
class ClientManager(GeneratorsPort):

    user_setting_file_url = "user_setting.json"

    def __init__(self):
        self.config: Dict[str, Any] = load_yaml('adapter/model_sdk/setting/openai/model.yaml')
        self.user_setting = JSONFileUtil(self.user_setting_file_url)

        self.max_token_map = {
            "gpt-4.1-": 32768,
            "gpt-4o-": 16384,
            "gpt-4-": 4096,
            "claude-opus-4": 32000,
            "claude-sonnet-4": 64000,
            "claude-3-7-sonnet": 64000,
            "claude-3-5-sonnet": 8192,
            "Claude 3.5 Sonnet": 8192,
            "claude-3-5-haiku": 8192,
            "claude-3-opus": 4096,
            "gemini-1.5": 8192,
            "gemini-2.5": 65536,
            "gemini-2.0-flash": 8192,
            "gemini-2.0-flash-thinking": 65536,
            "gemini-2.0-pro": 65536,
            "gemini-2.5-flash-preview-tts": 16384,
            "gemini-2.5-pro-preview-tts": 16384
        }

    def load_generate(self, generate_id: str) -> Optional[LLMGenerator]:
        # 遍历项目内置支持的所有厂商
        for firm in self.config.keys():
            firm_model_config_url = f"adapter/model_sdk/setting/openai/{firm}_model.json"
            firm_model_config = JSONFileUtil(firm_model_config_url)
            # 遍历厂商启用的所有模型
            for model_name in firm_model_config.read().keys():
                firm_model_dict = firm_model_config.read_key(model_name)
                if firm_model_dict['id'] == generate_id:
                    return LLMGenerator.model_validate(firm_model_dict)
        return None

    def load_firm(self) -> List[GeneratorFirm]:
        firm_list: List[GeneratorFirm] = []
        for firm in self.config.keys():
            firm_list.append(GeneratorFirm.from_init(
                name=firm,
                base_url=self.config[firm]['base_url'] if 'base_url' in self.config[firm] else None,
                fields=self.config[firm]['fields'] if 'fields' in self.config[firm] else None
            ))
        return firm_list

    def is_non_standard(self, firm_name: str) -> bool:
        return firm_name in NON_STANDARD_FIRM_SUPPORT_LIST

    def load_model_by_firm(self, firm_name: str) -> List[LLMGenerator]:
        firm_model_config_url = f"adapter/model_sdk/setting/openai/{firm_name}_model.json"
        firm_model_config = JSONFileUtil(firm_model_config_url)
        model_list: List[str] = self.user_setting.read_key(firm_name)['model_list']
        generator_list: List[LLMGenerator] = []
        if model_list:
            for model in model_list:
                firm_model_dict = firm_model_config.read_key(model)
                if firm_model_dict:
                    generator_list.append(LLMGenerator.model_validate(firm_model_dict))
                else:
                    generator_list.append(LLMGenerator.from_disabled(
                        firm=firm_name, model=model, generators_type=model))
        return generator_list

    def load_model_by_api(self, firm_name: str) -> List[LLMGenerator]:
        client: ModelClient = self._get_model_client(firm=firm_name)
        firm_setting = self.user_setting.read_key(firm_name)
        model_list: List[LLMGenerator] = client.model_list(api_key=firm_setting['api_key'], base_url=firm_setting['base_url'])
        firm_setting['model_list'] = [generator.model for generator in model_list]
        self.user_setting.update_key(firm_setting['name'], firm_setting)
        return model_list

    def load_model_by_other_firm(self, firm_name: str) -> List[LLMGenerator]:
        firm_setting = self.user_setting.read_key(firm_name)
        if not firm_setting:
            return []
        firm_model_config_url = f"adapter/model_sdk/setting/openai/{firm_name}_model.json"
        firm_model_config = JSONFileUtil(firm_model_config_url).read()
        enabled_generators_type_map = {
            model_setting.get('generators_type'): model_setting
            for model_setting in firm_model_config.values()
        }
        generator_list: List[LLMGenerator] = []
        client: ModelClient = self._get_model_client(firm=firm_name)
        model_type_list = client.model_list(firm_setting.get('fields'))
        for model_type in model_type_list:
            if model_type in enabled_generators_type_map.keys():
                LLM_generator_info = enabled_generators_type_map[model_type]
                generator_list.append(LLMGenerator.model_validate(LLM_generator_info))
            else:
                generator_list.append(LLMGenerator.from_disabled(
                    firm=firm_name, generators_type=model_type))
        return generator_list

    def load_enabled_model_by_firm(self, firm_name: str) -> List[LLMGenerator]:
        firm_model_config_url = f"adapter/model_sdk/setting/openai/{firm_name}_model.json"
        firm_model_config = JSONFileUtil(firm_model_config_url)
        generator_list: List[LLMGenerator] = []
        for model in firm_model_config.read().keys():
            firm_model_dict = firm_model_config.read_key(model)
            if firm_model_dict:
                generator_list.append(LLMGenerator.model_validate(firm_model_dict))
        return generator_list

    def load_enabled_model(self) -> List[LLMGenerator]:
        firm_list: List[GeneratorFirm] = []
        for firm in self.config.keys():
            firm_list.extend(self.load_enabled_model_by_firm(firm))
        return firm_list

    def enable_or_disable_model(self, firm: str, model: str, enabled: bool, model_type: str) -> Optional[bool]:
        firm_model_config_url = f"adapter/model_sdk/setting/openai/{firm}_model.json"
        firm_model_config = JSONFileUtil(firm_model_config_url)
        if enabled:
            output_token_limit = None
            for key in self.max_token_map.keys():
                if model.startswith(key) or (model_type and model_type in key):
                    output_token_limit = self.max_token_map[key]
                    break

            llm_generator: LLMGenerator = LLMGenerator.from_init(
                firm=firm, model=model, generators_type=model_type,
                metadata={"output_token_limit": output_token_limit} if output_token_limit else None
            )
            firm_model_config.update_key(model, llm_generator.model_dump())
        else:
            firm_model_config.delete(model)
        return True

    def generate(self,
        llm_generator: LLMGenerator,
        tools: Iterable[Tool] = None,
        messages: Iterable[ChatStreamingChunk] = None,
        **generation_kwargs,
    ) -> ChatStreamingChunk:
        client: ModelClient = self._get_model_client(firm=llm_generator.firm)
        firm_setting = self.user_setting.read_key(llm_generator.firm)
        url = firm_setting["base_url"]
        rs = client.generate(
            model=llm_generator.model,
            api_secret=llm_generator.api_key_secret,
            base_url=url,
            message_list=messages,
            tools=tools,
            generation_kwargs=generation_kwargs
        )
        return rs

    def generate_test(
        self,
        llm_generator: LLMGenerator,
        validate_json: Optional[Callable[[Dict[str, Any]], bool]] = None,
        messages: Iterable[ChatStreamingChunk] = None,
        tools: Iterable[Tool] = None,
        **generation_kwargs,
    )-> Dict[str, Any] | None:
        client: ModelClient = self._get_model_client(firm=llm_generator.firm)
        firm_setting = self.user_setting.read_key(llm_generator.firm)
        url = firm_setting["base_url"]
        client.generate_test(
            model=llm_generator.model,
            api_secret=llm_generator.api_key_secret,
            base_url=url,
            message_list=messages,
            tools=tools,
            generation_kwargs=generation_kwargs
        )
        return {}

    def generate_json(
        self,
        llm_generator: LLMGenerator,
        validate_json: Optional[Callable[[Dict[str, Any]], bool]] = None,
        messages: Iterable[ChatStreamingChunk] = None,
        **generation_kwargs,
    ) -> Dict[str, Any] | None:
        retries = 0
        while retries < 1:
            contents = ""
            for chunk in self.generate_event(llm_generator=llm_generator, messages=messages, tools=[], **generation_kwargs):
                contents += chunk.content if chunk.content else ""
            try:
                print(contents)
                if contents.startswith("```json"):
                    # remove first and last line
                    response_lines = contents.split("\n")
                    response_lines = response_lines[1:-1]
                    contents = "\n".join(response_lines)
                json_response = json.loads(contents)
                # Use the validate_json function to check the response
                if validate_json and validate_json(json_response):
                    return json_response
                else:
                    return json_response
                    exception_message = "Validation failed for JSON response, retrying. You must return a valid JSON object parsed from the response."
            except json.JSONDecodeError as e:
                json_response = JSONFileUtil.extract_json_from_string(contents)
                if json_response is not None:
                    if validate_json and validate_json(json_response):
                        return json_response
                    else:
                        return json_response
                        exception_message = "Validation failed for JSON response, retrying. You must return a valid JSON object parsed from the response."
                else:
                    exception_message = f"Failed to parse JSON response, retrying. You must return a valid JSON object parsed from the response. Error: {e}"
                    return {"content": f"转换json失败 -> {contents}"}
            retries += 1
        raise ValueError("Failed to get a valid JSON response after multiple retries")

    def generate_event(self,
        llm_generator: LLMGenerator,
        messages: Iterable[ChatStreamingChunk] = None,
        tools: Iterable[Tool] = None,
        **generation_kwargs,
    ) -> Generator[ChatStreamingChunk, None, None]:
        client: ModelClient = self._get_model_client(firm=llm_generator.firm)
        firm_setting = self.user_setting.read_key(llm_generator.firm)
        url = firm_setting["base_url"]
        if llm_generator.metadata and "output_token_limit" in llm_generator.metadata:
            if "output_token_limit" not in generation_kwargs:
                generation_kwargs["output_token_limit"] = llm_generator.metadata["output_token_limit"]

        stream = client.generate_stream(
            model=llm_generator.model,
            api_secret=llm_generator.api_key_secret,
            base_url=url,
            message_list=messages,
            tools=tools,
            **generation_kwargs
        )
        for chunk in stream:
            chunk.model = llm_generator.model
            chunk.firm = llm_generator.firm
            yield chunk


    def _get_model_client(self, firm: str) -> ModelClient:
        if firm == "openai":
            return OpenAIClient()
        if firm == "google":
            return GeminiClient()
        if firm == "anthropic":
            return AnthropicClient()
        if firm == "amazon_bedrock":
            return AmazonClient()
        if firm == "azure_openai":
            return AzureClient()
