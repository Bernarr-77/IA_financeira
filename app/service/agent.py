import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from typing import Optional
import base64 as base64_lib

load_dotenv()

# Instanciando o cliente da nova versão
client = genai.Client(api_key=os.getenv("APIKEY_GEMINI"))

async def chamar_gemini(base64: Optional[str] = None,
                        mimetype: Optional[str] = None,
                        text: Optional[str] = None):
    
    conteudo = []

    if base64 and mimetype:
        conteudo.append(types.Part.from_bytes(
            data=base64_lib.b64decode(base64),
            mime_type=mimetype))
    if text:
        conteudo.append(text)

    try:
        resposta = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=conteudo)
        return resposta.text
    except Exception as e:
        print(f"❌ Erro na chamada do Gemini: {e}")
        return f"Erro ao processar com IA: {e}"