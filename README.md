# Nuclei Cloud — Distributed Vulnerability Scanner Orchestrator

A production-ready, multi-user web platform for orchestrating [Nuclei](https://github.com/projectdiscovery/nuclei) scans at scale.

## Architecture

```
                    ┌──────────────────────────────────────┐
                    │          Nginx (Reverse Proxy)        │
                    │     Rate Limiting · TLS Termination   │
                    └────────────┬─────────────────────────┘
                                 │ :80
             ┌───────────────────┼───────────────────┐
             │                   │                   │
    ┌────────▼──────┐   ┌────────▼──────┐   ┌───────▼──────┐
    │   Next.js     │   │   FastAPI     │   │   Flower     │
    │   Frontend    │   │   Backend     │   │  (Monitor)   │
    │   :3000       │   │   :8000       │   │   :5555      │
    └───────────────┘   └──────┬────────┘   └──────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
 ┌────────▼──────┐  ┌──────────▼──────┐  ┌─────────▼─────┐
 │  PostgreSQL   │  │     Redis        │  │  Docker Vol.  │
 │  (models +    │  │  (Celery queue   │  │  (templates + │
 │   findings)   │  │   + cache)       │  │   outputs)    │
 └───────────────┘  └──────────┬───────┘  └───────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼────┐  ┌────────▼─────┐  ┌──────▼──────────┐
    │  Worker:scan │  │Worker:notify │  │  Celery Beat    │
    │  (Nuclei)    │  │ (Webhooks)   │  │  (Scheduler)    │
    └─────────┬────┘  └──────────────┘  └─────────────────┘
              │ executes
    ┌─────────▼──────────┐
    │   nuclei binary    │
    │   -json streaming  │
    └────────────────────┘
```

## Features

| Feature | Details |
|---------|---------|
| **Multi-user RBAC** | ADMIN / ANALYST / VIEWER roles with JWT auth |
| **Target Management** | URL, IP, CIDR, Domain; bulk import; file upload; auto-dedup |
| **Template Management** | Auto-sync from projectdiscovery/nuclei-templates; custom YAML upload/editor |
| **Scan Orchestration** | Immediate + scheduled scans; real-time SSE streaming; cancellation |
| **Dashboard** | Severity breakdown pie chart; stats cards; recent scans/findings |
| **Full-text Search** | Search findings by template, host, description |
| **Webhooks** | Discord, Slack, Jira, Generic HTTP; HMAC signing; per-severity filter |
| **API Documentation** | Swagger UI at `/api/docs` |
| **Async Processing** | Celery + Redis; findings streamed in 50-item batches |
| **Performance** | Rate limiting, bulk-size, concurrency configurable per scan |

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — set SECRET_KEY, admin credentials

# 2. Launch everything
docker compose up -d

# 3. Open the dashboard
open http://localhost

# Default credentials:
# Email: admin@nucleicloud.local
# Password: changeme123!
```

**API Docs:** http://localhost/api/docs
**Flower (queue monitor):** http://localhost:5555

## Project Structure

```
nuclei_cloud/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point + lifespan
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy engine
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── user.py          # User + UserRole enum
│   │   │   ├── target.py        # Target + TargetList (M:M)
│   │   │   ├── scan.py          # Scan + ScanTargetList
│   │   │   ├── finding.py       # Finding (nuclei output)
│   │   │   ├── template.py      # Template (official + custom)
│   │   │   └── webhook.py       # Webhook (Discord/Slack/etc.)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── api/v1/              # REST API routes
│   │   │   ├── auth.py          # Login, refresh, API key
│   │   │   ├── users.py         # CRUD users (admin)
│   │   │   ├── targets.py       # Targets + target lists
│   │   │   ├── scans.py         # Scans + SSE stream
│   │   │   ├── findings.py      # Findings + full-text search
│   │   │   ├── webhooks.py      # Webhook CRUD + test
│   │   │   └── templates.py     # Template list + sync + editor
│   │   ├── core/
│   │   │   ├── security.py      # JWT, bcrypt, API key generation
│   │   │   └── rbac.py          # Role guards (Depends)
│   │   └── workers/
│   │       ├── celery_app.py    # Celery config + beat schedule
│   │       ├── scan_tasks.py    # ★ Core nuclei orchestrator
│   │       ├── notification_tasks.py  # Webhook dispatcher
│   │       └── template_tasks.py     # Git sync + indexer
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── app/                 # Next.js App Router pages
│       │   ├── page.tsx         # Dashboard
│       │   ├── scans/           # Scan list + detail + new
│       │   ├── findings/        # Global findings browser
│       │   ├── targets/         # Target list manager
│       │   ├── templates/       # Template browser + sync
│       │   ├── webhooks/        # Webhook manager
│       │   ├── users/           # User manager (admin)
│       │   └── settings/        # Account + API key
│       ├── components/
│       │   ├── layout/          # Sidebar + AppLayout guard
│       │   ├── dashboard/       # StatsCards + SeverityChart
│       │   ├── scans/           # ScanBadge
│       │   └── findings/        # SeverityBadge
│       ├── lib/
│       │   ├── api.ts           # Axios client + interceptors
│       │   ├── auth.ts          # Login/logout/cookie helpers
│       │   └── utils.ts         # Date helpers + severity config
│       └── types/index.ts       # Full TypeScript types
├── nginx/nginx.conf             # Reverse proxy + rate limiting
├── docker-compose.yml           # Full stack orchestration
└── .env.example                 # Environment template
```

## Scan Flow

```
POST /api/v1/scans
  → validates RBAC + target lists
  → creates Scan record (PENDING)
  → publishes task to Redis (Celery)
  → returns scan_id immediately      ← non-blocking ✓

Redis Queue
  → Celery worker picks up task
  → fetches all targets from DB
  → writes targets.txt to temp dir
  → exec: nuclei -list targets.txt -json-export results.json ...
  → streams stdout line by line
  → parses JSON findings in real-time
  → INSERT findings in 50-item batches
  → UPDATE scan counters per batch
  → finalizes status (DONE / FAILED)
  → dispatches webhook notifications

GET /api/v1/scans/{id}/stream  (Server-Sent Events)
  → polls DB every 3s
  → emits status + new findings live
  → closes when scan terminates
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login → JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Current user |
| GET | `/api/v1/scans/stats` | Dashboard aggregate stats |
| POST | `/api/v1/scans` | Create + launch scan |
| GET | `/api/v1/scans/{id}/stream` | SSE live updates |
| POST | `/api/v1/scans/{id}/cancel` | Cancel running scan |
| POST | `/api/v1/targets/import` | Bulk import targets |
| POST | `/api/v1/targets/upload` | Upload .txt file |
| GET | `/api/v1/findings` | Paginated findings + search |
| GET | `/api/v1/findings/stats` | Severity aggregation |
| POST | `/api/v1/templates/sync` | Trigger template sync (admin) |
| POST | `/api/v1/webhooks/{id}/test` | Fire test notification |

Full interactive docs: `http://localhost/api/docs`

## Security

- JWT access tokens (60 min) + refresh tokens (30 days)
- bcrypt password hashing
- RBAC enforced at every endpoint via FastAPI `Depends`
- HMAC-SHA256 webhook payload signing
- Nginx rate limiting: 60 req/min (API), 10 req/min (auth)
- No shell injection: nuclei args built as list (no `shell=True`)
- Input validation via Pydantic v2

## Scaling

To scale scan workers horizontally:
```bash
docker compose up --scale worker-scans=4 -d
```

Each worker handles one scan at a time (`worker_prefetch_multiplier=1`) to avoid memory contention with nuclei subprocess output.
