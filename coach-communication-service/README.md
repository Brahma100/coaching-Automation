# coach-communication-service

Reusable, provider-agnostic communication platform for coaching apps.

## Features
- Event-driven messaging workflow
- Provider adapters (Telegram and WhatsApp scaffold)
- Async delivery worker with retry and fallback
- Quiet hours and rule-driven automations
- Role-protected configuration APIs
- Encrypted provider credentials
- Python SDK for external emitters
- Backward compatibility wrapper for legacy Telegram calls

## Quick start
```bash
pip install -e .[dev]
uvicorn communication.app:app --reload
```

## API overview
- `POST /api/messages/events` emit business event
- `POST /api/providers` add or update provider config
- `POST /api/templates` manage message templates
- `POST /api/rules` configure automation rules
- `GET /api/analytics/summary` view delivery metrics
- `POST /api/telegram/link-token` issue signed Telegram linking deep-link token
- `POST /api/telegram/consume-link-update` parse+verify Telegram `/start link_...` updates

## UI
`ui/` contains a React dashboard scaffold for provider/rule/template/log/analytics workflows.

## SDK usage
```python
from sdk.client import CommunicationClient

client = CommunicationClient(base_url="http://localhost:8000")
client.emit_event("attendance.submitted", tenant_id="school-a", payload={"student_name": "Aarav"})
```
