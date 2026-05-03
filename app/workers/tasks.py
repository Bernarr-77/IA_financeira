"""
Tasks agendadas da Bia — enviadas automaticamente via WhatsApp.

Cada task:
1. Busca todos os usuários cadastrados no banco
2. Gera o resumo financeiro do período
3. Envia a mensagem via Evolution API
"""
import os
import httpx
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models import Usuario, Transacao, Parcela, Assinatura


# ─────────────────────────────────────────────
# Envio de mensagem (síncrono — Celery usa threads)
# ─────────────────────────────────────────────

def enviar_whatsapp(numero: str, texto: str, instancia: str):
    """Envia mensagem via Evolution API (versão síncrona para uso no Celery)."""
    url_servidor = os.getenv("SERVER_URL", "http://localhost:8080")
    nome_instancia = instancia or os.getenv("EVOLUTION_INSTANCE", "BiaFinanceira")
    api_key = os.getenv("AUTHENTICATION_API_KEY")

    url = f"{url_servidor}/message/sendText/{nome_instancia}"
    headers = {"Content-Type": "application/json", "apikey": api_key}
    body = {
        "number": numero,
        "text": texto,
        "delay": 1200,
        "linkPreview": False,
        "checkContact": False,
    }
    try:
        resposta = httpx.post(url, headers=headers, json=body, timeout=15)
        print(f"✅ Mensagem enviada para {numero} via {nome_instancia}: {resposta.status_code}")
    except Exception as e:
        print(f"❌ Erro ao enviar para {numero}: {e}")


def buscar_todos_usuarios():
    """Retorna todos os usuários cadastrados no banco."""
    with SessionLocal() as db:
        return db.scalars(select(Usuario)).all()


# ─────────────────────────────────────────────
# 🔔 ALERTA DIÁRIO — 7h
# ─────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.alerta_parcela")
def alerta_parcela():
    """Avisa sobre parcelas que vencem hoje."""
    usuarios = buscar_todos_usuarios()
    hoje = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    amanha = hoje + timedelta(days=1)

    for usuario in usuarios:
        with SessionLocal() as db:
            parcelas = db.scalars(
                select(Parcela)
                .join(Transacao)
                .where(
                    Transacao.usuario_id == usuario.id,
                    Parcela.pago == False,
                    Parcela.data_vencimento >= hoje,
                    Parcela.data_vencimento < amanha,
                )
                .order_by(Parcela.data_vencimento.asc())
            ).all()

            if not parcelas:
                continue

            linhas = [f"🔔 *Bom dia, {usuario.nome}!* Parcelas que vencem hoje:\n"]
            total = 0
            for p in parcelas:
                linhas.append(f"• {p.transacao.descricao} — {p.numero_parcela}/{p.transacao.numero_parcelas} — R${p.valor:.2f}")
                total += p.valor
            linhas.append(f"\n💰 Total: R${total:.2f}")

            enviar_whatsapp(usuario.whatsapp, "\n".join(linhas), usuario.instancia)


# ─────────────────────────────────────────────
# 📊 RESUMO DIÁRIO — 21h
# ─────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.resumo_diario")
def resumo_diario():
    """Envia o resumo dos gastos do dia + parcelas que vencem amanhã."""
    usuarios = buscar_todos_usuarios()
    hoje = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    amanha = hoje + timedelta(days=1)
    depois = amanha + timedelta(days=1)

    for usuario in usuarios:
        with SessionLocal() as db:
            # Gastos do dia
            gastos_dia = db.scalars(
                select(Transacao).where(
                    Transacao.usuario_id == usuario.id,
                    Transacao.valor_total > 0,
                    Transacao.data_compra >= hoje,
                    Transacao.data_compra < amanha,
                )
            ).all()

            total_dia = sum(t.valor_total for t in gastos_dia)

            # Parcelas de amanhã
            parcelas_amanha = db.scalars(
                select(Parcela)
                .join(Transacao)
                .where(
                    Transacao.usuario_id == usuario.id,
                    Parcela.pago == False,
                    Parcela.data_vencimento >= amanha,
                    Parcela.data_vencimento < depois,
                )
            ).all()

            linhas = [f"📊 *Boa noite, {usuario.nome}!* Resumo do dia:\n"]

            if gastos_dia:
                for t in gastos_dia:
                    linhas.append(f"• {t.descricao} ({t.categoria}) — R${t.valor_total:.2f}")
                linhas.append(f"\n💲 Total hoje: R${total_dia:.2f}")
            else:
                linhas.append("Nenhum gasto registrado hoje. Ótimo! 🎉")

            if parcelas_amanha:
                linhas.append(f"\n⚠️ Amanhã vencem {len(parcelas_amanha)} parcela(s):")
                for p in parcelas_amanha:
                    linhas.append(f"• {p.transacao.descricao} — R${p.valor:.2f}")

            enviar_whatsapp(usuario.whatsapp, "\n".join(linhas), usuario.instancia)


# ─────────────────────────────────────────────
# 📈 RESUMO SEMANAL — Segunda-feira 8h
# ─────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.resumo_semanal")
def resumo_semanal():
    """Envia o total gasto por categoria na semana anterior."""
    usuarios = buscar_todos_usuarios()
    hoje = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoje - timedelta(days=7)

    for usuario in usuarios:
        with SessionLocal() as db:
            transacoes = db.scalars(
                select(Transacao).where(
                    Transacao.usuario_id == usuario.id,
                    Transacao.valor_total > 0,
                    Transacao.data_compra >= inicio_semana,
                    Transacao.data_compra < hoje,
                )
            ).all()

            if not transacoes:
                enviar_whatsapp(
                    usuario.whatsapp,
                    f"📈 *Bom dia, {usuario.nome}!* Nenhum gasto registrado na semana passada. Continue assim! 🚀",
                    usuario.instancia
                )
                continue

            por_categoria: dict[str, float] = {}
            for t in transacoes:
                por_categoria[t.categoria] = por_categoria.get(t.categoria, 0) + t.valor_total

            ranking = sorted(por_categoria.items(), key=lambda x: x[1], reverse=True)
            total = sum(v for _, v in ranking)

            linhas = [f"📈 *Bom dia, {usuario.nome}!* Resumo da semana passada:\n"]
            for i, (cat, val) in enumerate(ranking):
                pct = (val / total) * 100
                linhas.append(f"{i + 1}. {cat} — R${val:.2f} ({pct:.0f}%)")
            linhas.append(f"\n💲 Total: R${total:.2f}")

            if usuario.limite_mensal:
                # Gastos do mês até agora
                mes_atual = hoje.month
                ano_atual = hoje.year
                gastos_mes = db.scalars(
                    select(Transacao).where(
                        Transacao.usuario_id == usuario.id,
                        Transacao.valor_total > 0,
                        func.extract("month", Transacao.data_compra) == mes_atual,
                        func.extract("year", Transacao.data_compra) == ano_atual,
                    )
                ).all()
                total_mes = sum(t.valor_total for t in gastos_mes)
                restante = usuario.limite_mensal - total_mes
                linhas.append(f"📋 No mês: R${total_mes:.2f} / R${usuario.limite_mensal:.2f} (sobra R${restante:.2f})")

            enviar_whatsapp(usuario.whatsapp, "\n".join(linhas), usuario.instancia)


# ─────────────────────────────────────────────
# 📋 RESUMO MENSAL — Dia 1 às 8h
# ─────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.resumo_mensal")
def resumo_mensal():
    """Envia o resumo completo do mês anterior: gastos vs limite, por categoria, parcelas."""
    usuarios = buscar_todos_usuarios()
    hoje = datetime.now(timezone.utc)
    mes_anterior = hoje.month - 1 if hoje.month > 1 else 12
    ano_anterior = hoje.year if hoje.month > 1 else hoje.year - 1

    for usuario in usuarios:
        with SessionLocal() as db:
            # Gastos do mês anterior
            transacoes = db.scalars(
                select(Transacao).where(
                    Transacao.usuario_id == usuario.id,
                    Transacao.valor_total > 0,
                    func.extract("month", Transacao.data_compra) == mes_anterior,
                    func.extract("year", Transacao.data_compra) == ano_anterior,
                )
            ).all()

            total_gastos = sum(t.valor_total for t in transacoes)

            # Receitas do mês anterior
            receitas = db.scalars(
                select(Transacao).where(
                    Transacao.usuario_id == usuario.id,
                    Transacao.valor_total < 0,
                    func.extract("month", Transacao.data_compra) == mes_anterior,
                    func.extract("year", Transacao.data_compra) == ano_anterior,
                )
            ).all()
            total_receitas = sum(abs(t.valor_total) for t in receitas)

            # Por categoria
            por_categoria: dict[str, float] = {}
            for t in transacoes:
                por_categoria[t.categoria] = por_categoria.get(t.categoria, 0) + t.valor_total

            ranking = sorted(por_categoria.items(), key=lambda x: x[1], reverse=True)

            # Parcelas do mês atual
            parcelas_mes = db.scalars(
                select(Parcela)
                .join(Transacao)
                .where(
                    Transacao.usuario_id == usuario.id,
                    Parcela.pago == False,
                    func.extract("month", Parcela.data_vencimento) == hoje.month,
                    func.extract("year", Parcela.data_vencimento) == hoje.year,
                )
            ).all()
            total_parcelas = sum(p.valor for p in parcelas_mes)

            linhas = [
                f"📋 *Bom dia, {usuario.nome}!* Resumo de {mes_anterior:02d}/{ano_anterior}:\n",
                f"💲 Gastos: R${total_gastos:.2f}",
                f"💰 Receitas: R${total_receitas:.2f}",
                f"📊 Saldo: R${total_receitas - total_gastos:.2f}",
            ]

            if usuario.limite_mensal:
                if total_gastos > usuario.limite_mensal:
                    linhas.append(f"⚠️ Ultrapassou o limite em R${total_gastos - usuario.limite_mensal:.2f}!")
                else:
                    linhas.append(f"✅ Ficou dentro do limite (sobrou R${usuario.limite_mensal - total_gastos:.2f})")

            if ranking:
                linhas.append("\n📊 *Por categoria:*")
                for cat, val in ranking[:5]:
                    linhas.append(f"• {cat}: R${val:.2f}")

            if parcelas_mes:
                linhas.append(f"\n📅 *Parcelas deste mês:* {len(parcelas_mes)} pendentes (R${total_parcelas:.2f})")

            enviar_whatsapp(usuario.whatsapp, "\n".join(linhas), usuario.instancia)


# ─────────────────────────────────────────────
# 🔄 ALERTA DE ASSINATURAS — Dia 15 às 10h
# ─────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.alerta_assinaturas")
def alerta_assinaturas():
    """Envia um lembrete mensal com todas as assinaturas ativas e o custo total."""
    usuarios = buscar_todos_usuarios()

    for usuario in usuarios:
        with SessionLocal() as db:
            assinaturas = db.scalars(
                select(Assinatura)
                .where(Assinatura.usuario_id == usuario.id, Assinatura.ativa == True)
                .order_by(Assinatura.valor.desc())
            ).all()

            if not assinaturas:
                continue

            total_mensal = sum(a.valor for a in assinaturas)
            total_anual = total_mensal * 12

            linhas = [f"🔄 *Oi, {usuario.nome}!* Lembrete das suas assinaturas ativas:\n"]
            for a in assinaturas:
                linhas.append(f"• {a.nome} — R${a.valor:.2f}/mês (vence dia {a.dia_vencimento})")

            linhas.append(f"\n💲 Total mensal: R${total_mensal:.2f}")
            linhas.append(f"📅 Total anual: R${total_anual:.2f}")

            if usuario.limite_mensal:
                pct = (total_mensal / usuario.limite_mensal) * 100
                linhas.append(f"📊 Isso representa {pct:.1f}% do seu limite mensal.")

            linhas.append("\nAlguma assinatura que você não usa mais? Me fale que eu cancelo! 😉")

            enviar_whatsapp(usuario.whatsapp, "\n".join(linhas), usuario.instancia)
