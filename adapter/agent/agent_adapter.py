from adapter.agent.prompts.clarification import SYSTEM_MESSAGE_CLARIFICATION
from adapter.agent.prompts.ppter import SYSTEM_MESSAGE_PPTER
from adapter.agent.prompts.svger import SYSTEM_MESSAGE_SVGER
from application.domain.agents.agent import Agent, AgentInstance, AgentInfo
from application.domain.agents.clarification_agent import ClarificationAgent
from application.domain.agents.plan_agent import PlanAgent
from application.domain.agents.ppter_agent import PpterAgent
from application.domain.agents.text_agent import TextAgent
from application.domain.agents.svger_agent import SvgerAgent
from application.domain.generators.generator import LLMGenerator
from application.port.outbound.agent_port import AgentPort
from application.port.outbound.conversation_port import ConversationPort
from application.port.outbound.generators_port import GeneratorsPort
from application.port.outbound.tools_port import ToolsPort
from application.port.outbound.ws_message_port import WsMessagePort
from common.core.container.annotate import component
from common.utils.json_file_util import JSONFileUtil
from common.utils.file_util import get_resource_path
from typing import Optional, Dict, List

import asyncio

from adapter.agent.prompts.browser import (
    WEB_SURFER_OCR_PROMPT,
    WEB_SURFER_QA_SYSTEM_MESSAGE,
    WEB_SURFER_TOOL_PROMPT,
    WEB_SURFER_SYSTEM_MESSAGE,
    WEB_SURFER_NO_TOOLS_PROMPT,
)

from adapter.agent.prompts.plan import (
    ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING,
    ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION,
    ORCHESTRATOR_PLAN_PROMPT_JSON,
    ORCHESTRATOR_PLAN_REPLAN_JSON
)


@component
class AgentAdapter(AgentPort):

    @staticmethod
    def _load_prompt_list(agent_info: AgentInfo) -> Dict[str, str]:
        prompts = {}
        if agent_info.name == "websurfer":
            prompts['WEB_SURFER_OCR_PROMPT'] = WEB_SURFER_OCR_PROMPT
            # prompts['WEB_SURFER_QA_PROMPT'] = WEB_SURFER_QA_PROMPT
            prompts['WEB_SURFER_QA_SYSTEM_MESSAGE'] = WEB_SURFER_QA_SYSTEM_MESSAGE
            prompts['WEB_SURFER_TOOL_PROMPT'] = WEB_SURFER_TOOL_PROMPT
            prompts['WEB_SURFER_SYSTEM_MESSAGE'] = WEB_SURFER_SYSTEM_MESSAGE
            prompts['WEB_SURFER_NO_TOOLS_PROMPT'] = WEB_SURFER_NO_TOOLS_PROMPT
        if agent_info.name == "plan":
            prompts['ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING'] = ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING
            prompts['ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION'] = ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION
            prompts['ORCHESTRATOR_PLAN_PROMPT_JSON'] = ORCHESTRATOR_PLAN_PROMPT_JSON
            prompts['ORCHESTRATOR_PLAN_REPLAN_JSON'] = ORCHESTRATOR_PLAN_REPLAN_JSON
        if agent_info.name == "clarification":
            prompts['SYSTEM_MESSAGE_CLARIFICATION'] = SYSTEM_MESSAGE_CLARIFICATION
        if agent_info.name == "ppter":
            prompts['SYSTEM_MESSAGE_PPTER'] = SYSTEM_MESSAGE_PPTER
        if agent_info.result_type == "text":
            prompts = agent_info.agent_prompts
        if agent_info.name == "汉语新解":
            prompts['SYSTEM_MESSAGE_SVGER'] = SYSTEM_MESSAGE_SVGER
        return prompts

    agent_file_url = get_resource_path("adapter/agent/agent.json")
    customize_agent_file_url = get_resource_path("adapter/agent/customize_agent.json")
    agent_instance_file_pre_url = "conversations/agent_instance/"

    def load_instance_info(self, instance_id: str, conversation_id: str) -> Optional[AgentInfo]:
        agent_instance_file = f"{self.agent_instance_file_pre_url}{conversation_id}.json"
        agent_instance_config = JSONFileUtil(agent_instance_file)
        # 遍历所有agent
        for agent_instance_dict_id in agent_instance_config.read().keys():
            # 获取agent
            if agent_instance_dict_id == instance_id:
                agent_instance_dict = agent_instance_config.read_key(instance_id)
                agent_info = AgentInfo.model_validate(agent_instance_dict)
                agent_info.agent_prompts = self._load_prompt_list(agent_info)
                return agent_info
        return None

    def save_instance_info(self, instance_info: AgentInfo) -> AgentInfo:
        agent_instance_file = f"{self.agent_instance_file_pre_url}{instance_info.conversation_id}.json"
        agent_instance_config = JSONFileUtil(agent_instance_file)
        agent_instance_config.update_key(instance_info.instance_id, instance_info.model_dump())
        return instance_info

    def save(self, agent: Agent) -> str:
        agent_config = JSONFileUtil(self.customize_agent_file_url)
        agent_config.update_key(agent.id, agent.model_dump())
        return agent.id

    def load(self, agent_id: str) -> Optional[Agent]:
        agent = self._load_by_id(agent_id=agent_id, agent_file_url=self.agent_file_url)
        if agent:
            return agent
        return self._load_by_id(agent_id=agent_id, agent_file_url=self.customize_agent_file_url)

    def remove(self, agent_id: str) -> str:
        agent_config = JSONFileUtil(self.customize_agent_file_url)
        agent_config.delete(agent_id)
        return agent_id

    def load_by_name(self, agent_name: str) -> Optional[Agent]:
        agent = self._load_by_name(agent_name=agent_name, agent_file_url=self.agent_file_url)
        if agent:
            return agent
        return self._load_by_name(agent_name=agent_name, agent_file_url=self.customize_agent_file_url)

    def _load_by_id(self, agent_id: str, agent_file_url: str) -> Optional[Agent]:
        agent_config = JSONFileUtil(agent_file_url)
        # 遍历所有agent
        for agent_dict_id in agent_config.read().keys():
            # 获取agent
            if agent_dict_id == agent_id:
                agent_dict = agent_config.read_key(agent_id)
                agent = Agent.model_validate(agent_dict)
                # 加载所有提示词 TODO 后面可能会持久化，统一返回
                agent.agent_prompts = self._load_prompt_list(
                    agent.info(conversation_id="1", dialog_segment_id="1", generator_id="1", instance_id="1"))
                return agent
        return None

    def _load_by_name(self, agent_name: str, agent_file_url: str) -> Optional[Agent]:
        agent_config = JSONFileUtil(agent_file_url)
        # 遍历所有agent
        for agent_dict_id in agent_config.read().keys():
            agent_dict = agent_config.read_key(agent_dict_id)
            if agent_dict['name'] == agent_name:
                agent = Agent.model_validate(agent_dict)
                # 加载所有提示词 TODO 后面可能会持久化，统一返回
                agent.agent_prompts = self._load_prompt_list(agent.info(conversation_id="1", dialog_segment_id="1", generator_id="1", instance_id="1"))
                return agent
        return None

    def make_instance(self, agent_info: AgentInfo, llm_generator: LLMGenerator, generators_port: GeneratorsPort,
                      conversation_port: ConversationPort, ws_message_port: WsMessagePort, tools_port: ToolsPort) -> Optional[AgentInstance]:
        # if agent_info.name == 'websurfer':
        #     agent_instance = BrowserAgent(
        #         generators_port=generators_port,
        #         llm_generator=llm_generator,
        #         ws_message_port=ws_message_port,
        #         conversation_port=conversation_port,
        #         tools_port=tools_port,
        #     )
        #     asyncio.run(
        #         agent_instance.lazy_init(
        #             config={}
        #         )
        #     )
        #     return agent_instance
        if agent_info.name == 'plan':
            agent_instance = PlanAgent(
                generators_port=generators_port,
                llm_generator=llm_generator,
                ws_message_port=ws_message_port,
                conversation_port=conversation_port,
                tools_port=tools_port,
            )
            agents, team_description = self.load_agent_teams()
            asyncio.run(
                agent_instance.lazy_init(
                config={
                    "agents": agents,
                    "team_description": team_description
                    }
                )
            )
            return agent_instance
        if agent_info.name == 'clarification':
            agent_instance = ClarificationAgent(
                generators_port=generators_port,
                llm_generator=llm_generator,
                ws_message_port=ws_message_port,
                conversation_port=conversation_port,
                tools_port=tools_port,
            )
            return agent_instance
        if agent_info.name == 'ppter':
            agent_instance = PpterAgent(
                generators_port=generators_port,
                llm_generator=llm_generator,
                ws_message_port=ws_message_port,
                conversation_port=conversation_port,
                tools_port=tools_port,
            )
            return agent_instance
        if agent_info.result_type and agent_info.result_type == 'text':
            agent_instance = TextAgent(
                generators_port=generators_port,
                llm_generator=llm_generator,
                ws_message_port=ws_message_port,
                conversation_port=conversation_port,
                tools_port=tools_port,
            )
            return agent_instance
        if agent_info.name == '汉语新解':
            agent_instance = SvgerAgent(
                generators_port=generators_port,
                llm_generator=llm_generator,
                ws_message_port=ws_message_port,
                conversation_port=conversation_port,
                tools_port=tools_port,
            )
            return agent_instance

    def load_agent_teams(self) -> tuple[List[Agent], str]:
        agents = [
            self.load("4877f996-2fb5-400d-9b26-245a824e325f"),
            self.load("f83b0799-366c-4b1b-8983-050ef0ebcf49")
        ]
        team_description = "\n".join(
            [
                f"{agent.name}: {agent.description}".strip()
                for agent in agents
            ]
        )
        return agents, team_description

    def check_agent_in_teams(self, agent_name: str) -> bool:
        agents, load_agent_teams = self.load_agent_teams()
        result = False
        for agent in agents:
            if agent.name == agent_name:
                result = True
        return result

    def load_all(self) -> List[Agent]:
        agent_config = JSONFileUtil(self.agent_file_url)
        customize_agent_config = JSONFileUtil(self.customize_agent_file_url)
        res :List[Agent] = []
        # 遍历所有内置agent
        for agent_dict_id in agent_config.read().keys():
            agent_dict = agent_config.read_key(agent_dict_id)
            agent = Agent.model_validate(agent_dict)
            res.append(agent)
        # 遍历所有自定义agent
        for agent_dict_id in customize_agent_config.read().keys():
            agent_dict = customize_agent_config.read_key(agent_dict_id)
            agent = Agent.model_validate(agent_dict)
            res.append(agent)
        return res


    def load_extension(self) -> List[Agent]:
        agent_config = JSONFileUtil(self.customize_agent_file_url)
        res: List[Agent] = []
        # 遍历所有自定义agent
        for agent_dict_id in agent_config.read().keys():
            agent_dict = agent_config.read_key(agent_dict_id)
            agent = Agent.model_validate(agent_dict)
            if agent.result_type and agent.result_type == 'text':
                res.append(agent)
        return res