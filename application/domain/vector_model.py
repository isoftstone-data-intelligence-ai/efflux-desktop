from datetime import datetime
from pydantic import BaseModel
from typing import Optional, ClassVar
from common.utils.common_utils import create_uuid
from common.utils.time_utils import create_from_second_now


class VectorModel(BaseModel):
    """向量模型领域实体（参考 File 类结构）"""

    id: Optional[str] = None  # 模型ID（初始化时生成）
    created: Optional[datetime] = None  # 创建时间（初始化时生成）

    # 业务相关字段
    firm: str  # 所属厂商名称
    model: str  # 向量模型名称
    api_key: str  # 模型关联的 API Key
    base_url: str  # 模型基础URL

    def init(self):
        """初始化生成ID和创建时间（参考 File.init 方法）"""
        self.id = create_uuid()
        self.created = create_from_second_now()

    def model_dump(self, **kwargs):
        """自定义序列化方法（参考 File.model_dump 处理 datetime 字段）"""
        data = super().model_dump(**kwargs)
        if self.created:
            data["created"] = self.created.isoformat()
        return data

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """自定义反序列化方法（参考 File.model_validate 转换 datetime 字符串）"""
        if "created" in obj and isinstance(obj["created"], str):
            obj["created"] = datetime.fromisoformat(obj["created"])
        return super().model_validate(obj, **kwargs)
