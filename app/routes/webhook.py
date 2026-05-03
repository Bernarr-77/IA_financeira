import os
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from app.core.security import validar_api_key
from app.service.agent import chamar_gemini, transcrever_audio
from datetime import datetime
import httpx
from app.db.session import get_db
from app.service.tools import criar_usuario, buscar_usuario, salvar_conversa_usuario
from sqlalchemy.orm import Session
from app.db.models import Role
from app.db.session import SessionLocal

router = APIRouter(prefix="/webhook")

# Só processa eventos de mensagens recebidas
EVENTOS_PERMITIDOS = ["messages.upsert"]

# Cache de IDs de mensagens já processadas (evita resposta dupla caso a Evolution reenvie o webhook)
MENSAGENS_PROCESSADAS: set[str] = set()


# ─────────────────────────────────────────────
# Funções auxiliares
# ─────────────────────────────────────────────

async def buscar_base64_audio(id_audio: str, audio_data: dict, nome_instancia: str, url_servidor: str, api_key: str) -> dict:
    """Baixa o áudio da Evolution API em formato base64 para enviar ao Gemini."""
    url = f"{url_servidor}/chat/getBase64FromMediaMessage/{nome_instancia}"
    headers = {"Content-Type": "application/json", "apikey": api_key}
    corpo = {
        "message": {
            "key": {"id": id_audio},
            "message": {"audioMessage": audio_data}
        }
    }
    async with httpx.AsyncClient() as client:
        try:
            resposta = await client.post(url, headers=headers, json=corpo)
            return resposta.json()
        except Exception:
            return {}


async def resolver_lid_para_numero(jid_lid: str, push_name: str, nome_instancia: str, url_servidor: str, api_key: str) -> str:
    """
    A Evolution API às vezes envia o remetente como '@lid' (ID interno do dispositivo),
    que não pode ser usado para enviar mensagens. Esta função busca o número real do
    contato (ex: 5531...@s.whatsapp.net) pelo nome exibido (pushName) na agenda da instância.
    """
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            resposta = await client.post(
                f"{url_servidor}/chat/findContacts/{nome_instancia}",
                headers=headers,
                json={}  # sem filtro retorna todos os contatos
            )
            contatos = resposta.json()

            # A resposta pode ser uma lista direta ou um objeto com chave "contacts"
            if not isinstance(contatos, list):
                contatos = contatos.get("contacts", [])

            for contato in contatos:
                remote_jid = contato.get("remoteJid", "")
                # Compara o pushName e garante que é um número real (não outro @lid)
                if contato.get("pushName") == push_name and "@s.whatsapp.net" in remote_jid:
                    return remote_jid.split("@")[0]

        except Exception:
            pass

    return jid_lid  # fallback: retorna o @lid original (pode falhar ao enviar)


async def enviar_resposta_whatsapp(numero: str, texto: str, url_servidor: str, nome_instancia: str, api_key: str):
    """Envia a resposta da IA de volta para o usuário via Evolution API."""
    url = f"{url_servidor}/message/sendText/{nome_instancia}"
    headers = {"Content-Type": "application/json", "apikey": api_key}
    body = {
        "number": numero,
        "text": texto,
        "delay": 1200,       # simula digitação (ms)
        "linkPreview": False,
        "checkContact": False,
    }
    async with httpx.AsyncClient() as client:
        try:
            resposta = await client.post(url, headers=headers, json=body)
            return resposta.json()
        except Exception:
            return None


# ─────────────────────────────────────────────
# Processamento principal (roda em background)
# ─────────────────────────────────────────────

async def processar_mensagem(payload: dict, db: Session):
    """
    Processa uma mensagem recebida do WhatsApp:
    1. Filtra mensagens próprias e duplicadas
    2. Resolve o número de destino (inclusive @lid)
    3. Extrai texto ou áudio da mensagem
    4. Envia para o Gemini e devolve a resposta ao usuário
    """
    try:
        data = payload.get("data", {})
        key = data.get("key", {})
        msg_id = key.get("id", "")

        # ── Filtro de duplicatas ──────────────────────────────────────────────
        # A Evolution pode reenviar o webhook se demorar a responder.
        # O BackgroundTask já evita isso, mas este cache é uma segurança extra.
        if msg_id in MENSAGENS_PROCESSADAS:
            return
        MENSAGENS_PROCESSADAS.add(msg_id)
        if len(MENSAGENS_PROCESSADAS) > 1000:  # evita vazamento de memória
            MENSAGENS_PROCESSADAS.pop()

        # ── Ignora mensagens enviadas pelo próprio bot ────────────────────────
        if key.get("fromMe"):
            return

        # ── Extrai dados do payload ───────────────────────────────────────────
        message = data.get("message", {})
        remote_jid = key.get("remoteJid", "")
        push_name = data.get("pushName", "")
        nome_instancia = payload.get("instance")
        url_servidor = payload.get("server_url") or os.getenv("SERVER_URL")
        api_key = payload.get("apikey") or os.getenv("AUTHENTICATION_API_KEY")

        # ── Resolve o número de destino ───────────────────────────────────────
        if "@lid" in remote_jid:
            # @lid é um ID interno do dispositivo — não serve para enviar mensagens.
            # Busca o número real pelo pushName na agenda da instância.
            jid_destino = await resolver_lid_para_numero(remote_jid, push_name, nome_instancia, url_servidor, api_key)
        elif "@s.whatsapp.net" in remote_jid:
            # Número padrão: extrai só os dígitos (ex: 55319...)
            jid_destino = remote_jid.split("@")[0]
        else:
            # Grupos ou outros tipos: usa o JID completo
            jid_destino = remote_jid

        # ── Processa a mensagem ───────────────────────────────────────────────
        texto_mensagem = message.get("conversation") or message.get("extendedTextMessage", {}).get("text")
        audio_mensagem = message.get("audioMessage")
        resposta_gemini = None

        # ── Lógica de Usuário ─────────────────────────────────────────────────
        usuario = buscar_usuario(numero=jid_destino, db=db)
        if not usuario:
            usuario = criar_usuario(numero=jid_destino, nome=push_name, db=db, instancia=nome_instancia)
        elif usuario.instancia != nome_instancia:
            usuario.instancia = nome_instancia
            db.add(usuario)
            db.commit()
            db.refresh(usuario)

        if texto_mensagem:
            # Salva a mensagem do usuário
            salvar_conversa_usuario(texto=texto_mensagem, numero=jid_destino, db=db, role=Role.USER)
            
            resposta_gemini = await chamar_gemini(
                text=texto_mensagem,
                nome=push_name,
                numero=jid_destino,
                data_hoje=datetime.now().strftime("%d/%m/%Y %H:%M")
            )

        elif audio_mensagem:
            resultado_base64 = await buscar_base64_audio(msg_id, audio_mensagem, nome_instancia, url_servidor, api_key)
            audio_base64 = resultado_base64.get("base64")
            
            if audio_base64:
                # 1. Transcreve o áudio primeiro
                transcricao = await transcrever_audio(audio_base64, audio_mensagem.get("mimetype"))
                
                # 2. Salva a transcrição no banco de dados
                texto_para_banco = transcricao if transcricao else "[Áudio não transcrito]"
                salvar_conversa_usuario(texto=texto_para_banco, numero=jid_destino, db=db, role=Role.USER)
                
                # 3. Se transcreveu algo, manda para a Bia processar como se fosse texto
                if transcricao:
                    resposta_gemini = await chamar_gemini(
                        text=transcricao,
                        nome=push_name,
                        numero=jid_destino,
                        data_hoje=datetime.now().strftime("%d/%m/%Y %H:%M")
                    )

        # ── Envia a resposta e Salva ──────────────────────────────────────────
        if resposta_gemini and jid_destino:
            # Salva a resposta da IA
            salvar_conversa_usuario(texto=resposta_gemini, numero=jid_destino, db=db, role=Role.ASSISTENTE)
            
            await enviar_resposta_whatsapp(jid_destino, resposta_gemini, url_servidor, nome_instancia, api_key)

    except Exception as e:
        print(f"❌ Erro no processamento: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────
# Endpoint do webhook
# ─────────────────────────────────────────────

@router.post("/evolution")
async def capturar_payload(background_tasks: BackgroundTasks, request: Request, payload: dict = Depends(validar_api_key)):
    """
    Recebe os eventos do webhook da Evolution API.
    Responde imediatamente com 200 OK (evita retries) e processa a mensagem em background.
    """
    evento = payload.get("event")

    # Ignora eventos que não sejam mensagens recebidas (ex: send.message, connection.update...)
    if evento not in EVENTOS_PERMITIDOS:
        return {"status": "ignored", "event": evento}

    # Agenda o processamento em background e retorna imediatamente para a Evolution
    db = SessionLocal()
    background_tasks.add_task(processar_mensagem, payload, db)

    return {"status": "received"}
