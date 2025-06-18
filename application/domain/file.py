from datetime import datetime
from enum import Enum

from common.utils.common_utils import create_uuid
from common.utils.file_util import open_and_base64
from common.utils.time_utils import create_from_second_now, create_from_timestamp, create_from_timestamp_to_int
from application.domain.generators.tools import ToolInstance
from pydantic import BaseModel
from typing import Optional, List, Literal, Dict, Any
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from typing import ClassVar, List


class File(BaseModel):
    """文件实体"""

    # 可转化的文件类型后缀
    CONVERTIBLE_EXTS: ClassVar[List[str]] = ['pdf', 'doc', 'docx', 'txt', 'md', 'html', 'ppt', 'pptx', 'xls', 'xlsx']

    # 文件ID
    id: Optional[str] = None
    # 文件名
    name: Optional[str] = None
    # 文件路径
    path: Optional[str] = None
    # 文件大小
    size: Optional[int] = None
    # 文件类型
    type: Optional[str] = None
    # 文件创建时间
    created: Optional[datetime] = None

    def init(self):
        self.id = create_uuid()
        self.created = create_from_second_now()

    # 自定义处理模型转化为字典的方法
    def model_dump(self, **kwargs):
        # 使用 super() 获取字典格式
        data = super().model_dump()
        # 转换 datetime 字段为字符串（ISO 格式）
        data['created'] = self.created.isoformat() if self.created else None
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # 确保将创建的字符串转换为 datetime 对象
        if 'created' in obj and isinstance(obj['created'], str):
            obj['created'] = datetime.fromisoformat(obj['created'])
        return super().model_validate(obj)

    def is_convertible(self) -> bool:
        """检查文件是否可转化"""
        if not self.name:
            return False
        ext = self.name.split('.')[-1].lower()
        return ext in self.CONVERTIBLE_EXTS


class FileChunk(BaseModel):
    """文件块实体"""

    # Chroma ID
    id: Optional[str] = None
    # 文件ID
    file_id: Optional[str] = None
    # 文件块内容
    content: Optional[str] = None


    def init(self):
        self.id = create_uuid()
