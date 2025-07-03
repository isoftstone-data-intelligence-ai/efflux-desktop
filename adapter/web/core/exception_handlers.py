from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from common.core.errors.common_exception import CommonException
from common.core.errors.common_error_code import CommonErrorCode
from common.core.errors.business_exception import BusinessException
from adapter.web.vo.base_response import BaseResponse
from common.core.logger import get_logger

logger = get_logger(__name__)


async def common_exception_handler(request: Request, exc: CommonException):
    """
    处理自定义的 CommonException 异常
    """
    logger.error(f"CommonException: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=500,  # HTTP状态码不能超过599
        content=BaseResponse.from_error(code=exc.code, message=exc.message, error_message=exc.dynamics_message).dict()
    )

async def business_exception_handler(request: Request, exc: BusinessException):
    """
    处理自定义的 BusinessException 异常
    """
    logger.error(f"BusinessException: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=200,  # HTTP状态码不能超过599
        content=BaseResponse.from_error(code=exc.code, message=exc.message, error_message=exc.dynamics_message).dict()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    处理 FastAPI 的请求验证异常
    """
    errors = exc.errors()
    error_messages = []

    for error in errors:
        loc = " -> ".join([str(l) for l in error.get("loc", [])])
        msg = error.get("msg", "")
        error_messages.append(f"{loc}: {msg}")

    error_msg = "; ".join(error_messages)
    logger.warning(f"请求参数验证失败: {error_msg}")

    return JSONResponse(
        status_code=422,
        content=BaseResponse.from_error(message=error_msg, code=CommonErrorCode.VALIDATION_ERROR.value,
                                        error_message=str(exc)).dict()
        # content={
        #     "success": False,
        #     "error": {
        #         "code": ErrorCode.VALIDATION_ERROR.value,
        #         "type": "validation_error",
        #         "message": f"请求参数验证失败: {error_msg}",
        #         "details": errors
        #     }
        # }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    处理 HTTP 异常
    """
    logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content=BaseResponse.from_error(message=exc.detail, code=exc.status_code,
                                        error_message=str(exc)).dict()
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    处理所有未被其他处理器处理的异常
    """
    logger.error(f"未处理的异常: {str(exc)}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=BaseResponse.from_error(message=CommonErrorCode.INTERNAL_SERVER_ERROR.desc,
                                        code=CommonErrorCode.INTERNAL_SERVER_ERROR.value, error_message=str(exc)).dict()
    )