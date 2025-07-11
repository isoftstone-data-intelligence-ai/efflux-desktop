from fastapi import FastAPI
import os
from default_setting import artifacts_prompt, default_agent, model_settings
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
from common.utils.common_utils import CONVERSATION_STOP_FLAG_KEY, create_uuid, CURRENT_CONVERSATION_AGENT_INSTANCE_ID
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

def set_default_configuration():
    print("set_default_configuration...")
    # 配置内置agent
    agent_file_url = get_resource_path("adapter/agent/agent.json")
    agent_config = JSONFileUtil(agent_file_url)
    agent_ppt = default_agent['ppter']
    agent_config.update_key(agent_ppt['id'], agent_ppt)
    agent_svg = default_agent['new_interpretation_of_chinese']
    agent_config.update_key(agent_svg['id'], agent_svg)
    # 模型配置
    save_yaml("adapter/model_sdk/setting/openai/model.yaml", model_settings)
    # e2b提示词配置
    write(md_url="adapter/setting/artifacts_prompt.md", content=artifacts_prompt)


if __name__ == "__main__":
    # 获取系统临时目录
    data_dir = get_app_data_dir()
    # 更改当前工作目录为临时目录
    os.chdir(data_dir)
    # 打印当前工作目录，确认更改成功
    print("Current Working Directory:", os.getcwd())
    # 初始化默认配置
    set_default_configuration()
    # 启动
    asyncio.run(main())
