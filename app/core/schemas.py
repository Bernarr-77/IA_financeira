from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Any

class KeySchema(BaseModel):
    remoteJid: Optional[str] = None
    id: Optional[str] = None
    model_config = ConfigDict(extra='allow')

class AudioSchema(BaseModel):
    url: Optional[str] = None
    mimetype: Optional[str] = None
    model_config = ConfigDict(extra='allow')

class MessageSchema(BaseModel):
    conversation: Optional[str] = None
    audioMessage: Optional[AudioSchema] = None
    model_config = ConfigDict(extra='allow')

class DataSchema(BaseModel):
    key: Optional[KeySchema] = None
    message: Optional[MessageSchema] = None
    pushName: Optional[str] = None
    model_config = ConfigDict(extra='allow')


class EvolutionSchema(BaseModel):
    event: Optional[str] = None
    instance: Optional[str] = None
    data: Optional[DataSchema] = None
    server_url: Optional[str] = None
    apikey: Optional[str] = None
    model_config = ConfigDict(extra='allow')