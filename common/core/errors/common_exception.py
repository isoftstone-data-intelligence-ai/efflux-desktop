from common.core.errors.base_error_code import BaseErrorCode
from typing import Optional
import traceback
from functools import wraps
from common.core.logger import get_logger

logger = get_logger(__name__)


class CommonException(Exception):
    """所有应用级别的异常的基类"""

    def __init__(self, error_code: BaseErrorCode, dynamics_message: Optional[str]):
        # 设置错误消息、错误码和异常类型
        self.message = error_code.get_desc()
        self.code = error_code.get_value()
        self.dynamics_message = dynamics_message
        # 调用父类的初始化方法
        super().__init__(self.message)

    def __str__(self):
        # 重写异常的输出方式
        return f"{self.code}:{self.dynamics_message}"


# 自定义装饰器，处理异常，异常作为参数传递给 default_func
def handle_exception(default_func):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Exception occurred in {func.__name__}: {e}")
                traceback.print_exc()  # 打印异常栈信息
                return default_func(*args, **kwargs, exception=e)  # 将异常对象作为参数传递给 default_func
        return wrapper
    return decorator

# 自定义异步装饰器，处理异常，异常作为参数传递给 default_func
def handle_async_exception(default_func):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # 这里是异步生成器的调用
                async for result in func(*args, **kwargs):
                    yield result  # 继续生成结果
            except Exception as e:
                # 获取最内层的异常
                inner_exc = _get_inner_exception(e)
                logger.error(f"Exception occurred: {inner_exc}")
                traceback.print_exc()  # 打印异常栈信息
                # 异常发生时调用 default_func 来生成默认值
                # 假设 default_func 返回一个异步生成器（即实现了 __aiter__ 和 __anext__）
                async for result in default_func(exception=inner_exc):
                    yield result
        return wrapper
    return decorator

def _get_inner_exception(exc):
    # 遍历 `__cause__` 直到没有更多的嵌套异常
    while hasattr(exc, "exceptions") and len(exc.exceptions) > 0:
        exc = exc.exceptions[0]
    return exc