FROM node:20-bookworm-slim AS web-builder

WORKDIR /workspace/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY server/requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY server/app ./app
COPY --from=web-builder /workspace/web/dist /app/web-dist
COPY downloads /app/downloads

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
