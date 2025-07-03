from fastapi import FastAPI
import os
import tempfile
import platform
from importlib import import_module
from fastapi.middleware.cors import CORSMiddleware
from common.core.logger import get_logger, LOGGING_CONFIG
from common.core.container.container import get_container
from common.core.connection_manager import manager, dispatcher
from adapter.web.core.exception_registry import register_exception_handlers
from application.port.outbound.task_port import TaskPort
from application.port.outbound.event_port import EventPort
from application.port.outbound.cache_port import CachePort
from common.utils.file_util import get_resource_path
from common.utils.common_utils import CONVERSATION_STOP_FLAG_KEY, SINGLETON_WEBSOCKET_CLIENT_ID, create_uuid, \
    CURRENT_CONVERSATION_AGENT_INSTANCE_ID
import uvicorn
import copy
import asyncio

from common.utils.json_file_util import JSONFileUtil
from common.utils.yaml_util import save_yaml
from common.utils.markdown_util import write

logger = get_logger(__name__)
app = FastAPI()

async def startup():
    logger.info("app启动")
    # 启动容器
    get_container()
    # 设置会话停止缓存
    get_container().get(CachePort).set_data(name=CONVERSATION_STOP_FLAG_KEY, key="test", value=False)
    get_container().get(CachePort).set_data(name=CURRENT_CONVERSATION_AGENT_INSTANCE_ID, key="test", value=False)

async def shutdown():
    logger.info("app关闭")
    # 关闭task线程池
    get_container().get(TaskPort).shutdown()
    # 关闭事件总线
    get_container().get(EventPort).shutdown()

app.add_event_handler("startup", startup)
app.add_event_handler("shutdown", shutdown)
# 注册异常控制器
register_exception_handlers(app)

# origins = [
#     "https://www.runoob.com:80",
#     "https://www.runoob.com",
#     "127.0.0.1",
#     "127.0.0.1:80",
#     "https://127.0.0.1",
#     "http://127.0.0.1",
#     "http://127.0.0.1:80",
#     # "http://127.0.0.1:3003",
#     # "http://127.0.0.1:3000",
#     # "http://127.0.0.1",
#     # "http://47.236.204.213:3003",
#     # "http://47.236.204.213:3000",
#     # "http://47.236.204.213",
#     # "http://localhost:3003",
#     # "http://localhost:3000",
#     # "http://localhost",
# ]

origins = [
    "*"
]

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许所有源，或者指定特定源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)


def include_routers_from_package(package_name: str):
    """扫描指定包，动态导入所有模块，并注册路由

    Args:
        package_name: 包名，例如 'adapter.web.controller'
    """
    try:
        # 尝试直接导入包
        package = import_module(package_name)
        package_path = os.path.dirname(os.path.abspath(package.__file__))

        # 获取包中所有模块
        modules = []
        for item in os.listdir(package_path):
            full_path = os.path.join(package_path, item)
            # 跳过 __pycache__ 目录和非 .py 文件
            if item == '__pycache__' or not item.endswith('.py') or item.startswith('__'):
                continue
            module_name = item[:-3]  # 移除 .py 后缀
            modules.append(module_name)

        # 导入模块并注册路由
        for module_name in modules:
            try:
                full_module_name = f"{package_name}.{module_name}"
                module = import_module(full_module_name)
                if hasattr(module, 'router'):
                    app.include_router(module.router)
                    logger.info(f"Successfully registered router from {full_module_name}")
            except Exception as e:
                logger.error(f"Error importing {module_name}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Error in include_routers_from_package: {str(e)}")
        import traceback
        traceback.print_exc()

# 扫描指定包下的所有controller
include_routers_from_package('adapter.web.controller')

# # 程序入口
# if __name__ == "__main__":
#     # 配置 uvicorn 使用项目的日志配置
#     # 从 uvicorn 获取默认日志配置
#     uvicorn_log_config = copy.deepcopy(LOGGING_CONFIG)
#
#     # 确保 uvicorn 相关的日志器使用我们的配置
#     for logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
#         if logger_name not in uvicorn_log_config['loggers']:
#             uvicorn_log_config['loggers'][logger_name] = {
#                 'handlers': ['console', 'file'],
#                 'level': 'INFO',
#                 'propagate': False,
#             }
#
#     uvicorn.run("main:app",
#                 host="0.0.0.0",
#                 port=8000,
#                 workers=1,
#                 reload=False,
#                 log_level="info",
#                 log_config=uvicorn_log_config)

# # 停止服务的接口
# @app.post("/shutdown")
# async def shutdown_service():
#     logger.info("即将关闭服务...")
#     # 停止 WebSocket 服务器和 Uvicorn 服务器
#     stop_event.set()  # 停止事件
#
#     return {"message": "服务正在关闭"}
#
# # 在主程序中管理这些服务
# stop_event = asyncio.Event()

from websockets import serve

async def ws_handler(websocket):
    # 假设你在路径参数中指定了 client_id，例如 ws://localhost:8765/ws?client_id=abc
    query = dict((kv.split("=") for kv in websocket.request.path.split("?")[1].split("&")))
    client_id = query.get("client_id", create_uuid())
    # client_id = SINGLETON_WEBSOCKET_CLIENT_ID
    # client_id = create_uuid()
    manager.register(client_id, websocket)
    logger.info(f"connection open -> client_id[{client_id}]")
    try:
        async for message in websocket:
            print(f"Received from {client_id}: {message}")
            await websocket.send(f"Echo: {message}")
    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        logger.info(f"connection close -> client_id[{client_id}]")
        manager.unregister(client_id)

# 同时启动 FastAPI 和 WebSocket
async def main():
    # 1. 自定义 WebSocket server（关闭压缩）
    # ws_server = await serve(ws_handler, "0.0.0.0", 8765, compression=None, ping_interval=None)

    ws_server = await serve(ws_handler, "0.0.0.0", 38765, ping_interval=None)

    # 获取当前事件循环
    loop = asyncio.get_running_loop()

    # 启动消息派发器
    dispatcher.start(loop)

    # 2. 启动 FastAPI 应用（通过 uvicorn）
    uvicorn_log_config = copy.deepcopy(LOGGING_CONFIG)
    for logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
        if logger_name not in uvicorn_log_config['loggers']:
            uvicorn_log_config['loggers'][logger_name] = {
                'handlers': ['console'],
                'level': 'DEBUG',
                'propagate': False,
            }

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=38080,
        workers=1,
        reload=True,
        log_level="info",
        log_config=uvicorn_log_config,
        # ssl_keyfile="server.key",  # 私钥文件
        # ssl_certfile="server.crt",  # 证书文件
    )
    server = uvicorn.Server(config)

    # 并发运行两个服务
    await asyncio.gather(
        server.serve(),
        ws_server.wait_closed(),  # 保持 WebSocket 运行
    )

    # # 等待停止事件，终止应用
    # await stop_event.wait()  # 当停止事件被触发，进程将结束
    #
    # # 执行 shutdown 操作
    # await shutdown()


def get_app_data_dir():
    # 获取操作系统类型
    system = platform.system().lower()
    if system == 'darwin':  # macOS
        app_data_dir = os.path.join(os.path.expanduser("~"), 'Library', 'Application Support', 'efflux-desktop')
    elif system == 'windows':  # Windows
        app_data_dir = os.getenv('APPDATA')  # Roaming
        if not app_data_dir:
            app_data_dir = os.getenv('LOCALAPPDATA')  # Local
        app_data_dir = os.path.join(app_data_dir, 'efflux-desktop')
    else:  # Linux or other Unix-like systems
        app_data_dir = os.path.join(os.path.expanduser("~"), '.config', 'efflux-desktop')

    # 如果目录不存在，则创建它
    os.makedirs(app_data_dir, exist_ok=True)
    return app_data_dir

def default_setting():
    print("加载默认配置")
    agent_file_url = get_resource_path("adapter/agent/agent.json")
    agent_config = JSONFileUtil(agent_file_url)
    agent_ppt = {
        "id": "f83b0799-366c-4b1b-8983-050ef0ebcf49",
        "name": "ppter",
        "tools_group_list": [
            {
                "group_name": "browser",
                "type": "LOCAL"
            }
        ],
        "build_in": True,
        "description": "PPT Agent"
    }
    agent_config.update_key(agent_ppt['id'], agent_ppt)
    agent_svg = {
        "id": "f83b0799-366c-4b1b-8983-050ef0ebcf50",
        "name": "汉语新解",
        "tools_group_list": [
            {
                "group_name": "browser",
                "type": "LOCAL"
            }
        ],
        "build_in": True,
        "description": "SVG Agent"
    }
    agent_config.update_key(agent_svg['id'], agent_svg)
    model_dist = {
        "openai":{
            "base_url": "https://api.openai.com/v1",
            "model_list": ["o3-pro", "o4-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4.5-preview", "o3", "gpt-4o-search-preview", "gpt-4o-mini-search-preview", "o3-mini", "o1", "o1-pro", "o1-preview", "o1-mini", "gpt-4o", "chatgpt-4o-latest", "gpt-4o-mini"]
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "model_list": ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022"]
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com",
            "model_list": [
                "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite-preview-06-17", "gemini-2.5-flash-preview-05-20",
                "gemini-2.0-flash", "gemini-2.0-flash-lite"
            ]
        },
        "Amazon Bedrock": {
            "fields": {
                "AWS_ACCESS_KEY_ID": "AWS Access Key",
                "AWS_SECRET_ACCESS_KEY": "AWS Secret Key",
                "AWS_REGION": "AWS Region",
            }
        },
        "Azure OpenAI": {
            "fields": {
                "endpoint": "Azure OpenAI Endpoint: https://isfot-ai.openai.azure.com/ (demo)",
                "subscription_key": "Azure OpenAI Subscription Key: c70ec31c1d794452a5e18eefb0e**** (demo)",
                "api_version": "Azure OpenAI API Version: 2024-12-01-preview (demo)"
            }
        },
        "tongyi": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model_list": ["qwq-max", "qwq-plus", "deepseek-r1", "deepseek-v3", "qwen-max", "qwen-plus"]
        }
    }
    save_yaml("adapter/model_sdk/setting/openai/model.yaml", model_dist)
    artifacts_prompt = """
You are a skilled software engineer.
You do not make mistakes.
Generate an fragment.
You can install additional dependencies.
Do not touch project dependencies files like package.json, package-lock.json, requirements.txt, etc.
You can use one of the following templates:

1. Python data analyst: "Runs code as a Jupyter notebook cell. Strong data analysis angle. Can use complex visualisation to explain results." File: script.py. Dependencies installed: python, jupyter, numpy, pandas, matplotlib, seaborn, plotly. Port: none.
2. Next.js developer: "A Next.js 13+ app that reloads automatically. Using the pages router." File: pages/index.tsx. Dependencies installed: nextjs@14.2.5, typescript, @types/node, @types/react, @types/react-dom, postcss, tailwindcss, shadcn. Port: 3000.
3. Vue.js developer: "A Vue.js 3+ app that reloads automatically. Only when asked specifically for a Vue app." File: app.vue. Dependencies installed: vue@latest, nuxt@3.13.0, tailwindcss. Port: 3000.
4. Streamlit developer: "A streamlit app that reloads automatically." File: app.py. Dependencies installed: streamlit, pandas, numpy, matplotlib, request, seaborn, plotly. Port: 8501.
5. Gradio developer: "A gradio app. Gradio Blocks/Interface should be called demo." File: app.py. Dependencies installed: gradio, pandas, numpy, matplotlib, request, seaborn, plotly. Port: 7860.

And please provide your response in JSON format without any additional explanations or comments.
The response must follow this schema structure, with the code placed in the code field.
Use the same language matching the user's language when filling the commentary section.

schema:{
    "commentary": "I will generate a simple 'Hello World' application using the Next.js template. This will include a basic page that displays 'Hello World' when accessed.",
    "template": "nextjs-developer",
    "title": "Hello World",
    "description": "A simple Next.js app that displays 'Hello World'.",
    "additional_dependencies": [],
    "has_additional_dependencies": false,
    "install_dependencies_command": "",
    "port": 3000,
    "file_path": "pages/index.tsx",
    "code": ""
}
    """
    write(md_url="adapter/setting/artifacts_prompt.md", content=artifacts_prompt)


if __name__ == "__main__":
    # 获取系统临时目录
    data_dir = get_app_data_dir()

    # 更改当前工作目录为临时目录
    os.chdir(data_dir)

    # 打印当前工作目录，确认更改成功
    print("Current Working Directory:", os.getcwd())

    default_setting()

    asyncio.run(main())
