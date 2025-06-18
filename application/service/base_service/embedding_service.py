import injector
from langchain_core.embeddings import Embeddings

from application.port.outbound.embedding_port import EmbeddingPort
from application.port.outbound.generators_port import GeneratorsPort
from application.port.outbound.vector_model_port import VectorModelPort
from common.core.logger import get_logger

logger = get_logger(__name__)

class EmbeddingService:

    @injector.inject
    def __init__(
        self,
        embedding_port: EmbeddingPort,
        generators_port: GeneratorsPort,
        vector_model_port: VectorModelPort,
    ):
        self.embedding_port = embedding_port
        self.vector_model_port = vector_model_port
        self.generators_port = generators_port

    async def get_embeddings(self, generator_id: str) -> Embeddings:
        llm_generator = self.generators_port.load_generate(generator_id)
        logger.debug(f"加载的生成器: {llm_generator}")
        embeddings_model_settings = None
        embeddings_model_settings_list = await self.vector_model_port.list()
        logger.debug(f"向量模型设置列表: {embeddings_model_settings_list}")
        if not embeddings_model_settings_list:
            raise ValueError("未找到向量模型设置")
        # 取 最新的 向量模型 设置
        for i in embeddings_model_settings_list:
            if i.firm == llm_generator.firm:
                embeddings_model_settings = i
        if not embeddings_model_settings:
            raise ValueError(f"未找到对应的向量模型设置: {llm_generator.firm}")
        embeddings = self.embedding_port.get_embeddings(embeddings_model_settings)
        return embeddings
