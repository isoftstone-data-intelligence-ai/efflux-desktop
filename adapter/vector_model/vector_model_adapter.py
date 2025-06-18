import os
from application.port.outbound.vector_model_port import VectorModelPort
from application.domain.vector_model import VectorModel
from common.core.container.annotate import component
from common.utils.file_util import check_file_and_create
import jsonlines
from typing import List, Dict, Any

@component
class VectorModelAdapter(VectorModelPort):
    """向量模型持久化适配器（使用JSONL文件存储）"""

    vector_models_file = "vector_models/vector_models.jsonl"

    def __init__(self):
        check_file_and_create(self.vector_models_file)

    async def list(self) -> List[VectorModel]:
        """从JSONL文件读取所有向量模型配置"""
        models = []
        if not os.path.exists(self.vector_models_file):
            return models
        with jsonlines.open(self.vector_models_file, mode='r') as reader:
            for obj in reader:
                models.append(VectorModel.model_validate(obj))
        return models

    async def add(self, vector_model: VectorModel) -> None:
        """追加写入新向量模型到JSONL文件"""
        with jsonlines.open(self.vector_models_file, mode='a') as writer:
            writer.write(vector_model.model_dump())

    async def delete(self, id: str) -> bool:
        """从JSONL文件删除指定ID的模型配置"""
        remaining_models = []
        deleted = False
        with jsonlines.open(self.vector_models_file, mode='r') as reader:
            for obj in reader:
                if obj.get("id") != id:
                    remaining_models.append(obj)
                else:
                    deleted = True
        with jsonlines.open(self.vector_models_file, mode='w') as writer:
            for model in remaining_models:
                writer.write(model)
        return deleted