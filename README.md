# Transition Support Portal POC

This proof of concept implements the requested React + FastAPI + PostgreSQL stack for users moving from an older tool to a new tool. It includes role-based dashboards for property staff/owners, CMCs, and admins, plus mocked Zoom, Outlook, and training integrations.

## What is included

- React + Vite frontend with persona switcher.
- FastAPI backend with async SQLAlchemy models.
- PostgreSQL local container that maps to Amazon RDS PostgreSQL in production.
- Mock integration services for:
  - Third-party training API.
  - Microsoft Graph free/busy and Outlook calendar events.
  - Zoom meeting creation.
  - Notification queue records.
- Seed data for one property, one owner, two staff users, two CMCs, and one admin.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open the frontend at `http://localhost:5173` and the FastAPI docs at `http://localhost:8000/docs`.

## Seed personas

The UI fetches these automatically from `/api/debug/seed-users`:

- Avery Admin: admin persona.
- Casey CMC: assigned CMC persona.
- Morgan CMC Admin: CMC with admin privilege.
- Olivia Owner: property owner persona.
- Sam Staff: property staff persona.
- Taylor Trainer: second property staff persona.

## Environment variables

Set `MOCK_INTEGRATIONS=false` only after configuring real credentials.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string. Use Amazon RDS in production. |
| `TRAINING_API_BASE_URL` / `TRAINING_API_KEY` | Third-party training-status provider. |
| `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` | Microsoft Graph app credentials for Outlook calendar access. |
| `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` | Zoom Server-to-Server OAuth credentials. |
| `NOTIFICATION_FROM_EMAIL` | Sender for confirmation/reminder emails. |

## API examples

List POC users:

```bash
curl http://localhost:8000/api/debug/seed-users
```

List properties for a persona:

```bash
curl -H "X-User-Id: 00000000-0000-0000-0000-000000000004" \
  http://localhost:8000/api/properties
```

Find available slots:

```bash
curl -H "X-User-Id: 00000000-0000-0000-0000-000000000004" \
  "http://localhost:8000/api/scheduling/slots?property_id=10000000-0000-0000-0000-000000000001&start=2026-06-04T09:00:00%2B05:30&end=2026-06-10T17:00:00%2B05:30&timezone=Asia/Kolkata&duration_minutes=30"
```

Book a follow-up call:

```bash
curl -X POST http://localhost:8000/api/scheduling/book \
  -H "Content-Type: application/json" \
  -H "X-User-Id: 00000000-0000-0000-0000-000000000004" \
  -d '{
    "property_id":"10000000-0000-0000-0000-000000000001",
    "call_type":"follow_up",
    "start_time":"2026-06-04T09:00:00+05:30",
    "end_time":"2026-06-04T09:30:00+05:30",
    "timezone":"Asia/Kolkata",
    "attendee_user_ids":[]
  }'
```

## Production hardening backlog

1. Replace development header authentication with SSO/JWT validation.
2. Add Alembic migrations and automated migration pipeline.
3. Add row-level authorization tests and audit log coverage.
4. Replace mock integrations with Microsoft Graph, Zoom, and training-provider clients.
5. Move reminders to a durable queue/scheduler such as EventBridge Scheduler + Lambda, Celery, or APScheduler with a persistent job store.
6. Add integration failure handling and reconciliation jobs for calendar/Zoom drift.
7. Add observability with structured logs, metrics, traces, and dead-letter queues.
