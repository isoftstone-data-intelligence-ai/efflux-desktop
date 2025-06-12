import os
from typing import Any, List, Dict, Optional
import jsonlines
from common.utils.file_util import check_file_and_create, del_file
from common.core.container.annotate import component
from application.domain.file import File, FileChunk
from application.port.outbound.file_port import FilePort

@component
class FileAdapter(FilePort):

    def __init__(self):
        self.file_info_list_path = "files/files_list.jsonl"
        check_file_and_create(self.file_info_list_path)

    def get_allowed_file_types(self) -> List[str]:
        """直接返回允许的文件类型"""
        return File.CONVERTIBLE_EXTS

    async def upload(self, file: Any, **kwargs) -> File:
        """保存文件元信息到JSONL"""
        file_entity = File(
            name=file.filename,
            size=file.size,
            type=file.content_type
        )
        file_entity.init()
        # 保存文件
        check_file_and_create(f"uploads/{file_entity.id}", await file.read())
        # 保存文件记录
        with jsonlines.open(self.file_info_list_path, mode='a') as writer:
            writer.write(file_entity.model_dump())

        return file_entity

    def file_list(self,
                 content_keyword: str = None,
                 filename_keyword: str = None,
                 **kwargs) -> List[Dict[str, Any]]:
        """从JSONL读取文件列表"""
        files = []
        if not os.path.exists(self.file_info_list_path):
            return files

        with jsonlines.open(self.file_info_list_path, mode='r') as reader:
            for obj in reader:
                if filename_keyword and filename_keyword not in obj.get('name', ''):
                    continue
                files.append(obj)
        return files

    def delete(self, file_id_list: List[str], **kwargs) -> Dict[str, Any]:
        """从JSONL删除文件记录"""
        remaining_files = []
        deleted_count = 0

        with jsonlines.open(self.file_info_list_path, mode='r') as reader:
            for obj in reader:
                if obj.get('id') not in file_id_list:
                    remaining_files.append(obj)
                else:
                    deleted_count += 1

        with jsonlines.open(self.file_info_list_path, mode='w') as writer:
            for file in remaining_files:
                writer.write(file)

        return {"deleted_count": deleted_count}

    # chunks相关操作使用ChromaDB（由其他Adapter实现）
    def chunk_list(self,
                  content_keyword: str = None,
                  file_id_list: List[str] = None,
                  **kwargs) -> List[Dict[str, Any]]:
        """由专门的VectorDBAdapter实现"""
        raise NotImplementedError("Chunk operations should be handled by VectorDBAdapter")
