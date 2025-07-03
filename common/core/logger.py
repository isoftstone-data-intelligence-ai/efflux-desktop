import logging.config
import os
import platform

print(f"================{os.getcwd()}")

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

log_file_path = os.path.join(get_app_data_dir(), 'app.log')

print(f"================{log_file_path}")

# 高级日志配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,  # 必须为 False
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(process)d - %(thread)d - %(name)s - %(levelname)s - %(message)s",
        },
        "detailed": {
            "format": "%(asctime)s - %(process)d - %(thread)d - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        },
        "color": {  # 带颜色的格式器
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s%(asctime)s %(process)s - %(thread)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "log_colors": {
                "DEBUG": "white",
                "INFO": "cyan",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "color",
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "formatter": "detailed",
            "filename": log_file_path,
        },
    },
    "loggers": {
        "": {  # 根日志器
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "common.utils.json_file_util": {
            "handlers": ["console", "file"],
            "level": "INFO",  # json读取工具 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "adapter.tools.mcp.tools_adapter": {
            "handlers": ["console", "file"],
            "level": "INFO",  # mcp工具调用详情 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "pdfminer": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "asyncio": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "httpcore": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "openai": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "anthropic": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "botocore": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "websockets.server": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "sse_starlette": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "adapter.model_sdk.openai.client": {
            "handlers": ["console", "file"],
            "level": "DEBUG",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        "application.service.task_handlers.tool_task_handler": {
            "handlers": ["console", "file"],
            "level": "INFO",  # 只显示 INFO 及以上级别的日志
            "propagate": False,
        },
        # "sqlalchemy": {  # 配置 SQLAlchemy 日志
        #     "handlers": ["console", "file"],  # 使用与根日志器相同的处理器
        #     "level": "WARNING",  # SQLAlchemy 日志级别
        #     "propagate": False,  # 禁止传播到根日志器
        # },
        # "sqlalchemy.engine.Engine": {  # 配置 sqlalchemy.engine.Engine 日志
        #     "handlers": ["console", "file"],  # 使用与根日志器相同的处理器
        #     "level": "WARNING",  # sqlalchemy.engine.Engine 日志级别
        #     "propagate": False,  # 禁止传播到根日志器
        # },
        # "uvicorn.access": {  # FastAPI 的访问日志
        #     "handlers": ["console", "file"],
        #     "level": "INFO",
        #     "propagate": False,
        # },
    },
}

# 应用日志配置
logging.config.dictConfig(LOGGING_CONFIG)

# 日志获取函数
def get_logger(name) -> logging.Logger:
    return logging.getLogger(name)

def logger(cls) -> logging.Logger:
    cls.log = get_logger(cls.__name__)
    return cls