# One container: API + WebSocket + MCP endpoint + the built web app.

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REGISTA_WEB_DIST=/app/web/dist \
    REGISTA_DOCS=/app/docs
WORKDIR /app
COPY README.md ./
COPY backend/pyproject.toml backend/README.md backend/
COPY backend/regista backend/regista
RUN pip install "./backend[azure]" && useradd --uid 10001 --create-home regista
COPY docs docs
COPY --from=web /web/dist web/dist
USER regista
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
# The Container Apps ingress is the only way in, so trust its X-Forwarded-For: per-visitor rate limits see real clients
CMD ["uvicorn", "regista.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
