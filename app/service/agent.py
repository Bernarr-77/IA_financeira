import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from typing import Optional
import base64 as base64_lib
from app.service.tools import (
    buscar_historico,
    # Fase 1 - Transações
    registrar_gasto,
    registrar_receita,
    deletar_transacao,
    # Fase 2 - Consultas
    consultar_resumo_mes,
    consultar_saldo_livre,
    consultar_por_categoria,
    consultar_historico_transacoes,
    # Fase 3 - Parcelas
    listar_parcelas_vencendo,
    marcar_parcela_paga,
    # Fase 4 - Perfil
    atualizar_limite_mensal,
    atualizar_dia_vencimento,
    consultar_perfil,
    # Fase 5 - Inteligência
    prever_gastos_mes,
    alertar_categoria_excessiva,
    sugerir_economia,
    # Fase 6 - Extras
    editar_transacao,
    buscar_transacao,
    comparar_meses,
    ranking_categorias,
    calcular_comprometimento,
    exportar_resumo_texto,
    lembrete_parcela,
    # Fase 7 - Assinaturas
    registrar_assinatura,
    listar_assinaturas,
    cancelar_assinatura,
    resumo_assinaturas,
)

load_dotenv()

client = genai.Client(api_key=os.getenv("APIKEY_GEMINI"))

# ─────────────────────────────────────────────
# Mapa de funções disponíveis para a Bia
# ─────────────────────────────────────────────
# Quando a IA decide chamar uma função, buscamos ela aqui pelo nome.
FERRAMENTAS_DISPONIVEIS = {
    "registrar_gasto": registrar_gasto,
    "registrar_receita": registrar_receita,
    "deletar_transacao": deletar_transacao,
    "consultar_resumo_mes": consultar_resumo_mes,
    "consultar_saldo_livre": consultar_saldo_livre,
    "consultar_por_categoria": consultar_por_categoria,
    "consultar_historico_transacoes": consultar_historico_transacoes,
    "listar_parcelas_vencendo": listar_parcelas_vencendo,
    "marcar_parcela_paga": marcar_parcela_paga,
    "atualizar_limite_mensal": atualizar_limite_mensal,
    "atualizar_dia_vencimento": atualizar_dia_vencimento,
    "consultar_perfil": consultar_perfil,
    "prever_gastos_mes": prever_gastos_mes,
    "alertar_categoria_excessiva": alertar_categoria_excessiva,
    "sugerir_economia": sugerir_economia,
    "editar_transacao": editar_transacao,
    "buscar_transacao": buscar_transacao,
    "comparar_meses": comparar_meses,
    "ranking_categorias": ranking_categorias,
    "calcular_comprometimento": calcular_comprometimento,
    "exportar_resumo_texto": exportar_resumo_texto,
    "lembrete_parcela": lembrete_parcela,
    "registrar_assinatura": registrar_assinatura,
    "listar_assinaturas": listar_assinaturas,
    "cancelar_assinatura": cancelar_assinatura,
    "resumo_assinaturas": resumo_assinaturas,
}

# ─────────────────────────────────────────────
# Definição das ferramentas para o Gemini
# ─────────────────────────────────────────────
# É assim que "apresentamos" as funções para a IA. Ela lê as descrições
# e decide sozinha qual chamar com base na mensagem do usuário.
DECLARACOES_FERRAMENTAS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="registrar_gasto",
            description="Registra um novo gasto no banco de dados e cria as parcelas automaticamente. Use APENAS após o usuário confirmar com 'sim', 'pode salvar', 'confirma' ou similar.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "descricao": types.Schema(type=types.Type.STRING, description="Nome ou descrição do gasto"),
                    "valor_total": types.Schema(type=types.Type.NUMBER, description="Valor total do gasto em reais"),
                    "categoria": types.Schema(type=types.Type.STRING, description="Categoria: Alimentação, Transporte, Saúde, Lazer, Educação, Moradia, Vestuário, Tecnologia, Assinatura ou Outros"),
                    "numero_parcelas": types.Schema(type=types.Type.INTEGER, description="Número de parcelas (1 = à vista)"),
                    "data_compra": types.Schema(type=types.Type.STRING, description="Data da compra no formato DD/MM/AAAA. Se não informada, usa a data de hoje."),
                },
                required=["numero", "descricao", "valor_total", "categoria"],
            ),
        ),
        types.FunctionDeclaration(
            name="registrar_receita",
            description="Registra uma entrada de dinheiro (salário, freelance, transferência recebida, etc).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "descricao": types.Schema(type=types.Type.STRING, description="Descrição da receita"),
                    "valor": types.Schema(type=types.Type.NUMBER, description="Valor recebido em reais"),
                    "data_recebimento": types.Schema(type=types.Type.STRING, description="Data no formato DD/MM/AAAA"),
                },
                required=["numero", "descricao", "valor"],
            ),
        ),
        types.FunctionDeclaration(
            name="deletar_transacao",
            description="Remove um gasto ou receita pelo ID da transação. Use quando o usuário pedir para apagar, remover ou cancelar um lançamento.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "transacao_id": types.Schema(type=types.Type.INTEGER, description="ID numérico da transação a ser removida"),
                },
                required=["numero", "transacao_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="consultar_resumo_mes",
            description="Retorna total de gastos e receitas do mês. Use quando o usuário perguntar 'quanto gastei?', 'como tô no mês?', 'resumo', 'extrato'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "mes": types.Schema(type=types.Type.INTEGER, description="Mês (1-12). Omitir para o mês atual."),
                    "ano": types.Schema(type=types.Type.INTEGER, description="Ano com 4 dígitos. Omitir para o ano atual."),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="consultar_saldo_livre",
            description="Calcula quanto o usuário ainda pode gastar no mês com base no limite mensal. Use para perguntas como 'quanto posso gastar?', 'tô no limite?', 'sobrou quanto?'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="consultar_por_categoria",
            description="Mostra o total gasto em uma categoria específica no mês. Use para perguntas como 'quanto gastei com alimentação?', 'gastos com transporte'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "categoria": types.Schema(type=types.Type.STRING, description="Nome da categoria a consultar"),
                    "mes": types.Schema(type=types.Type.INTEGER, description="Mês (1-12). Omitir para o mês atual."),
                    "ano": types.Schema(type=types.Type.INTEGER, description="Ano. Omitir para o ano atual."),
                },
                required=["numero", "categoria"],
            ),
        ),
        types.FunctionDeclaration(
            name="consultar_historico_transacoes",
            description="Lista os últimos gastos do usuário. Use para 'ver meus gastos', 'listar transações', 'histórico'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "limit": types.Schema(type=types.Type.INTEGER, description="Quantos registros retornar (padrão 10)"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="listar_parcelas_vencendo",
            description="Lista as parcelas não pagas que vencem nos próximos dias. Use para 'quais parcelas vencem?', 'o que tenho para pagar?', 'parcelas do mês'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "dias": types.Schema(type=types.Type.INTEGER, description="Quantos dias à frente verificar (padrão 30)"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="marcar_parcela_paga",
            description="Marca uma parcela como paga. Use quando o usuário disser 'paguei', 'quitei', 'marquei como pago' e informar o ID da parcela.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "parcela_id": types.Schema(type=types.Type.INTEGER, description="ID numérico da parcela a marcar como paga"),
                },
                required=["numero", "parcela_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="atualizar_limite_mensal",
            description="Define ou atualiza o orçamento mensal do usuário. Use para 'meu limite é X', 'quero gastar no máximo X por mês'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "limite": types.Schema(type=types.Type.NUMBER, description="Valor do limite mensal em reais"),
                },
                required=["numero", "limite"],
            ),
        ),
        types.FunctionDeclaration(
            name="atualizar_dia_vencimento",
            description="Define o dia de vencimento do cartão de crédito do usuário.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "dia": types.Schema(type=types.Type.INTEGER, description="Dia do mês de vencimento do cartão (1-31)"),
                },
                required=["numero", "dia"],
            ),
        ),
        types.FunctionDeclaration(
            name="consultar_perfil",
            description="Retorna as configurações do perfil do usuário (limite mensal, dia do cartão). Use para 'meu perfil', 'minhas configurações'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="prever_gastos_mes",
            description="Prevê o total de gastos do mês com base no ritmo atual e histórico dos últimos meses. Use para 'quanto vou gastar esse mês?', 'previsão de gastos'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="alertar_categoria_excessiva",
            description="Verifica se o usuário está gastando demais em alguma categoria. Use para 'onde tô gastando mais?', 'algum alerta?', 'tô exagerando em algo?'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "limite_percentual": types.Schema(type=types.Type.NUMBER, description="Percentual do limite mensal a partir do qual é considerado excessivo (padrão 40%)"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="sugerir_economia",
            description="Compara os gastos do mês atual com o mês anterior e sugere onde economizar. Use para 'como posso economizar?', 'onde posso cortar gastos?', 'dicas financeiras'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="editar_transacao",
            description="Edita uma transação existente. Atualiza descrição, valor ou categoria. Use quando o usuário pedir para corrigir, alterar ou editar um gasto.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "transacao_id": types.Schema(type=types.Type.INTEGER, description="ID da transação a editar"),
                    "descricao": types.Schema(type=types.Type.STRING, description="Nova descrição (opcional)"),
                    "valor_total": types.Schema(type=types.Type.NUMBER, description="Novo valor total (opcional)"),
                    "categoria": types.Schema(type=types.Type.STRING, description="Nova categoria (opcional)"),
                },
                required=["numero", "transacao_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="buscar_transacao",
            description="Busca transações por texto na descrição. Use para 'onde tá aquele gasto de X?', 'buscar transação', 'procurar gasto'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "termo": types.Schema(type=types.Type.STRING, description="Texto para buscar na descrição das transações"),
                },
                required=["numero", "termo"],
            ),
        ),
        types.FunctionDeclaration(
            name="comparar_meses",
            description="Compara gastos entre dois meses diferentes. Use para 'gastei mais em abril ou março?', 'comparar meses'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "mes1": types.Schema(type=types.Type.INTEGER, description="Primeiro mês (1-12)"),
                    "ano1": types.Schema(type=types.Type.INTEGER, description="Ano do primeiro mês"),
                    "mes2": types.Schema(type=types.Type.INTEGER, description="Segundo mês (1-12)"),
                    "ano2": types.Schema(type=types.Type.INTEGER, description="Ano do segundo mês"),
                },
                required=["numero", "mes1", "ano1", "mes2", "ano2"],
            ),
        ),
        types.FunctionDeclaration(
            name="ranking_categorias",
            description="Mostra as categorias ordenadas pelo maior gasto. Use para 'em que gasto mais?', 'ranking de gastos', 'top categorias'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "mes": types.Schema(type=types.Type.INTEGER, description="Mês (1-12). Omitir para o mês atual."),
                    "ano": types.Schema(type=types.Type.INTEGER, description="Ano. Omitir para o ano atual."),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="calcular_comprometimento",
            description="Calcula quanto da renda está comprometida com parcelas futuras. Use para 'quanto tá comprometido?', 'parcelas futuras', 'comprometimento'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="exportar_resumo_texto",
            description="Gera um resumo completo e detalhado do mês para o usuário compartilhar. Use para 'faz um resumão', 'relatório do mês', 'exportar resumo'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "mes": types.Schema(type=types.Type.INTEGER, description="Mês (1-12). Omitir para o mês atual."),
                    "ano": types.Schema(type=types.Type.INTEGER, description="Ano. Omitir para o ano atual."),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="lembrete_parcela",
            description="Lista parcelas que vencem hoje ou amanhã. Use para 'o que vence hoje?', 'parcelas de amanhã', 'lembrete'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "dias": types.Schema(type=types.Type.INTEGER, description="Quantos dias à frente verificar (padrão 1)"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="registrar_assinatura",
            description="Registra uma nova assinatura/serviço recorrente (Netflix, Spotify, academia, internet, etc.). Use quando o usuário disser 'assino Netflix', 'tenho assinatura de', 'pago todo mês'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "nome": types.Schema(type=types.Type.STRING, description="Nome da assinatura (ex: Netflix, Spotify, Academia)"),
                    "valor": types.Schema(type=types.Type.NUMBER, description="Valor mensal em reais"),
                    "dia_vencimento": types.Schema(type=types.Type.INTEGER, description="Dia do mês em que vence (1-31)"),
                    "categoria": types.Schema(type=types.Type.STRING, description="Categoria: Assinatura, Lazer, Saúde, Educação, etc."),
                },
                required=["numero", "nome", "valor", "dia_vencimento"],
            ),
        ),
        types.FunctionDeclaration(
            name="listar_assinaturas",
            description="Lista todas as assinaturas ativas do usuário com total mensal e anual. Use para 'minhas assinaturas', 'quais serviços pago', 'lista assinaturas'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                },
                required=["numero"],
            ),
        ),
        types.FunctionDeclaration(
            name="cancelar_assinatura",
            description="Cancela uma assinatura pelo ID. Use para 'cancelar Netflix', 'tirar assinatura'. Liste as assinaturas primeiro para pegar o ID se necessário.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                    "assinatura_id": types.Schema(type=types.Type.INTEGER, description="ID da assinatura a ser cancelada"),
                },
                required=["numero", "assinatura_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="resumo_assinaturas",
            description="Mostra o impacto financeiro das assinaturas: total mensal, anual e percentual do limite. Use para 'quanto gasto com assinatura', 'impacto das assinaturas', 'resumo assinaturas'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "numero": types.Schema(type=types.Type.STRING, description="Número WhatsApp do usuário"),
                },
                required=["numero"],
            ),
        ),
    ])
]


# ─────────────────────────────────────────────
# Transcrição de áudio
# ─────────────────────────────────────────────

async def transcrever_audio(base64_audio: str, mimetype: str) -> str:
    """Usa o Gemini para transcrever um áudio e retornar apenas o texto."""
    conteudo = [
        types.Part.from_bytes(
            data=base64_lib.b64decode(base64_audio),
            mime_type=mimetype
        ),
        "Transcreva este áudio exatamente como falado. Não adicione comentários, apenas o texto."
    ]
    try:
        resposta = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=conteudo
        )
        return resposta.text.strip()
    except Exception as e:
        print(f"❌ Erro na transcrição: {e}")
        return ""


# ─────────────────────────────────────────────
# Agente principal com Function Calling
# ─────────────────────────────────────────────

async def chamar_gemini(nome: str,
                        numero: str,
                        data_hoje: str,
                        text: Optional[str] = None,
                        base64: Optional[str] = None,
                        mimetype: Optional[str] = None) -> str:

    instrucao = f"""
Você é a Bia, secretária financeira pessoal. Objetiva, inteligente e eficiente.
Responda SEMPRE em português brasileiro, de forma natural e amigável, sem ser prolixo.
═══ DADOS DO USUÁRIO ═══
- Nome: {nome}
- Número WhatsApp: {numero}
- Data e hora agora: {data_hoje}
═══ REGRAS ABSOLUTAS ═══
1. NUNCA pergunte o nome, número ou dados que já estão acima.
2. NUNCA invente valores, datas ou transações que o usuário não mencionou.
3. NUNCA responda nada fora do tema de finanças pessoais. Se o usuário tentar outro assunto, redirecione com educação.
4. Use os dados de data/hora para entender "hoje", "ontem", "semana passada", "mês que vem", etc.
5. Ao registrar gastos: SEMPRE mostre o resumo e peça confirmação antes de chamar a ferramenta registrar_gasto.
6. Só chame registrar_gasto quando o usuário confirmar com "sim", "pode salvar", "confirma" ou similar.
═══ COMO IDENTIFICAR INTENÇÕES ═══
- REGISTRAR GASTO: "Gastei 50 reais em pizza", "Comprei notebook 3000 em 5x"
  → Identifique descrição, valor, parcelas, categoria. Confirme antes de salvar.
- CONSULTAS: "quanto gastei?", "como tô no mês?", "resumo", "extrato"
  → Use as ferramentas de consulta.
- PARCELAS: "quais vencem esse mês?", "paguei o cartão"
  → Use as ferramentas de parcela.
- INTELIGÊNCIA: "onde posso economizar?", "previsão do mês", "tô gastando demais?"
  → Use as ferramentas de análise.
═══ CATEGORIAS VÁLIDAS ═══
Alimentação | Transporte | Saúde | Lazer | Educação | Moradia | Vestuário | Tecnologia | Assinatura | Outros
═══ FORMATO DAS RESPOSTAS ═══
- Máximo 4 linhas por resposta.
- Use emojis com moderação (💰✅❌📊📅💲).
- Ao confirmar registro, use este modelo:
  posso salvar os dados:
  💲 nome: <descrição>
  ✅ valor: R$ <valor>
  💰 parcela: <Nx (R$ valor_parcela)>
  📊 categoria: <categoria>
  📅 data: <data>
  posso confirmar?
- Não deixe asteriscos soltos. Use negrito sem exibir os asteriscos.
- NUNCA use aspas (ex: "Nome") ao se referir ao nome do usuário ou às descrições dos gastos.
"""

    # Monta o conteúdo com histórico + mensagem atual
    conteudo = []
    historico = buscar_historico(numero=numero)
    if historico:
        conteudo.extend(historico)

    parts_atuais = []
    if base64 and mimetype:
        parts_atuais.append(types.Part.from_bytes(
            data=base64_lib.b64decode(base64),
            mime_type=mimetype))
    if text:
        parts_atuais.append(types.Part.from_text(text=text))

    if parts_atuais:
        conteudo.append({"role": "user", "parts": parts_atuais})

    config = types.GenerateContentConfig(
        system_instruction=instrucao,
        tools=DECLARACOES_FERRAMENTAS,
    )

    try:
        # ── Loop de Function Calling ──────────────────────────────────────────
        # O Gemini pode pedir para chamar uma função. Quando isso acontece,
        # executamos a função, devolvemos o resultado, e ele gera a resposta final.
        while True:
            resposta = await client.aio.models.generate_content(
                model="gemini-3-flash-preview",
                contents=conteudo,
                config=config,
            )

            # Verifica se a IA quer chamar alguma ferramenta
            function_calls = [
                part.function_call
                for candidate in resposta.candidates
                for part in candidate.content.parts
                if part.function_call
            ]

            if not function_calls:
                # Sem chamada de função: retorna o texto final
                return resposta.text

            # Adiciona a resposta da IA (com as function_calls) ao histórico do loop
            conteudo.append(resposta.candidates[0].content)

            # Executa cada função solicitada pela IA
            resultados_funcoes = []
            for fc in function_calls:
                nome_funcao = fc.name
                args = dict(fc.args)

                print(f"🔧 Bia chamando ferramenta: {nome_funcao}({args})")

                funcao = FERRAMENTAS_DISPONIVEIS.get(nome_funcao)
                if funcao:
                    resultado = funcao(**args)
                else:
                    resultado = {"erro": f"Ferramenta '{nome_funcao}' não encontrada."}

                resultados_funcoes.append(
                    types.Part.from_function_response(
                        name=nome_funcao,
                        response=resultado,
                    )
                )

            # Devolve os resultados para a IA gerar a resposta final
            conteudo.append({"role": "user", "parts": resultados_funcoes})

    except Exception as e:
        print(f"❌ Erro na chamada do Gemini: {e}")
        return f"Erro ao processar com IA: {e}"