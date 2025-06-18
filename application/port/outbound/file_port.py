from abc import ABC, abstractmethod
from application.domain.generators.chat_chunk.chunk import ChatStreamingChunk
from application.domain.file import File, FileChunk, File
from application.domain.generators.generator import LLMGenerator
from application.domain.generators.tools import Tool
from typing import Iterable, Generator, Callable, List, Optional, Dict, Any
from fastapi import APIRouter, Depends, File, UploadFile, Form

class FilePort(ABC):

    @abstractmethod
    def get_allowed_file_types(self) -> list[str]:
        """
        获取允许上传的文件类型
        :return: 允许的文件类型后缀列表
        """

    @abstractmethod
    async def upload(self, file: UploadFile, **kwargs) -> File:
        """
        上传文件
        :param file: 文件
        :param kwargs: 参数
        :return:
        """

    @abstractmethod
    def file_list(self,
            file_id_list: list[str] = None,
            content_keyword: str = None, filename_keyword: str = None,
            **kwargs) -> list[dict[str, Any]]:
        """
        查询 文件列表
        :param content_keyword: 内容关键字
        :param filename_keyword: 文件名关键字
        :param kwargs: 参数
        :return: list[dict[str, Any]] 文件信息列表
        """

    @abstractmethod
    def delete(self, file_id_list: list[str], **kwargs) -> dict[str, Any]:
        """
        删除文件
        :param file_id_list: 文件id列表
        :param kwargs: 参数
        :return: dict[str, Any]
        """
