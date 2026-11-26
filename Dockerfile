# EcoByte: one image with the built React app + the FastAPI server.
#   docker build -t ecobyte . && docker run -p 8000:8000 ecobyte

# 1) Build the frontend
FROM node:22-alpine AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2) Python server that also serves the built frontend
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Canteen times (deadlines, "today", meal slots) follow the college's clock, not the server's UTC.
    TZ=Asia/Kolkata
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=web /app/frontend/dist /app/frontend/dist
RUN useradd --create-home ecobyte && chown -R ecobyte /app/backend/data
USER ecobyte
EXPOSE 8000
# Seed only runs when the database is empty, so restarts keep all data.
CMD ["sh", "-c", "python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
