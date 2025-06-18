from abc import ABC, abstractmethod
from application.domain.file import File, FileChunk
from typing import List, Dict, Optional, Any

class FileCase(ABC):

    @abstractmethod
    async def get_allowed_file_types(self) -> List[str]:
        """获取允许上传的文件类型列表"""

    @abstractmethod
    async def upload_file(self, file: Any, generator_id: str, **kwargs) -> File:
        """上传文件"""

    @abstractmethod
    async def get_file_list(
        self,
        content_keyword: Optional[str] = None,
        filename_keyword: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """获取文件列表"""

    @abstractmethod
    async def delete_files(self, file_id_list: List[str], **kwargs) -> Dict[str, Any]:
        """删除文件"""
