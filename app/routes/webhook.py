from fastapi import APIRouter, Depends
from app.core.security import validar_api_key
import json
import os
from dotenv import load_dotenv
from app.core.schemas import EvolutionSchema
import httpx


load_dotenv()

router = APIRouter(prefix="/webhook", tags=["Webhook"])

EVENTOS_PERMITIDOS = os.getenv("WEBHOOK_EVENTS_FILTER", "").split(",")


async def buscar_base64(id_audio, audio, nome_instancia, url_servidor, api_key):
    url = f"{url_servidor}/chat/getBase64FromMediaMessage/{nome_instancia}"
    headers = {"apikey": api_key}
    corpo = {
    "message": {
        "key": {"id": id_audio},
        "message": {"audioMessage": audio.model_dump()}
    }
}
    
    async with httpx.AsyncClient() as client:
        resposta = await client.post(url, headers=headers, json=corpo)
        return resposta.json()



@router.post("/evolution")
async def capturar_payload(payload: EvolutionSchema,dependencia = Depends(validar_api_key)):
    try:
        evento = payload.event
        if EVENTOS_PERMITIDOS and evento not in EVENTOS_PERMITIDOS:
            return {"status": "ignored", "event": evento}
        if payload.data.message.conversation:
            texto_extraido = payload.data.message.conversation
        elif payload.data.message.audioMessage:
            audio = payload.data.message.audioMessage
            id_audio = payload.data.key.id
            nome_instancia = payload.instance
            url = payload.server_url
            api = payload.apikey
            resultado_base64 = await buscar_base64(id_audio=id_audio,
                                                    audio=audio,
                                                    nome_instancia=nome_instancia,
                                                    url_servidor=url,
                                                    api_key=api)
            audio_pronto = resultado_base64.get("base64", None)
    except Exception as e:
        print(f"❌ Erro ao capturar payload: {e}")
        return {"status": "error"}
    return {"status": "success"}

