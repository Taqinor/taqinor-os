# backend/celery_worker/Dockerfile
FROM python:3.11-slim-buster

WORKDIR /app

ENV PYTHONUNBUFFERED 1

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

CMD ["celery", "-A", "erp_agentique", "worker", "-l", "info"]
