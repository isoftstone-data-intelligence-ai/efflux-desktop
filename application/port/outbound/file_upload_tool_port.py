import base64
from typing import List, Any
from application.domain.generators.tools import Tool, ToolInstance
from tools_port import ToolsPort
from common.utils.file_util import extract_pdf_text
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceBgeEmbeddings


class PdfParser(Tool):
    """
    处理用户提交的@文件,切分并向量化存储,根据用户上下文搜索相关文档内容,从而体现@文档到上下文
    """
    def __init__(self):
        super().__init__(
            name = "pdfparser",
            server_name = "pdfparser",
            description = "process upload file with pdf format",
            inputSchema = {"embedding_model":"BAAI/bge-small-zh",
                           "chroma_dir":"./chroma","build":False}
        )

class FileUploadPort(ToolsPort):
    async def load_tools(self, server_name: str) -> List[Tool]:
        """
        按 mcp server 名字获取工具集合
        :param server_name:  mcp server名字
        :return: 工具集合
        """
        file_upload_tools={"pdfparser":PdfParser}
        file_upload_tool = file_upload_tools[server_name]()
        return [file_upload_tool]
    
    @staticmethod
    async def recursive_split(tool_instance: ToolInstance,s,chunk_size=1024,chunk_overlap=128):
        text_splitter = RecursiveCharacterTextSplitter(
            separators=[ "\n\n","\n", " ", ".",",",
                "\u200B",  # Zero-width space
                "\uff0c",  # Fullwidth comma
                "\u3001",  # Ideographic comma
                "\uff0e",  # Fullwidth full stop
                "\u3002",  # Ideographic full stop
                "",],
            # Existing args
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            )
        split_docs= text_splitter.create_documents([s])
        tool_instance.inputSchema["split_docs"]= split_docs

    @staticmethod
    async def get_split_text(tool_instance: ToolInstance):
        if "path" in tool_instance.arguments.keys():
            extracted_text = extract_pdf_text(tool_instance.arguments["path"])
        else:
            extracted_text = tool_instance.arguments["text"]
        await FileUploadPort.recursive_split(tool_instance,extracted_text)
    
    
    @staticmethod
    async def get_embedding_model( tool_instance: ToolInstance):
        tool_instance.inputSchema["embedding_model_instance"]= HuggingFaceBgeEmbeddings(model_name=tool_instance.inputSchema["embedding_model"], 
                                            encode_kwargs={"normalize_embeddings": True})
        
    @staticmethod
    async def get_vectordb(tool_instance: ToolInstance):
        tool_instance.inputSchema["vectordb"] = Chroma.from_documents(documents=tool_instance.inputSchema["split_docs"],embedding=tool_instance.inputSchema["embedding_model_instance"],persist_directory=tool_instance.inputSchema["chroma_dir"])
    
    @staticmethod
    async def search(tool_instance: ToolInstance):
        sim_docs = tool_instance.inputSchema["vectordb"].similarity_search(tool_instance.arguments["query"], k=3)
        search_result=""
        for i, sim_doc in enumerate(sim_docs):
            search_result+="检索到第{}个内容：\n{} \n----------\n".format(i,sim_doc.page_content)
        return {"id":tool_instance.tool_call_id,"result":search_result}
    
    async def call_tools(self, tool_instance: ToolInstance) -> dict[str, Any]:
        """
        工具调用
        :param tool_instance: 工具实例对象
        :return: 工具调用结果
        """
        if not tool_instance.inputSchema["build"]:
            await FileUploadPort.get_split_text(tool_instance)
            await FileUploadPort.get_embedding_model(tool_instance)
            await FileUploadPort.get_vectordb(tool_instance)
            tool_instance.inputSchema["build"]=True
        result= await FileUploadPort.search(tool_instance)
        return result


if __name__ == "__main__":
    # test case
    import asyncio
    import nest_asyncio
    nest_asyncio.apply()
    tool_instance = ToolInstance(PdfParser())
    tool_instance.arguments = {"path":"./大模型基础_完整版.pdf","query":"注意力机制是什么？"}
    tool_instance.tool_call_id = "test_001"
    test_tool_port = FileUploadPort()
    result = asyncio.run(test_tool_port.call_tools(tool_instance))
    print(result)
