from app.db.session import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Enum, ForeignKey, DateTime, Float, Boolean, Integer
import enum
from datetime import datetime, timezone
from typing import List

class Role(enum.Enum):
    USER = "USER"
    ASSISTENTE = "ASSISTENTE"

class Usuario(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    whatsapp: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    dia_vencimento_cartao: Mapped[int] = mapped_column(nullable=True)
    limite_mensal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    instancia: Mapped[str] = mapped_column(String(100), nullable=True)

    # Um usuário tem muitas conversas e muitas transações
    conversas: Mapped[List["Conversas"]] = relationship(back_populates="usuario")
    transacoes: Mapped[List["Transacao"]] = relationship(back_populates="usuario")
    assinaturas: Mapped[List["Assinatura"]] = relationship(back_populates="usuario")

class Conversas(Base):
    __tablename__ = "conversas_zap"
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    conteudo: Mapped[str] = mapped_column(nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))

    usuario: Mapped["Usuario"] = relationship(back_populates="conversas")

class Transacao(Base):
    __tablename__ = "transacoes"
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    valor_total: Mapped[float] = mapped_column(Float, nullable=False)
    numero_parcelas: Mapped[int] = mapped_column(nullable=False, default=1)
    data_compra: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))

    usuario: Mapped["Usuario"] = relationship(back_populates="transacoes")
    parcelas: Mapped[List["Parcela"]] = relationship(back_populates="transacao")

class Parcela(Base):
    __tablename__ = "parcelas"
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    transacao_id: Mapped[int] = mapped_column(ForeignKey("transacoes.id"))
    numero_parcela: Mapped[int] = mapped_column(nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    data_vencimento: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    pago: Mapped[bool] = mapped_column(Boolean, default=False)

    transacao: Mapped["Transacao"] = relationship(back_populates="parcelas")

class Assinatura(Base):
    __tablename__ = "assinaturas"
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False, default="Assinatura")
    dia_vencimento: Mapped[int] = mapped_column(Integer, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))

    usuario: Mapped["Usuario"] = relationship(back_populates="assinaturas")

