from pydantic import BaseModel, Field, field_validator, ConfigDict
import re
from typing import Optional

class KeySchema(BaseModel):
    remoteJid: str = Field(min_length=5, max_length=40)
    id: str
    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator('remoteJid', mode='before')
    @classmethod
    def limpar_jid(cls, v: str) -> str:
        if isinstance(v, str):
            return v.split("@")[0]
        return v

class AudioSchema(BaseModel):
    url: Optional[str] = None
    mimetype: Optional[str] = None
    fileSha256: Optional[str] = None
    fileLength: Optional[str] = None
    seconds: Optional[int] = None
    ptt: Optional[bool] = None
    mediaKey: Optional[str] = None
    fileEncSha256: Optional[str] = None
    directPath: Optional[str] = None
    mediaKeyTimestamp: Optional[str] = None


class MessageSchema(BaseModel):
    conversation: Optional[str] = None
    audioMessage: Optional[AudioSchema] = None

class DataSchema(BaseModel):
    key: KeySchema
    message: MessageSchema
    pushName: str


class EvolutionSchema(BaseModel):
    event: str = Field(min_length=1, max_length=100)
    instance: str
    data: DataSchema 
    server_url: Optional[str] = None
    apikey: str