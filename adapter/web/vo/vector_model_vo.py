from pydantic import BaseModel

class CreateVectorModelRequest(BaseModel):
    firm: str  # 厂商名称
    model: str  # 模型名称
    api_key: str  # API Key
    base_url: str  # 模型基础URL

class DeleteVectorModelRequest(BaseModel):
    id: str
