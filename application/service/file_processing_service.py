import injector
from typing import List

from application.domain.file import File, FileChunk
from application.port.outbound.file_vector_port import FileVectorPort
from application.service.base_service.embedding_service import EmbeddingService
from common.core.container.annotate import component
from common.core.logger import get_logger

logger = get_logger(__name__)

@component
class FileProcessingService:

    @injector.inject
    def __init__(
        self,
        file_vectordb_port: FileVectorPort,
        embedding_service: EmbeddingService,
    ):
        self.file_vectordb_port = file_vectordb_port
        self.embedding_service = embedding_service

    async def process_file_to_chunks(self, generator_id: str, file_entity: File) -> List[FileChunk]:
        # 原代码未等待异步方法，导致得到协程对象，添加 await 等待获取实际的 Embeddings 实例
        embeddings = await self.embedding_service.get_embeddings(generator_id)
        return await self.file_vectordb_port.store_chunks(embeddings, file_entity)
