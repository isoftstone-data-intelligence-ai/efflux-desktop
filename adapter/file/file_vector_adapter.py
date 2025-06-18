from typing import Dict, List, Any, Optional
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredImageLoader
)
from langchain_chroma import Chroma
from application.port.outbound.file_vector_port import FileVectorPort
from application.domain.file import File
from langchain_core.embeddings import Embeddings
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from common.core.container.annotate import component
from application.port.outbound.embedding_port import EmbeddingPort  # 新增导入
import injector  # 新增注入支持
from adapter.model_sdk.embedding_adapter import EmbeddingAdapter
from application.domain.generators.generator import LLMGenerator  # 新增导入
from application.domain.generators.firm import GeneratorFirm

# 文件类型到加载器的映射（扩展支持更多类型可在此添加）
LOADER_MAPPING = {
    "txt": TextLoader,
    "pdf": PyPDFLoader,
    "docx": Docx2txtLoader,
    "pptx": UnstructuredPowerPointLoader,
    "png": UnstructuredImageLoader,
    "jpg": UnstructuredImageLoader,
    "jpeg": UnstructuredImageLoader
}

@component
class LangchainFileVectorAdapter(FileVectorPort):
    """使用Langchain实现的文件向量化适配器"""

    def __init__(
        self
    ):
        self.persist_dir = "./chroma_db"
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

    def _llm_generator(self, generator_id: str) -> LLMGenerator:
        # 获取厂商api key
        llm_generator: LLMGenerator = self.generators_port.load_generate(generator_id)
        firm: GeneratorFirm = self.user_setting_port.load_firm_setting(llm_generator.firm)
        llm_generator.set_api_key_secret(firm.api_key)
        llm_generator.check_firm_api_key()
        return llm_generator

    async def store_chunks(self, embedding: Embeddings, file: File) -> Dict[str, Any]:
        """实现文件加载、分块、向量化存储全流程"""
        # 1. 根据文件类型选择加载器
        file_ext = file.type
        loader_cls = LOADER_MAPPING.get(file_ext)
        if not loader_cls:
            raise ValueError(f"不支持的文件类型: {file_ext}")
        # 2. 加载文档内容（langchain加载器是同步的，这里用async包装）
        loader = loader_cls(file.path)
        documents = loader.load()  # 同步操作，实际项目中可能需要异步包装或线程池

        # 3. 文本分块
        chunks = self.text_splitter.split_documents(documents)

        # 4. 添加自定义元数据（继承原文档元数据并扩展）
        now_chunks = []
        for i, chunk in enumerate(chunks):
            chunk.metadata = {
                **chunk.metadata,  # 保留原始元数据（如文件路径）
                "file_id": file.id,
            }
            now_chunks.append(chunk)
            if len(now_chunks) == 10:  # 每100个分块打印一次进度
                Chroma.from_documents(
                    documents=now_chunks,
                    embedding=embedding,  # 使用领域端口替代具体实现
                    persist_directory=self.persist_dir
                )
                now_chunks = []
                print(f"已处理 {i + 1} 个分块")

        # 5. 存储到Chroma（同步操作，实际项目建议用异步包装）
        if len(now_chunks) > 0:
            Chroma.from_documents(
                documents=now_chunks,
                embedding=embedding,
                persist_directory=self.persist_dir
            )

        return {
            "file_id": file.id,
            "chunk_count": len(chunks),
            "persist_dir": self.persist_dir
        }

    async def search_chunks(self, embeddings: Embeddings, query: str, file_ids: List[str] = None) -> List[Dict]:
        """基于Chroma的相似性搜索"""
        # 加载已持久化的向量库
        vectordb = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=embeddings,
        )
        # 执行搜索（默认返回前5个结果，可根据需求调整）
        search_results = vectordb.similarity_search_with_score(
            query,
            k=3,
            filter={"file_id": {"$in": file_ids}} if file_ids else None
        )
        if not search_results:
            return []
        # 过滤指定文件ID的结果（如果有）
        filtered_results = []
        for doc, score in search_results:
            filtered_results.append(doc.page_content)
        return filtered_results
