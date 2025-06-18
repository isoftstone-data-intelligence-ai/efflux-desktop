from abc import ABC, abstractmethod
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from application.domain.file import File, FileChunk, File
from application.domain.generators.generator import LLMGenerator
from application.domain.generators.tools import Tool
from typing import Iterable, Generator, Callable, List, Optional, Dict, Any
from fastapi import APIRouter, Depends, File, UploadFile, Form
from langchain_core.embeddings import Embeddings

class FileVectorPort(ABC):
    """文件向量化专用接口"""

    @abstractmethod
    async def store_chunks(self, embedding: Embeddings, file: File) -> Dict[str, Any]:
        """存储文件块"""

    @abstractmethod
    async def search_chunks(self, embeddings: Embeddings, query: str, file_ids: List[str] = None) -> List[Dict]:
        """搜索文件块"""
