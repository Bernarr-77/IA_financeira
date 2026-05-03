web: alembic upgrade head && python -m uvicorn main:app --host 0.0.0.0 --port $PORT
worker: python -m celery -A app.workers.celery_app worker --loglevel=info
beat: python -m celery -A app.workers.celery_app beat --loglevel=info
