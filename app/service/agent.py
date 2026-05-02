import os
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional

load_dotenv()
genai.configure(api_key=os.getenv("APIKEY_GEMINI"))
model = genai.GenerativeModel("gemini-3-flash-preview")

async def chamar_gemini(base64: Optional[str] = None,
                mimetype: Optional[str] = None,
                text: Optional[str] = None):  
        conteudo = []
        if base64 and mimetype:
            conteudo.append({
            "mime_type": mimetype,
            "data": base64
        })
        if text:
            resposta = await model.generate_content_async(conteudo)
        texto_IA = resposta.text