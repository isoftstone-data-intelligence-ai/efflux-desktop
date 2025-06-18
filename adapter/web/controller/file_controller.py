from fastapi import APIRouter, Depends, UploadFile, File, Query, Form
from common.core.logger import get_logger
from common.core.container.container import get_container
from application.port.inbound.file_case import FileCase
from adapter.web.vo.base_response import BaseResponse
from adapter.web.vo.file_vo import FileDelVo
from typing import List, Optional

logger = get_logger(__name__)

router = APIRouter(prefix="/api/file", tags=["FILE"])

def file_case() -> FileCase:
    return get_container().get(FileCase)

@router.get("/allowed_types")
async def get_allowed_file_types(
    file_service: FileCase = Depends(file_case)
) -> BaseResponse:
    return BaseResponse.from_success(
        data=await file_service.get_allowed_file_types()
    )

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    generator_id: Optional[str] = Form(None),
    file_service: FileCase = Depends(file_case)
) -> BaseResponse:
    return BaseResponse.from_success(
        data=await file_service.upload_file(file, generator_id)
    )

@router.get("/list")
async def get_files(
    content_keyword: Optional[str] = Query(None),
    filename_keyword: Optional[str] = Query(None),
    file_service: FileCase = Depends(file_case)
) -> BaseResponse:
    return BaseResponse.from_success(data=await file_service.get_file_list(
        content_keyword=content_keyword,
        filename_keyword=filename_keyword
    ))

@router.delete("/batch")
async def delete_files(
    vo: FileDelVo,
    file_service: FileCase = Depends(file_case)
) -> BaseResponse:
    return BaseResponse.from_success(
        data=await file_service.delete_files(file_id_list=vo.file_id_list)
    )