from abc import ABC, abstractmethod
from application.domain.vector_model import VectorModel
from typing import List

class VectorModelPort(ABC):
    """向量模型输出端口抽象接口（参考UserSettingPort格式）"""

    @abstractmethod
    async def list(self) -> List[VectorModel]:
        """
        获取所有向量模型配置集合（对应VectorModelService.list）
        :return: 向量模型对象列表
        """

    @abstractmethod
    async def add(self, vector_model: VectorModel) -> VectorModel:
        """
        保存新的向量模型配置（对应VectorModelService.add）
        :param vector_model: 已初始化的向量模型领域对象
        :return: 保存后的向量模型对象（可能包含持久化生成的额外信息）
        """

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """
        删除指定ID的向量模型配置（对应VectorModelService.delete）
        :param id: 向量模型ID
        :return: 删除操作是否成功
        """
