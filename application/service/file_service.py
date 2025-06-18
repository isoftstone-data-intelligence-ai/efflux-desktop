from typing import List, Dict, Optional, Any

from application.domain.file import File, FileChunk
from common.core.container.annotate import component
from application.port.inbound.file_case import FileCase
from application.port.outbound.file_port import FilePort
from application.port.outbound.task_port import TaskPort  # 新增导入
import injector
from common.core.logger import get_logger
from application.domain.tasks.task import Task, TaskType  # 新增导入

logger = get_logger(__name__)

@component
class FileService(FileCase):

    @injector.inject
    def __init__(self, file_port: FilePort, task_port: TaskPort):  # 注入TaskPort
        self.file_port = file_port
        self.task_port = task_port

    async def get_allowed_file_types(self) -> List[str]:
        return self.file_port.get_allowed_file_types()

    async def upload_file(self, file: Any, generator_id: str, **kwargs) -> File:
        logger.info(f"上传文件 ---> [filename={getattr(file, 'filename', 'unknown')}]")
        # 先快速上传文件获取基本信息
        file_entity = await self.file_port.upload(file, **kwargs)

        # 创建异步处理任务
        task = Task.from_singleton(
            client_id=file_entity.id,  # 使用文件ID作为任务ID
            task_type=TaskType.FILE_PROCESSING,
            data={
                "file_entity": file_entity,
                "generator_id": generator_id,
            }
        )
        self.task_port.execute_task(task)
        logger.info(f"已创建文件处理任务: {task.id}")

        return file_entity

    async def get_file_list(
        self,
        content_keyword: Optional[str] = None,
        filename_keyword: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        logger.info(f"查询文件列表 ---> [content_keyword={content_keyword}, filename_keyword={filename_keyword}]")
        return self.file_port.file_list(
            content_keyword=content_keyword,
            filename_keyword=filename_keyword,
            **kwargs
        )

    async def delete_files(self, file_id_list: List[str], **kwargs) -> Dict[str, Any]:
        logger.info(f"删除文件 ---> {file_id_list}")
        return self.file_port.delete(file_id_list, **kwargs)
