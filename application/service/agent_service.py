from application.domain.agents.agent import Agent
from application.port.inbound.agent_case import AgentCase
from application.port.outbound.agent_port import AgentPort
from common.core.container.annotate import component
from common.core.errors.business_exception import BusinessException
from common.core.errors.business_error_code import AgentErrorCode
from common.utils.common_utils import create_uuid
from application.port.outbound.tools_port import ToolsPort
from typing import Optional, Dict, Any, List
import injector

@component
class AgentService(AgentCase):

    @injector.inject
    def __init__(
        self,
        agent_port: AgentPort,
        tools_port: ToolsPort,
    ):
        self.agent_port = agent_port
        self.tools_port = tools_port

    async def save(self, agent: Agent) -> str:
        if agent.id is None:
            agent.id = create_uuid()
        agent.result_type = "text"
        agent.tools_group_list = []
        old_agent = self.agent_port.load_by_name(agent.name)
        if old_agent and old_agent.id != agent.id:
            raise BusinessException(error_code=AgentErrorCode.HAS_SAME_NAME,
                                  dynamics_message="extension: " + agent.name)
        # tool_list: List[Tool] = []
        # if 'tools_group' in agent_dict:
        #     for tools_group in agent_dict.pop('tools_group'):
        #         tools = await self.tools_port.load_tools(group_name=tools_group['name'], tool_type=ToolType[tools_group['type']])
        #         tool_list.extend(tools)
        # # agent: Optional[Agent] = None
        # if 'id' in agent_dict and agent_dict['id']:
        #     agent = Agent(id=agent_dict['id'], name=agent_dict['name'], description=agent_dict['description'],tools=tool_list)
        # else:
        #     agent = Agent.from_init(name=agent_dict['name'], description=agent_dict['description'],tools=tool_list)
        return self.agent_port.save(agent)

    async def load(self, agent_id: str) -> Optional[Agent]:
        return self.agent_port.load(agent_id)

    async def remove(self, agent_id: str) -> str:
        return self.agent_port.remove(agent_id)

    async def load_extension(self) -> List[Agent]:
        return self.agent_port.load_extension()

    async def load_all(self) -> List[Agent]:
        return self.agent_port.load_all()

    async def load_by_name(self, agent_name: str) -> Optional[Agent]:
        return self.agent_port.load_by_name(agent_name)