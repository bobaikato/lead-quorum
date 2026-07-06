# One image, two roles. Which one a container plays is chosen at run time by SERVICE:
#   SERVICE=a2a  AGENT=enrichment|rederive  -> a specialist A2A microservice
#   SERVICE=web  (default)                  -> the orchestrator + frontend
# Cloud Run injects $PORT; everything binds to it.
FROM python:3.12-slim

WORKDIR /app

# Dependencies first so the layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app
ENV SERVICE=web

CMD ["sh", "-c", "if [ \"$SERVICE\" = a2a ]; then exec uvicorn agents.a2a_server:app --host 0.0.0.0 --port ${PORT:-8080}; else exec uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8080}; fi"]
