from pydantic import BaseModel
from typing import List, Optional
from fastapi import UploadFile

class FileDelVo(BaseModel):
    file_id_list: List[str]
