from fastapi import HTTPException, status, Request
import os
import secrets
from dotenv import load_dotenv

load_dotenv(override=True)

CHAVE_VERDADEIRA = os.getenv("AUTHENTICATION_API_KEY")

async def validar_api_key(request: Request):
    try:
        # Lê o JSON e guarda no estado da requisição para ser reusado
        body = await request.json()
        request.state.payload = body
        
        chave_recebida = body.get("apikey")
        
        if not chave_recebida or not secrets.compare_digest(str(chave_recebida), str(CHAVE_VERDADEIRA)):
            print(f"❌ Chave inválida recebida: {chave_recebida}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Chave de API inválida"
            )
        return body
    except Exception as e:
        print(f"❌ Erro na validação: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar a requisição"
        )
