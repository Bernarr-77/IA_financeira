from fastapi import HTTPException, status, Depends
import os
import secrets
from dotenv import load_dotenv
from app.core.schemas import EvolutionSchema

load_dotenv(override=True)

CHAVE_VERDADEIRA = os.getenv("AUTHENTICATION_API_KEY")

if not CHAVE_VERDADEIRA:
    raise RuntimeError("A variável AUTHENTICATION_API_KEY não foi configurada no .env")

async def validar_api_key(payload: EvolutionSchema):
    chave_recebida = payload.apikey
    if not secrets.compare_digest(chave_recebida, CHAVE_VERDADEIRA):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API inválida"
        )
    return True
