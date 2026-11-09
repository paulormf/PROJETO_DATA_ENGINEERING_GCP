FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements-materializer.txt ./requirements-materializer.txt
RUN pip install --no-cache-dir -r requirements-materializer.txt

COPY src ./src
COPY config ./config

ENTRYPOINT ["python", "-m", "materialization.bigquery_full_materializer"]
