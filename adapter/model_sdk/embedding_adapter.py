from application.port.outbound.embedding_port import EmbeddingPort
from application.domain.generators.generator import LLMGenerator
from common.core.container.container import get_container
from common.core.errors.common_exception import CommonException
from common.core.logger import get_logger
from langchain_openai import OpenAIEmbeddings
from application.domain.generators.firm import GeneratorFirm
from application.domain.vector_model import VectorModel
from common.core.container.annotate import component
from application.port.outbound.embedding_port import EmbeddingPort
import httpx  # 新增HTTP客户端依赖
from typing import List, Any
import os
from openai import OpenAI

logger = get_logger(__name__)
from langchain_core.embeddings import Embeddings

class TongyiEmbeddings(Embeddings):
    """通义千问向量模型适配器"""

    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """生成多个文本的嵌入向量"""

        client = OpenAI(
            api_key=self.api_key,  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
            base_url=self.base_url  # 百炼服务的base_url
        )

        completion = client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=1024,# 指定向量维度（仅 text-embedding-v3及 text-embedding-v4支持该参数）
            encoding_format="float"
        )
        result = completion.data
        result = [item.embedding for item in result]  # 提取嵌入向量

        return result

    def embed_query(self, text: str) -> list[float]:
        """生成单个查询文本的嵌入向量"""
        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        completion = client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=1024,
            encoding_format="float"
        )
        result = completion.data
        result = [item.embedding for item in result]
        return result[0]


@component
class EmbeddingAdapter(EmbeddingPort):
    """大模型嵌入适配器工厂（基于LLMGenerator动态选择）"""

    def get_embeddings(self, embeddings_model_settings: VectorModel) -> EmbeddingPort:
        """
        获取指定厂商对应的嵌入适配器
        :param embeddings_model_settings: 向量模型配置
        :return: 对应的EmbeddingPort实现
        """
        firm = embeddings_model_settings.firm
        if firm == "openai":
            return OpenAIEmbeddings(
                model=embeddings_model_settings.model,
                api_key=embeddings_model_settings.api_key,
                base_url=embeddings_model_settings.base_url,
            )
        elif firm == "tongyi":  # 单独处理通义千问
            return TongyiEmbeddings(
                model=embeddings_model_settings.model,
                api_key=embeddings_model_settings.api_key,
                base_url=embeddings_model_settings.base_url,
            )
        else:
            raise ValueError(f"不支持的向量模型厂商: {firm}")