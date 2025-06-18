from abc import ABC, abstractmethod
from typing import List
from langchain_core.embeddings import Embeddings
from application.domain.vector_model import VectorModel

class EmbeddingPort(ABC):
    """大模型文本嵌入领域端口"""

    @abstractmethod
    def get_embeddings(self, embeddings_model_settings: VectorModel) -> Embeddings:
        """获取指定生成器的向量模型实例"""
        pass