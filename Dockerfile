# Облачный запуск студии: бэкенд + собранный интерфейс на одном порту.
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
COPY backend/prompt_setup_catalogue.json /app/backend/prompt_setup_catalogue.json
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock.txt backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt
COPY backend/ backend/
COPY docs/ docs/
COPY --from=web /app/frontend/dist frontend/dist
ENV STUDIO_DATA_DIR=/data
VOLUME /data
EXPOSE 8000
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000","--no-access-log","--proxy-headers","--forwarded-allow-ips","*"]
