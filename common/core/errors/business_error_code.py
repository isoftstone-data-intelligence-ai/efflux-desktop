from common.core.errors.base_error_code import BaseErrorCode


class GeneratorErrorCode(BaseErrorCode):
    # ===== mcp_server错误 (1000-1099) =====
    NO_APIKEY_FOUND = (1001, "未找到指定厂商的apikey")
    NO_CONVERSATION_FOUND = (1002, "未找到指定的会话信息")
    TOOL_AUTH_NOT_MATCH = (1003, "工具授权不匹配")
    GENERATOR_NOT_FOUND = (1004, "未找到执行模型生产者")

class TaskErrorCode(BaseErrorCode):
    TASK_RUN_ERR = (2001, "Task run error")

class ToolsErrorCode(BaseErrorCode):
    NO_APIKEY_FOUND = (1001, "未找到指定厂商的apikey")

class MCPServerErrorCode(BaseErrorCode):
    NO_APIKEY_FOUND = (1001, "未找到指定厂商的apikey")

class AgentErrorCode(BaseErrorCode):
    HAS_SAME_NAME = (1101, "extension name 相同")