## EFFLUX DESKTOP


<div align="center">
    <h1>Efflux - Backend</h1>
    <p>LLM Agent 智能体对话客户端后端</p>
    <p>
        <a href="LICENSE">
            <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
        </a>
        <a href="https://www.python.org/downloads/">
            <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python">
        </a>
        <a href="https://fastapi.tiangolo.com/">
            <img src="https://img.shields.io/badge/FastAPI-0.115.6+-brightgreen.svg" alt="FastAPI">
        </a>
        <a href="https://modelcontextprotocol.io/">
            <img src="https://img.shields.io/badge/MCP-1.1.1-coral.svg" alt="MCP">
        </a>
    </p>
    <p>
        <a href="./README.md">English</a> | <b>简体中文</b>
    </p>
    <br/>
</div>


Efflux-Desktop 是一个专为 Windows 客户端前端设计的本地 Python 服务项目，作为用户端的智能助手运行。它基于大语言模型提供智能对话能力，支持流式会话响应和完整的对话历史管理。
通过集成 MCP 协议，Efflux 可作为 MCP Host 连接不同的 MCP Servers，为模型提供标准化的工具调用和数据访问能力，确保 Windows 客户端能够通过简洁的接口获取强大的 AI 功能支持。


### 主要特性
- 快速构建 Agent 智能体
- MCP 工具动态加载与调用
- 支持多种大语言模型接入
- 实时流式对话响应
- 会话历史记录管理


### 环境要求
- Python 3.12+
- PostgreSQL
- uv 包和项目管理工具，可通过`pip install uv`安装




### 致谢

本项目使用了以下优秀的开源项目和技术：

- [@modelcontextprotocol/mcp](https://modelcontextprotocol.io) - 标准化的 LLM 数据交互开放协议
- [@langchain-ai/langchain](https://github.com/langchain-ai/langchain) - LLM 应用开发框架
- [@pydantic/pydantic](https://github.com/pydantic/pydantic) - 数据验证和设置管理
- [@tiangolo/fastapi](https://github.com/tiangolo/fastapi) - 现代、快速的 Web 框架
- [@astral-sh/uv](https://github.com/astral-sh/uv) - 极速 Python 包管理器

感谢这些项目的开发者和维护者为开源社区做出的贡献。


