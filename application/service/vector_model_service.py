from typing import List
from injector import inject
from common.core.container.annotate import component
from application.port.inbound.vector_model_case import VectorModelCase
from application.port.outbound.vector_model_port import VectorModelPort  # 假设存在对应的输出端口
from application.domain.vector_model import VectorModel

@component
class VectorModelService(VectorModelCase):
    """向量模型业务逻辑实现（参考UserSettingsService格式）"""

    @inject
    def __init__(self, vector_model_port: VectorModelPort):
        """通过依赖注入获取向量模型输出端口"""
        self.vector_model_port = vector_model_port

    async def list(self) -> List[VectorModel]:
        """调用端口获取所有向量模型列表"""
        return await self.vector_model_port.list()

    async def add(self, firm: str, model: str, api_key: str, base_url: str) -> VectorModel:
        """创建并初始化向量模型实体，调用端口保存"""
        # 初始化领域模型（参考VectorModel.init方法）
        vector_model = VectorModel(
            firm=firm,
            model=model,
            api_key=api_key,
            base_url=base_url
        )
        vector_model.init()  # 生成ID和创建时间
        return await self.vector_model_port.add(vector_model)

    async def delete(self, id: str) -> bool:
        """调用端口执行删除操作"""
        return await self.vector_model_port.delete(id)
