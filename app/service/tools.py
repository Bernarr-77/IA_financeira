from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.db.models import Usuario, Conversas, Transacao, Parcela, Assinatura, Role
from app.db.session import SessionLocal
from datetime import datetime, timezone, timedelta
from typing import Optional

def criar_usuario(numero: str, nome: str, db: Session, instancia: str = None) -> Usuario:
    novo_usuario = Usuario(nome=nome, whatsapp=numero, instancia=instancia)
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario

def buscar_usuario(numero: str, db: Session) -> Usuario:
    query = select(Usuario).where(Usuario.whatsapp == numero)
    return db.scalars(query).first()

def salvar_conversa_usuario(texto: str, db: Session, numero: str,  role: Role = Role.USER):
    usuario = buscar_usuario(numero= numero, db=db)
    if usuario:
        nova_conversa = Conversas(usuario_id= usuario.id,
                                    conteudo=texto,
                                    role= role)
        db.add(nova_conversa)
        db.commit()
        db.refresh(nova_conversa)

def buscar_historico(numero: str, limit: int = 10):
    with SessionLocal() as db:
        query = (
            select(Conversas)
            .join(Usuario)
            .where(Usuario.whatsapp == numero)
            .order_by(Conversas.id.desc()) 
            .limit(limit)
        )
        
        mensagens = db.scalars(query).all()
        mensagens.reverse()
        
        historico_formatado = []
        for msg in mensagens:
            role_gemini = "user" if msg.role == Role.USER else "model"
            historico_formatado.append({
                "role": role_gemini,
                "parts": [{"text": msg.conteudo}]
            })
        
        return historico_formatado


# ─────────────────────────────────────────────
# FASE 1: Gestão de Transações
# ─────────────────────────────────────────────

def registrar_gasto(numero: str, descricao: str, valor_total: float, categoria: str,
                    numero_parcelas: int = 1, data_compra: Optional[str] = None) -> dict:
    """Salva um gasto no banco e cria as parcelas automaticamente."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        # Define a data da compra
        dt_compra = datetime.now(timezone.utc)
        if data_compra:
            try:
                dt_compra = datetime.strptime(data_compra, "%d/%m/%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        nova_transacao = Transacao(
            usuario_id=usuario.id,
            descricao=descricao,
            categoria=categoria,
            valor_total=valor_total,
            numero_parcelas=numero_parcelas,
            data_compra=dt_compra,
        )
        db.add(nova_transacao)
        db.flush()  # Gera o ID sem fechar a transação

        # Cria as parcelas automaticamente
        valor_parcela = round(valor_total / numero_parcelas, 2)
        for i in range(numero_parcelas):
            vencimento = dt_compra + timedelta(days=30 * (i + 1))
            parcela = Parcela(
                transacao_id=nova_transacao.id,
                numero_parcela=i + 1,
                valor=valor_parcela,
                data_vencimento=vencimento,
                pago=False,
            )
            db.add(parcela)

        db.commit()
        return {
            "sucesso": True,
            "mensagem": f"Gasto '{descricao}' de R${valor_total:.2f} em {numero_parcelas}x registrado.",
            "transacao_id": nova_transacao.id,
        }


def registrar_receita(numero: str, descricao: str, valor: float,
                      data_recebimento: Optional[str] = None) -> dict:
    """Salva uma entrada de dinheiro (salário, freelance, etc)."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        dt_recebimento = datetime.now(timezone.utc)
        if data_recebimento:
            try:
                dt_recebimento = datetime.strptime(data_recebimento, "%d/%m/%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        # Receitas são transações com valor negativo internamente OU com categoria "Receita"
        nova_transacao = Transacao(
            usuario_id=usuario.id,
            descricao=descricao,
            categoria="Receita",
            valor_total=-abs(valor),  # Negativo para representar entrada
            numero_parcelas=1,
            data_compra=dt_recebimento,
        )
        db.add(nova_transacao)
        db.commit()
        return {
            "sucesso": True,
            "mensagem": f"Receita '{descricao}' de R${valor:.2f} registrada.",
        }


def deletar_transacao(numero: str, transacao_id: int) -> dict:
    """Remove uma transação e suas parcelas do banco de dados."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        transacao = db.scalars(
            select(Transacao).where(
                Transacao.id == transacao_id,
                Transacao.usuario_id == usuario.id
            )
        ).first()

        if not transacao:
            return {"erro": f"Transação #{transacao_id} não encontrada ou não pertence a você."}

        # Remove as parcelas primeiro (integridade referencial)
        parcelas = db.scalars(select(Parcela).where(Parcela.transacao_id == transacao_id)).all()
        for p in parcelas:
            db.delete(p)

        db.delete(transacao)
        db.commit()
        return {"sucesso": True, "mensagem": f"Transação #{transacao_id} '{transacao.descricao}' removida."}


# ─────────────────────────────────────────────
# FASE 2: Consultas e Relatórios
# ─────────────────────────────────────────────

def consultar_resumo_mes(numero: str, mes: Optional[int] = None, ano: Optional[int] = None) -> dict:
    """Retorna o total gasto e recebido no mês informado (padrão: mês atual)."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        agora = datetime.now(timezone.utc)
        mes = mes or agora.month
        ano = ano or agora.year

        transacoes = db.scalars(
            select(Transacao).where(
                Transacao.usuario_id == usuario.id,
                func.extract("month", Transacao.data_compra) == mes,
                func.extract("year", Transacao.data_compra) == ano,
            )
        ).all()

        total_gastos = sum(t.valor_total for t in transacoes if t.valor_total > 0)
        total_receitas = sum(abs(t.valor_total) for t in transacoes if t.valor_total < 0)
        saldo = total_receitas - total_gastos

        return {
            "mes": f"{mes:02d}/{ano}",
            "total_gastos": round(total_gastos, 2),
            "total_receitas": round(total_receitas, 2),
            "saldo_do_mes": round(saldo, 2),
            "numero_transacoes": len(transacoes),
        }


def consultar_saldo_livre(numero: str) -> dict:
    """Retorna quanto ainda pode gastar com base no limite mensal configurado."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        if not usuario.limite_mensal or usuario.limite_mensal == 0:
            return {"aviso": "Você ainda não definiu um limite mensal. Use 'atualizar limite' para configurar."}

        resumo = consultar_resumo_mes(numero=numero)
        gasto = resumo.get("total_gastos", 0)
        livre = usuario.limite_mensal - gasto
        percentual = round((gasto / usuario.limite_mensal) * 100, 1)

        return {
            "limite_mensal": usuario.limite_mensal,
            "gasto_no_mes": round(gasto, 2),
            "saldo_livre": round(livre, 2),
            "percentual_usado": f"{percentual}%",
        }


def consultar_por_categoria(numero: str, categoria: str,
                             mes: Optional[int] = None, ano: Optional[int] = None) -> dict:
    """Retorna o total gasto em uma categoria específica no mês."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        agora = datetime.now(timezone.utc)
        mes = mes or agora.month
        ano = ano or agora.year

        transacoes = db.scalars(
            select(Transacao).where(
                Transacao.usuario_id == usuario.id,
                Transacao.categoria.ilike(f"%{categoria}%"),
                func.extract("month", Transacao.data_compra) == mes,
                func.extract("year", Transacao.data_compra) == ano,
            )
        ).all()

        total = sum(t.valor_total for t in transacoes if t.valor_total > 0)
        itens = [{"descricao": t.descricao, "valor": t.valor_total} for t in transacoes]

        return {
            "categoria": categoria,
            "mes": f"{mes:02d}/{ano}",
            "total": round(total, 2),
            "transacoes": itens,
        }


def consultar_historico_transacoes(numero: str, limit: int = 10) -> dict:
    """Retorna as últimas N transações do usuário."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        transacoes = db.scalars(
            select(Transacao)
            .where(Transacao.usuario_id == usuario.id)
            .order_by(Transacao.data_compra.desc())
            .limit(limit)
        ).all()

        itens = [
            {
                "id": t.id,
                "descricao": t.descricao,
                "categoria": t.categoria,
                "valor": t.valor_total,
                "parcelas": t.numero_parcelas,
                "data": t.data_compra.strftime("%d/%m/%Y"),
            }
            for t in transacoes
        ]

        return {"historico": itens, "total_registros": len(itens)}


# ─────────────────────────────────────────────
# FASE 3: Gestão de Parcelas
# ─────────────────────────────────────────────

def listar_parcelas_vencendo(numero: str, dias: int = 30) -> dict:
    """Lista parcelas que vencem nos próximos N dias (padrão: 30)."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        agora = datetime.now(timezone.utc)
        limite = agora + timedelta(days=dias)

        parcelas = db.scalars(
            select(Parcela)
            .join(Transacao)
            .where(
                Transacao.usuario_id == usuario.id,
                Parcela.pago == False,
                Parcela.data_vencimento >= agora,
                Parcela.data_vencimento <= limite,
            )
            .order_by(Parcela.data_vencimento.asc())
        ).all()

        itens = [
            {
                "parcela_id": p.id,
                "descricao": p.transacao.descricao,
                "parcela": f"{p.numero_parcela}/{p.transacao.numero_parcelas}",
                "valor": p.valor,
                "vencimento": p.data_vencimento.strftime("%d/%m/%Y"),
            }
            for p in parcelas
        ]

        total = sum(p.valor for p in parcelas)
        return {"parcelas_vencendo": itens, "total_a_pagar": round(total, 2)}


def marcar_parcela_paga(numero: str, parcela_id: int) -> dict:
    """Marca uma parcela específica como paga."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        parcela = db.scalars(
            select(Parcela)
            .join(Transacao)
            .where(Parcela.id == parcela_id, Transacao.usuario_id == usuario.id)
        ).first()

        if not parcela:
            return {"erro": f"Parcela #{parcela_id} não encontrada ou não pertence a você."}

        parcela.pago = True
        db.commit()
        return {
            "sucesso": True,
            "mensagem": f"Parcela {parcela.numero_parcela}/{parcela.transacao.numero_parcelas} "
                        f"de '{parcela.transacao.descricao}' marcada como paga.",
        }


# ─────────────────────────────────────────────
# FASE 4: Perfil do Usuário
# ─────────────────────────────────────────────

def atualizar_limite_mensal(numero: str, limite: float) -> dict:
    """Define ou atualiza o orçamento mensal do usuário."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        usuario.limite_mensal = limite
        db.commit()
        return {"sucesso": True, "mensagem": f"Limite mensal atualizado para R${limite:.2f}."}


def atualizar_dia_vencimento(numero: str, dia: int) -> dict:
    """Define o dia de vencimento do cartão de crédito do usuário."""
    with SessionLocal() as db:
        if not 1 <= dia <= 31:
            return {"erro": "Dia inválido. Informe um valor entre 1 e 31."}

        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        usuario.dia_vencimento_cartao = dia
        db.commit()
        return {"sucesso": True, "mensagem": f"Dia de vencimento do cartão atualizado para dia {dia}."}


def consultar_perfil(numero: str) -> dict:
    """Retorna os dados de configuração do perfil do usuário."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        return {
            "nome": usuario.nome,
            "whatsapp": usuario.whatsapp,
            "limite_mensal": usuario.limite_mensal,
            "dia_vencimento_cartao": usuario.dia_vencimento_cartao,
        }


# ─────────────────────────────────────────────
# FASE 5: Inteligência Financeira
# ─────────────────────────────────────────────

def prever_gastos_mes(numero: str) -> dict:
    """Prevê o total de gastos do mês atual baseado no ritmo dos últimos 3 meses."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        agora = datetime.now(timezone.utc)
        totais = []

        # Busca os 3 meses anteriores para calcular a média
        for delta in range(1, 4):
            mes_ref = agora.month - delta
            ano_ref = agora.year
            if mes_ref <= 0:
                mes_ref += 12
                ano_ref -= 1

            transacoes = db.scalars(
                select(Transacao).where(
                    Transacao.usuario_id == usuario.id,
                    Transacao.valor_total > 0,
                    func.extract("month", Transacao.data_compra) == mes_ref,
                    func.extract("year", Transacao.data_compra) == ano_ref,
                )
            ).all()
            totais.append(sum(t.valor_total for t in transacoes))

        if not any(totais):
            return {"aviso": "Histórico insuficiente para previsão. Registre pelo menos 1 mês de gastos."}

        media_mensal = sum(totais) / len([t for t in totais if t > 0])

        # Calcula quanto já foi gasto no mês atual
        gasto_atual = sum(
            t.valor_total for t in db.scalars(
                select(Transacao).where(
                    Transacao.usuario_id == usuario.id,
                    Transacao.valor_total > 0,
                    func.extract("month", Transacao.data_compra) == agora.month,
                    func.extract("year", Transacao.data_compra) == agora.year,
                )
            ).all()
        )

        dias_passados = agora.day
        dias_no_mes = 30
        ritmo_diario = gasto_atual / dias_passados if dias_passados > 0 else 0
        previsao = round(ritmo_diario * dias_no_mes, 2)

        return {
            "media_ultimos_3_meses": round(media_mensal, 2),
            "gasto_atual_no_mes": round(gasto_atual, 2),
            "previsao_para_o_mes": previsao,
            "ritmo_diario": round(ritmo_diario, 2),
        }


def alertar_categoria_excessiva(numero: str, limite_percentual: float = 40.0) -> dict:
    """Verifica se alguma categoria ultrapassou X% do limite mensal total."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        if not usuario.limite_mensal or usuario.limite_mensal == 0:
            return {"aviso": "Defina um limite mensal para receber alertas por categoria."}

        agora = datetime.now(timezone.utc)
        transacoes = db.scalars(
            select(Transacao).where(
                Transacao.usuario_id == usuario.id,
                Transacao.valor_total > 0,
                func.extract("month", Transacao.data_compra) == agora.month,
                func.extract("year", Transacao.data_compra) == agora.year,
            )
        ).all()

        # Agrupa por categoria
        por_categoria: dict[str, float] = {}
        for t in transacoes:
            por_categoria[t.categoria] = por_categoria.get(t.categoria, 0) + t.valor_total

        alertas = []
        for cat, total in por_categoria.items():
            percentual = (total / usuario.limite_mensal) * 100
            if percentual >= limite_percentual:
                alertas.append({
                    "categoria": cat,
                    "gasto": round(total, 2),
                    "percentual_do_limite": f"{round(percentual, 1)}%",
                })

        if not alertas:
            return {"mensagem": "Nenhuma categoria ultrapassou o limite configurado. Continue assim! ✅"}

        return {"alertas": alertas, "limite_mensal": usuario.limite_mensal}


def sugerir_economia(numero: str) -> dict:
    """Analisa os gastos e sugere as categorias onde o usuário pode economizar."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        agora = datetime.now(timezone.utc)

        # Compara mês atual com mês anterior
        transacoes_atual = db.scalars(
            select(Transacao).where(
                Transacao.usuario_id == usuario.id,
                Transacao.valor_total > 0,
                func.extract("month", Transacao.data_compra) == agora.month,
                func.extract("year", Transacao.data_compra) == agora.year,
            )
        ).all()

        mes_ant = agora.month - 1 if agora.month > 1 else 12
        ano_ant = agora.year if agora.month > 1 else agora.year - 1
        transacoes_ant = db.scalars(
            select(Transacao).where(
                Transacao.usuario_id == usuario.id,
                Transacao.valor_total > 0,
                func.extract("month", Transacao.data_compra) == mes_ant,
                func.extract("year", Transacao.data_compra) == ano_ant,
            )
        ).all()

        def agrupar(transacoes):
            resultado = {}
            for t in transacoes:
                resultado[t.categoria] = resultado.get(t.categoria, 0) + t.valor_total
            return resultado

        atual = agrupar(transacoes_atual)
        anterior = agrupar(transacoes_ant)

        sugestoes = []
        for cat, valor_atual in atual.items():
            valor_ant = anterior.get(cat, 0)
            if valor_ant > 0 and valor_atual > valor_ant:
                aumento = valor_atual - valor_ant
                sugestoes.append({
                    "categoria": cat,
                    "mes_passado": round(valor_ant, 2),
                    "mes_atual": round(valor_atual, 2),
                    "aumento": round(aumento, 2),
                    "dica": f"Você gastou R${aumento:.2f} a mais em {cat} esse mês.",
                })

        # Ordena pelo maior aumento
        sugestoes.sort(key=lambda x: x["aumento"], reverse=True)

        if not sugestoes:
            return {"mensagem": "Seus gastos estão estáveis ou menores que o mês passado. Ótimo trabalho! 🎉"}

        return {"sugestoes_de_economia": sugestoes[:3]}  # Top 3 categorias


# ─────────────────────────────────────────────
# FASE 6: Ferramentas Extras
# ─────────────────────────────────────────────

def editar_transacao(numero: str, transacao_id: int,
                     descricao: Optional[str] = None,
                     valor_total: Optional[float] = None,
                     categoria: Optional[str] = None) -> dict:
    """Edita uma transação existente. Atualiza apenas os campos informados."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        transacao = db.scalars(
            select(Transacao).where(
                Transacao.id == transacao_id,
                Transacao.usuario_id == usuario.id
            )
        ).first()

        if not transacao:
            return {"erro": f"Transação #{transacao_id} não encontrada."}

        alteracoes = []
        if descricao:
            transacao.descricao = descricao
            alteracoes.append(f"descrição → {descricao}")
        if valor_total is not None:
            transacao.valor_total = valor_total
            alteracoes.append(f"valor → R${valor_total:.2f}")
        if categoria:
            transacao.categoria = categoria
            alteracoes.append(f"categoria → {categoria}")

        db.commit()
        return {
            "sucesso": True,
            "mensagem": f"Transação #{transacao_id} atualizada: {', '.join(alteracoes)}.",
        }


def buscar_transacao(numero: str, termo: str) -> dict:
    """Busca transações pela descrição usando texto parcial."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        transacoes = db.scalars(
            select(Transacao).where(
                Transacao.usuario_id == usuario.id,
                Transacao.descricao.ilike(f"%{termo}%"),
            )
            .order_by(Transacao.data_compra.desc())
            .limit(10)
        ).all()

        if not transacoes:
            return {"mensagem": f"Nenhuma transação encontrada com '{termo}'."}

        itens = [
            {
                "id": t.id,
                "descricao": t.descricao,
                "valor": t.valor_total,
                "categoria": t.categoria,
                "data": t.data_compra.strftime("%d/%m/%Y"),
            }
            for t in transacoes
        ]
        return {"resultados": itens, "total": len(itens)}


def comparar_meses(numero: str, mes1: int, ano1: int, mes2: int, ano2: int) -> dict:
    """Compara gastos totais entre dois meses diferentes."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        def total_mes(mes, ano):
            transacoes = db.scalars(
                select(Transacao).where(
                    Transacao.usuario_id == usuario.id,
                    Transacao.valor_total > 0,
                    func.extract("month", Transacao.data_compra) == mes,
                    func.extract("year", Transacao.data_compra) == ano,
                )
            ).all()
            return round(sum(t.valor_total for t in transacoes), 2)

        t1 = total_mes(mes1, ano1)
        t2 = total_mes(mes2, ano2)
        diferenca = round(t2 - t1, 2)

        return {
            f"{mes1:02d}/{ano1}": t1,
            f"{mes2:02d}/{ano2}": t2,
            "diferenca": diferenca,
            "analise": f"{'Gastou mais' if diferenca > 0 else 'Gastou menos'} em {mes2:02d}/{ano2} (R${abs(diferenca):.2f}).",
        }


def ranking_categorias(numero: str, mes: Optional[int] = None, ano: Optional[int] = None) -> dict:
    """Retorna as categorias ordenadas pelo maior gasto no mês."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        agora = datetime.now(timezone.utc)
        mes = mes or agora.month
        ano = ano or agora.year

        transacoes = db.scalars(
            select(Transacao).where(
                Transacao.usuario_id == usuario.id,
                Transacao.valor_total > 0,
                func.extract("month", Transacao.data_compra) == mes,
                func.extract("year", Transacao.data_compra) == ano,
            )
        ).all()

        por_categoria: dict[str, float] = {}
        for t in transacoes:
            por_categoria[t.categoria] = por_categoria.get(t.categoria, 0) + t.valor_total

        ranking = sorted(por_categoria.items(), key=lambda x: x[1], reverse=True)
        itens = [{"posicao": i + 1, "categoria": cat, "total": round(val, 2)} for i, (cat, val) in enumerate(ranking)]

        return {"mes": f"{mes:02d}/{ano}", "ranking": itens}


def calcular_comprometimento(numero: str) -> dict:
    """Calcula o percentual da renda comprometido em parcelas futuras não pagas."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        if not usuario.limite_mensal or usuario.limite_mensal == 0:
            return {"aviso": "Defina um limite mensal para calcular o comprometimento."}

        agora = datetime.now(timezone.utc)
        parcelas_futuras = db.scalars(
            select(Parcela)
            .join(Transacao)
            .where(
                Transacao.usuario_id == usuario.id,
                Parcela.pago == False,
                Parcela.data_vencimento >= agora,
            )
        ).all()

        total_comprometido = sum(p.valor for p in parcelas_futuras)
        meses_comprometidos = len(set(p.data_vencimento.strftime("%Y-%m") for p in parcelas_futuras))
        media_mensal = total_comprometido / meses_comprometidos if meses_comprometidos > 0 else 0
        percentual = round((media_mensal / usuario.limite_mensal) * 100, 1) if usuario.limite_mensal else 0

        return {
            "total_comprometido": round(total_comprometido, 2),
            "parcelas_restantes": len(parcelas_futuras),
            "media_mensal_parcelas": round(media_mensal, 2),
            "percentual_da_renda": f"{percentual}%",
            "limite_mensal": usuario.limite_mensal,
        }


def exportar_resumo_texto(numero: str, mes: Optional[int] = None, ano: Optional[int] = None) -> dict:
    """Gera um resumo completo e formatado do mês para o usuário copiar/compartilhar."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        agora = datetime.now(timezone.utc)
        mes = mes or agora.month
        ano = ano or agora.year

        transacoes = db.scalars(
            select(Transacao).where(
                Transacao.usuario_id == usuario.id,
                func.extract("month", Transacao.data_compra) == mes,
                func.extract("year", Transacao.data_compra) == ano,
            )
            .order_by(Transacao.data_compra.asc())
        ).all()

        gastos = [t for t in transacoes if t.valor_total > 0]
        receitas = [t for t in transacoes if t.valor_total < 0]
        total_gastos = sum(t.valor_total for t in gastos)
        total_receitas = sum(abs(t.valor_total) for t in receitas)

        # Agrupa gastos por categoria
        por_categoria: dict[str, float] = {}
        for t in gastos:
            por_categoria[t.categoria] = por_categoria.get(t.categoria, 0) + t.valor_total

        # Parcelas do mês
        parcelas_mes = db.scalars(
            select(Parcela)
            .join(Transacao)
            .where(
                Transacao.usuario_id == usuario.id,
                func.extract("month", Parcela.data_vencimento) == mes,
                func.extract("year", Parcela.data_vencimento) == ano,
            )
        ).all()
        total_parcelas = sum(p.valor for p in parcelas_mes if not p.pago)

        return {
            "periodo": f"{mes:02d}/{ano}",
            "total_gastos": round(total_gastos, 2),
            "total_receitas": round(total_receitas, 2),
            "saldo": round(total_receitas - total_gastos, 2),
            "gastos_por_categoria": {k: round(v, 2) for k, v in sorted(por_categoria.items(), key=lambda x: x[1], reverse=True)},
            "numero_transacoes": len(transacoes),
            "parcelas_pendentes_no_mes": round(total_parcelas, 2),
            "limite_mensal": usuario.limite_mensal,
        }


def lembrete_parcela(numero: str, dias: int = 1) -> dict:
    """Lista parcelas que vencem hoje ou amanhã. Usada pelos alertas automáticos."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        agora = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        limite = agora + timedelta(days=dias + 1)

        parcelas = db.scalars(
            select(Parcela)
            .join(Transacao)
            .where(
                Transacao.usuario_id == usuario.id,
                Parcela.pago == False,
                Parcela.data_vencimento >= agora,
                Parcela.data_vencimento < limite,
            )
            .order_by(Parcela.data_vencimento.asc())
        ).all()

        if not parcelas:
            return {"mensagem": "Nenhuma parcela vencendo nos próximos dias. Tudo tranquilo! ✅"}

        itens = [
            {
                "descricao": p.transacao.descricao,
                "parcela": f"{p.numero_parcela}/{p.transacao.numero_parcelas}",
                "valor": p.valor,
                "vencimento": p.data_vencimento.strftime("%d/%m/%Y"),
            }
            for p in parcelas
        ]
        total = sum(p.valor for p in parcelas)
        return {"parcelas_vencendo": itens, "total": round(total, 2)}


# ─────────────────────────────────────────────
# Fase 7 — Gestão de Assinaturas
# ─────────────────────────────────────────────

def registrar_assinatura(numero: str, nome: str, valor: float, dia_vencimento: int, categoria: str = "Assinatura") -> dict:
    """Registra uma nova assinatura recorrente (Netflix, Spotify, academia, etc.)."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        nova = Assinatura(
            usuario_id=usuario.id,
            nome=nome,
            valor=valor,
            dia_vencimento=dia_vencimento,
            categoria=categoria,
            ativa=True,
        )
        db.add(nova)
        db.commit()
        db.refresh(nova)

        return {
            "sucesso": True,
            "mensagem": f"Assinatura '{nome}' registrada com sucesso!",
            "id": nova.id,
            "nome": nova.nome,
            "valor": nova.valor,
            "dia_vencimento": nova.dia_vencimento,
            "categoria": nova.categoria,
        }


def listar_assinaturas(numero: str) -> dict:
    """Lista todas as assinaturas ativas do usuário."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        assinaturas = db.scalars(
            select(Assinatura)
            .where(Assinatura.usuario_id == usuario.id, Assinatura.ativa == True)
            .order_by(Assinatura.dia_vencimento.asc())
        ).all()

        if not assinaturas:
            return {"mensagem": "Você não tem nenhuma assinatura ativa cadastrada."}

        itens = [
            {
                "id": a.id,
                "nome": a.nome,
                "valor": a.valor,
                "dia_vencimento": a.dia_vencimento,
                "categoria": a.categoria,
            }
            for a in assinaturas
        ]
        total_mensal = sum(a.valor for a in assinaturas)
        total_anual = total_mensal * 12
        return {
            "assinaturas": itens,
            "total_mensal": round(total_mensal, 2),
            "total_anual": round(total_anual, 2),
            "quantidade": len(itens),
        }


def cancelar_assinatura(numero: str, assinatura_id: int) -> dict:
    """Cancela (desativa) uma assinatura pelo ID."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        assinatura = db.scalars(
            select(Assinatura).where(
                Assinatura.id == assinatura_id,
                Assinatura.usuario_id == usuario.id,
            )
        ).first()

        if not assinatura:
            return {"erro": f"Assinatura #{assinatura_id} não encontrada."}

        if not assinatura.ativa:
            return {"mensagem": f"A assinatura '{assinatura.nome}' já estava cancelada."}

        assinatura.ativa = False
        db.commit()

        economia_anual = assinatura.valor * 12
        return {
            "sucesso": True,
            "mensagem": f"Assinatura '{assinatura.nome}' cancelada com sucesso!",
            "economia_mensal": round(assinatura.valor, 2),
            "economia_anual": round(economia_anual, 2),
        }


def resumo_assinaturas(numero: str) -> dict:
    """Retorna um resumo financeiro das assinaturas: total mensal, anual e impacto no limite."""
    with SessionLocal() as db:
        usuario = buscar_usuario(numero=numero, db=db)
        if not usuario:
            return {"erro": "Usuário não encontrado."}

        assinaturas = db.scalars(
            select(Assinatura)
            .where(Assinatura.usuario_id == usuario.id, Assinatura.ativa == True)
            .order_by(Assinatura.valor.desc())
        ).all()

        if not assinaturas:
            return {"mensagem": "Você não tem nenhuma assinatura ativa."}

        total_mensal = sum(a.valor for a in assinaturas)
        total_anual = total_mensal * 12

        resultado = {
            "assinaturas": [{"nome": a.nome, "valor": a.valor, "dia": a.dia_vencimento} for a in assinaturas],
            "total_mensal": round(total_mensal, 2),
            "total_anual": round(total_anual, 2),
            "quantidade": len(assinaturas),
        }

        if usuario.limite_mensal:
            percentual = (total_mensal / usuario.limite_mensal) * 100
            resultado["percentual_do_limite"] = round(percentual, 1)
            resultado["mensagem_limite"] = (
                f"Suas assinaturas consomem {percentual:.1f}% do seu limite mensal de R${usuario.limite_mensal:.2f}."
            )

        return resultado
