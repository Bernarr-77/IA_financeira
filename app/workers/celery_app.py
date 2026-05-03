import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Configuração do Celery
# ─────────────────────────────────────────────
celery_app = Celery(
    "bia_financeira",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    include=["app.workers.tasks"],
)

celery_app.conf.timezone = "America/Sao_Paulo"

# ─────────────────────────────────────────────
# Agendamento automático (Celery Beat)
# ─────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # 🔔 Todo dia às 7h — Alerta de parcelas que vencem hoje
    "alerta-parcela-diario": {
        "task": "app.workers.tasks.alerta_parcela",
        "schedule": crontab(hour=7, minute=0),
    },
    # 📊 Todo dia às 21h — Resumo diário de gastos
    "resumo-diario": {
        "task": "app.workers.tasks.resumo_diario",
        "schedule": crontab(hour=21, minute=0),
    },
    # 📈 Toda segunda-feira às 8h — Resumo semanal por categoria
    "resumo-semanal": {
        "task": "app.workers.tasks.resumo_semanal",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
    },
    # 📋 Todo dia 1 às 8h — Resumo mensal completo
    "resumo-mensal": {
        "task": "app.workers.tasks.resumo_mensal",
        "schedule": crontab(hour=8, minute=0, day_of_month=1),
    },
    # 🔄 Todo dia 15 às 10h — Alerta de assinaturas ativas
    "alerta-assinaturas": {
        "task": "app.workers.tasks.alerta_assinaturas",
        "schedule": crontab(hour=10, minute=0, day_of_month=15),
    },
}
