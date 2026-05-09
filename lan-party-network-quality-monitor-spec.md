# LAN Party Network Quality Monitor — Implementation Specification

## 1. Goal

Build a small LAN-party network quality monitoring application.

The system consists of:

1. A server application running on an Ubuntu server.
2. A web interface with:
   - overview dashboard
   - client list
   - client detail view
   - downloadable Windows client installer
3. A lightweight Windows desktop client installed on each participant PC.
4. A database schema suitable for future Grafana integration.

No authentication is required for the MVP.

---

## 2. Recommended Tech Stack

### Server

| Area | Choice | Reason |
|---|---|---|
| Backend API | FastAPI / Python | Fast to build, good WebSocket support, easy Docker deployment |
| Frontend | React + Vite + TypeScript | Simple SPA, fast dashboard development |
| Database | PostgreSQL | Grafana-compatible, reliable, easy Docker setup |
| Time-series layout | PostgreSQL tables designed for TimescaleDB later | Allows Grafana or TimescaleDB extension to be added later |
| Realtime updates | WebSocket from server to browser | Live dashboard without polling |
| Packaging | Docker + Docker Compose | Easy startup on Ubuntu server |
| Static file serving | FastAPI or Caddy/Nginx inside container | Serves frontend and client downloads |

### Windows Client

| Area | Choice | Reason |
|---|---|---|
| Desktop app | Tauri 2 |
| UI | React + TypeScript |
| Native logic | Rust |
| Packaging | Tauri Windows MSI or EXE installer |
| Network tests | Rust async networking |
| Server communication | HTTP JSON + optional WebSocket later |

Tauri is recommended instead of Electron because it creates smaller desktop apps and uses the native OS webview. The client also needs some native capabilities, especially for network interface discovery and stable background execution.

---

## 3. High-Level Architecture

```text
+---------------------------------------------------------+
| Ubuntu Server                                           |
|                                                         |
|  +-------------------+        +----------------------+  |
|  | FastAPI Backend   | <----> | PostgreSQL Database  |  |
|  +---------+---------+        +----------------------+  |
|            |                                            |
|            | serves REST API, WebSocket, frontend       |
|            v                                            |
|  +-------------------+                                  |
|  | React Web UI      |                                  |
|  +-------------------+                                  |
|                                                         |
|  /downloads/client-latest.exe                           |
+-------------------^-------------------------------------+
                    |
                    | HTTP metrics upload
                    |
+-------------------+---------------------+
| Windows Client PCs                      |
|                                         |
|  +-------------------------------+      |
|  | Tauri Client                  |      |
|  | - ping/latency checks         |      |
|  | - UDP loss/jitter checks      |      |
|  | - network interface stats     |      |
|  | - reports metrics to server   |      |
|  +-------------------------------+      |
+-----------------------------------------+
```

---

## 4. Monitoring Model

Avoid a full peer-to-peer mesh by default.

### Default checks

Each client should measure against:

1. Monitoring server
2. Optional configured game server
3. Optional LAN gateway/router

This gives useful data without creating unnecessary LAN traffic.

### Optional future check

A controlled peer test mode can be added later:

- server selects a small rotating set of peer pairs
- clients do short UDP tests
- results are reported centrally

Do not let every client constantly test every other client.

---

## 5. MVP Features

### Server Web UI

#### Overview Dashboard

Show:

- number of online clients
- number of offline clients
- worst latency clients
- packet loss alerts
- jitter alerts
- top bandwidth users
- recent events
- global LAN health indicator

Suggested health states:

| State | Meaning |
|---|---|
| Green | all clients healthy |
| Yellow | latency/jitter elevated or one minor issue |
| Red | packet loss, severe latency, or multiple clients affected |

#### Client List

Columns:

- hostname
- username
- IP address
- OS
- client version
- online/offline
- last seen
- latency to server
- packet loss
- jitter
- upload Mbps
- download Mbps
- health status

#### Client Detail View

Show:

- client metadata
- current status
- latency graph
- jitter graph
- packet loss graph
- network throughput graph
- recent events
- last submitted metrics payload
- client version

#### Download Page

Show:

- latest Windows client download button
- server URL the client should use
- simple installation instructions

Example:

```text
Download Windows Client
Server URL: http://192.168.1.10:8080
```

---

## 6. Windows Client Features

### Required MVP Behavior

The Windows client should:

1. Start as a normal desktop application.
2. Ask for or auto-detect the server URL on first launch.
3. Save config locally.
4. Register itself with the server.
5. Run periodic measurements.
6. Upload metrics every 2 seconds.
7. Show a small local status window:
   - connected/disconnected
   - server URL
   - last latency
   - packet loss
   - client ID
8. Keep running while the app is open.

### Optional Later Behavior

- start with Windows
- minimize to system tray
- auto-update
- signed installer
- peer-to-peer test mode
- user nickname/team name
- QR-code setup from web UI

---

## 7. Network Measurements

### Metrics to Collect

Each client should collect:

| Metric | Description |
|---|---|
| latency_ms | round-trip latency to server |
| jitter_ms | variation in latency |
| packet_loss_percent | lost packets during measurement window |
| tx_mbps | outbound throughput estimate |
| rx_mbps | inbound throughput estimate |
| interface_name | active network adapter |
| local_ip | client IP |
| gateway_ip | optional detected gateway |
| server_reachable | boolean |
| game_server_latency_ms | optional |
| game_server_packet_loss_percent | optional |

### Recommended Measurement Strategy

#### Latency

Use UDP echo if possible.

Flow:

1. Client sends small UDP packet to server.
2. Server echoes packet immediately.
3. Client measures round-trip time.

Fallback:

- HTTP `/api/ping`
- ICMP ping only if permissions allow it

#### Packet Loss

Use UDP sequence numbers.

Example:

- client sends 20 UDP packets in a short test window
- server echoes each packet
- client calculates missing responses

#### Jitter

Calculate jitter from recent UDP RTT samples.

Simple MVP formula:

```text
jitter = average absolute difference between consecutive latency samples
```

#### Bandwidth

For MVP, do not run active bandwidth stress tests.

Instead:

- read OS network interface byte counters
- calculate delta between samples
- submit tx/rx Mbps

This avoids disturbing the LAN party.

---

## 8. API Specification

Base URL:

```text
http://SERVER_IP:8080
```

### `GET /`

Serves the web UI.

---

### `GET /downloads/client/latest`

Returns the latest Windows client installer.

---

### `GET /api/config`

Returns public server config.

Response:

```json
{
  "server_name": "LAN Party Monitor",
  "metrics_interval_seconds": 2,
  "udp_echo_port": 8090,
  "client_min_version": "0.1.0"
}
```

---

### `POST /api/clients/register`

Registers or updates a client.

Request:

```json
{
  "client_id": "uuid-v4-or-existing",
  "hostname": "PC-12",
  "username": "melvin",
  "os": "Windows 11",
  "client_version": "0.1.0",
  "local_ip": "192.168.1.42",
  "interface_name": "Ethernet"
}
```

Response:

```json
{
  "client_id": "uuid-v4-or-existing",
  "accepted": true,
  "metrics_interval_seconds": 2,
  "udp_echo_host": "192.168.1.10",
  "udp_echo_port": 8090
}
```

---

### `POST /api/metrics`

Uploads client metrics.

Request:

```json
{
  "client_id": "uuid-v4",
  "timestamp": "2026-05-09T20:15:00Z",
  "latency_ms": 1.2,
  "jitter_ms": 0.3,
  "packet_loss_percent": 0,
  "tx_mbps": 12.5,
  "rx_mbps": 45.8,
  "server_reachable": true,
  "game_server_latency_ms": null,
  "game_server_packet_loss_percent": null
}
```

Response:

```json
{
  "ok": true
}
```

---

### `GET /api/clients`

Returns current client list.

Response:

```json
[
  {
    "client_id": "uuid-v4",
    "hostname": "PC-12",
    "username": "melvin",
    "local_ip": "192.168.1.42",
    "online": true,
    "last_seen": "2026-05-09T20:15:00Z",
    "latency_ms": 1.2,
    "jitter_ms": 0.3,
    "packet_loss_percent": 0,
    "tx_mbps": 12.5,
    "rx_mbps": 45.8,
    "health": "green"
  }
]
```

---

### `GET /api/clients/{client_id}`

Returns detailed client metadata and recent metrics.

Query params:

```text
from=2026-05-09T19:00:00Z
to=2026-05-09T20:00:00Z
limit=1000
```

---

### `GET /api/events`

Returns recent network events.

---

### `WS /ws/dashboard`

Realtime dashboard updates.

Broadcast events:

```json
{
  "type": "client_metrics",
  "client_id": "uuid-v4",
  "metrics": {
    "latency_ms": 1.2,
    "jitter_ms": 0.3,
    "packet_loss_percent": 0
  }
}
```

---

## 9. UDP Echo Protocol

### Server

Listen on UDP port `8090`.

When a packet is received:

- echo the same payload back to sender immediately

### Client Packet

Binary or JSON is acceptable.

MVP JSON packet:

```json
{
  "client_id": "uuid-v4",
  "seq": 12345,
  "sent_at_unix_ms": 1778357700000
}
```

### Notes

For performance, binary packets can replace JSON later. JSON is fine for the MVP.

---

## 10. Database Design

Use PostgreSQL.

The schema should be Grafana-friendly. Store measurements as timestamped rows with numeric columns.

### Table: `clients`

```sql
CREATE TABLE clients (
    client_id UUID PRIMARY KEY,
    hostname TEXT NOT NULL,
    username TEXT,
    os TEXT,
    client_version TEXT,
    local_ip INET,
    interface_name TEXT,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_status TEXT NOT NULL DEFAULT 'unknown'
);
```

### Table: `client_metrics`

```sql
CREATE TABLE client_metrics (
    id BIGSERIAL PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    latency_ms DOUBLE PRECISION,
    jitter_ms DOUBLE PRECISION,
    packet_loss_percent DOUBLE PRECISION,
    tx_mbps DOUBLE PRECISION,
    rx_mbps DOUBLE PRECISION,
    server_reachable BOOLEAN,
    game_server_latency_ms DOUBLE PRECISION,
    game_server_packet_loss_percent DOUBLE PRECISION
);

CREATE INDEX idx_client_metrics_ts ON client_metrics (ts DESC);
CREATE INDEX idx_client_metrics_client_ts ON client_metrics (client_id, ts DESC);
```

### Table: `events`

```sql
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    severity TEXT NOT NULL,
    client_id UUID REFERENCES clients(client_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    data JSONB
);

CREATE INDEX idx_events_ts ON events (ts DESC);
CREATE INDEX idx_events_client_ts ON events (client_id, ts DESC);
```

### Future TimescaleDB Migration

If TimescaleDB is added later:

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
SELECT create_hypertable('client_metrics', 'ts');
```

Grafana can query the PostgreSQL database directly.

---

## 11. Health Calculation

### Client Online Status

A client is online if:

```text
now - last_seen <= 10 seconds
```

Otherwise offline.

### Health Rules

Suggested MVP thresholds:

| Metric | Green | Yellow | Red |
|---|---:|---:|---:|
| latency_ms | <= 5 ms | <= 20 ms | > 20 ms |
| jitter_ms | <= 2 ms | <= 10 ms | > 10 ms |
| packet_loss_percent | 0% | <= 1% | > 1% |

Client health is the worst state of its current metrics.

Global health is the worst state of all online clients, with an additional warning if more than 20% of clients are offline.

---

## 12. Docker Setup

### Services

Use Docker Compose with:

1. `app`
   - FastAPI backend
   - built React frontend
   - static client download files
   - UDP echo listener
2. `db`
   - PostgreSQL

### Example `docker-compose.yml`

```yaml
services:
  app:
    build: .
    container_name: lan-monitor-app
    ports:
      - "8080:8080/tcp"
      - "8090:8090/udp"
    environment:
      DATABASE_URL: postgresql://lanmonitor:lanmonitor@db:5432/lanmonitor
      PUBLIC_BASE_URL: http://localhost:8080
      UDP_ECHO_PORT: 8090
    volumes:
      - ./downloads:/app/downloads
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:16
    container_name: lan-monitor-db
    environment:
      POSTGRES_USER: lanmonitor
      POSTGRES_PASSWORD: lanmonitor
      POSTGRES_DB: lanmonitor
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### Startup

```bash
docker compose up -d
```

Web UI:

```text
http://SERVER_IP:8080
```

---

## 13. Repository Structure

Recommended monorepo:

```text
lan-party-monitor/
  README.md
  docker-compose.yml
  Dockerfile

  server/
    app/
      main.py
      api/
        clients.py
        metrics.py
        events.py
        downloads.py
      core/
        config.py
        database.py
        health.py
        udp_echo.py
        websocket.py
      models/
        client.py
        metric.py
        event.py
      migrations/
    pyproject.toml

  web/
    index.html
    package.json
    src/
      main.tsx
      App.tsx
      api/
      components/
      pages/
        DashboardPage.tsx
        ClientsPage.tsx
        ClientDetailPage.tsx
        DownloadPage.tsx

  client/
    package.json
    src/
      main.tsx
      App.tsx
    src-tauri/
      Cargo.toml
      tauri.conf.json
      src/
        main.rs
        config.rs
        metrics.rs
        network.rs
        reporter.rs

  downloads/
    client-latest.exe
```

---

## 14. Backend Implementation Notes

### FastAPI Modules

- `main.py`
  - app setup
  - static frontend serving
  - router registration
  - startup/shutdown hooks
- `database.py`
  - async SQLAlchemy engine
  - session handling
- `udp_echo.py`
  - asyncio UDP echo server
- `websocket.py`
  - dashboard connection manager
- `health.py`
  - health threshold logic

### Background Tasks

The server should run:

1. UDP echo server
2. offline client detector
3. event generator for threshold changes

---

## 15. Frontend Implementation Notes

### Main Pages

1. `/`
   - dashboard overview
2. `/clients`
   - client list
3. `/clients/:clientId`
   - detail view
4. `/download`
   - Windows client download page

### UI Components

- `HealthBadge`
- `MetricCard`
- `ClientTable`
- `LatencyChart`
- `PacketLossChart`
- `ThroughputChart`
- `EventList`

### Chart Library

Use one of:

- Recharts
- Apache ECharts

For MVP, Recharts is simpler.

---

## 16. Client Implementation Notes

### Config File

Store locally, for example:

```text
%APPDATA%\LanPartyMonitor\config.json
```

Example:

```json
{
  "client_id": "uuid-v4",
  "server_url": "http://192.168.1.10:8080",
  "metrics_interval_seconds": 2
}
```

### Client Loop

Pseudo-code:

```text
load config
if no server_url:
    show setup screen

register client with server

loop every metrics_interval_seconds:
    measure udp latency/loss/jitter
    read network interface counters
    POST /api/metrics
    update local UI status
```

### Windows Network Interface Stats

The Rust client should read:

- active network interface
- bytes sent/received
- local IP

Possible Rust crates:

- `sysinfo`
- `network-interface`
- `tokio`
- `reqwest`
- `serde`
- `uuid`

---

## 17. Security Notes

MVP has no authentication because it is intended for a trusted LAN.

Still implement:

- request size limits
- basic input validation
- no shell execution from API
- no arbitrary file downloads
- CORS restricted to local server origin if possible
- clear warning in README that the app is not internet-facing

Do not expose this service directly to the public internet without adding authentication.

---

## 18. Configuration

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | required | PostgreSQL connection string |
| `PUBLIC_BASE_URL` | `http://localhost:8080` | URL shown to clients |
| `METRICS_INTERVAL_SECONDS` | `2` | Client report interval |
| `CLIENT_OFFLINE_AFTER_SECONDS` | `10` | Offline threshold |
| `UDP_ECHO_PORT` | `8090` | UDP echo port |
| `RETENTION_DAYS` | `7` | Optional cleanup retention |
| `GAME_SERVER_HOST` | empty | Optional game server target |

---

## 19. Data Retention

For LAN parties, full long-term retention is not needed.

MVP:

- keep metrics for 7 days by default
- keep events for 30 days

Optional cleanup job:

```sql
DELETE FROM client_metrics WHERE ts < now() - interval '7 days';
DELETE FROM events WHERE ts < now() - interval '30 days';
```

---

## 20. MVP Implementation Milestones

### Milestone 1 — Server Skeleton

- Docker Compose
- FastAPI app
- PostgreSQL connection
- database migrations
- health endpoint

### Milestone 2 — Client Registration and Metrics API

- `POST /api/clients/register`
- `POST /api/metrics`
- `GET /api/clients`
- database writes

### Milestone 3 — UDP Echo

- UDP echo server
- basic test client script
- latency and loss calculation

### Milestone 4 — Web Dashboard

- React dashboard
- client table
- client detail page
- charts
- WebSocket updates

### Milestone 5 — Windows Client

- Tauri app
- setup screen
- registration
- UDP measurement loop
- metrics upload
- local status UI

### Milestone 6 — Packaging

- Docker image for server
- Tauri Windows installer
- server download endpoint
- README startup instructions

---

## 21. Acceptance Criteria

The MVP is complete when:

1. The server starts with:

```bash
docker compose up -d
```

2. The web UI is available at:

```text
http://SERVER_IP:8080
```

3. The web UI offers a Windows client download.

4. A Windows client can be installed and pointed at the server.

5. The client appears online in the dashboard.

6. The dashboard shows:
   - latency
   - jitter
   - packet loss
   - throughput
   - online/offline status

7. Client detail view shows recent metric history.

8. Data is stored in PostgreSQL in a Grafana-queryable format.

---

## 22. Non-Goals for MVP

Do not implement initially:

- authentication
- cloud hosting
- complex user management
- full peer-to-peer mesh testing
- active bandwidth stress tests
- automatic client updates
- internet exposure
- mobile clients

---

## 23. Suggested Project Name

Working name:

```text
LAN Pulse
```

Alternative names:

- LAN Quality Monitor
- PartyPing
- NetParty Monitor
- LAN Health Board
