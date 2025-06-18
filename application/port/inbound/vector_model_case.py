from abc import ABC, abstractmethod
from typing import List
from application.domain.vector_model import VectorModel

class VectorModelCase(ABC):
    """向量模型业务用例抽象接口（参考 model_case.py 格式）"""

    @abstractmethod
    async def list(self) -> List[VectorModel]:
        """
        获取所有向量模型列表（对应 controller 的 list 接口）
        :return: 向量模型对象列表
        """

    @abstractmethod
    async def add(self, firm: str, model: str, api_key: str, base_url: str) -> VectorModel:
        """
        新增向量模型（对应 controller 的 add 接口）
        :param firm: 所属厂商名称
        :param model: 向量模型名称
        :param api_key: 模型关联的 API Key
        :param base_url: 模型基础URL
        :return: 新增的向量模型对象
        """

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """
        删除指定向量模型（对应 controller 的 delete 接口）
        :param id: 待删除的向量模型 ID
        :return: 操作是否成功（True/False）
        """
