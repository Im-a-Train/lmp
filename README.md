# LAN Pulse

LAN Pulse is a LAN-party network quality monitor with:

- a FastAPI backend backed by PostgreSQL
- a React operator dashboard
- a Tauri desktop client that registers itself and uploads live metrics
- Docker Compose for local/server deployment
- tests and GitHub Actions CI

This MVP is designed for trusted LAN environments only. Do not expose it directly to the public internet without adding authentication and hardening.

## What’s Implemented

- `GET /api/config`, `GET /api/dashboard/`, `GET /api/clients/`, `GET /api/clients/{id}`, `GET /api/events/`
- `POST /api/clients/register` and `POST /api/metrics/`
- UDP echo listener on port `8090`
- offline detection, retention cleanup, and health change events
- web dashboard with overview, client list, client detail charts, and download page
- Tauri client config persistence, registration, UDP measurements, throughput sampling, and periodic reporting
- CI for server, web, and client

## Run the Full Stack

Start the stack:

```bash
docker compose up --build
```

Services:

- Web UI and API: `http://localhost:8080`
- UDP echo: `localhost:8090/udp`

The compose app container serves the built React UI from `/` and the client download from `/downloads/client/latest`.

## Local Development

### Server

```bash
cd server
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Web

```bash
cd web
npm install
npm run dev -- --host 0.0.0.0
```

### Client

```bash
cd client
npm install
npm run tauri
```

## Tests

```bash
cd server && pytest
cd web && npm run test
cd client && npm run test:rust
```

## Client Packaging

Windows installers are built in GitHub Actions on `windows-latest` and uploaded as workflow artifacts.

For a local Linux bundle from a Dockerized builder environment:

```bash
cd client
npm run bundle:linux:docker
```

That command writes `downloads/client-latest-linux.AppImage`.

## Notes on Downloads

`downloads/client-latest.exe` is currently a checked-in placeholder so the end-to-end MVP path works immediately. Replace it with the packaged Tauri Windows installer artifact for real deployments.
