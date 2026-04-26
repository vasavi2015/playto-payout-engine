# Playto Payout Engine

Minimal Django + DRF payout engine for merchant balances, idempotent payout requests, concurrent fund holds, async payout processing, and React dashboard.

## Stack

- Backend: Django, Django REST Framework
- DB: PostgreSQL
- Worker: Celery + Redis
- Frontend: React + Tailwind
- Tests: pytest + Django TransactionTestCase

## Local setup with Docker

```bash
docker compose up --build
```

Backend runs on:

```text
http://localhost:8000
```

Seed data is created automatically by the backend container.

## Manual backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Run worker separately:

```bash
celery -A payout_engine worker -l info
```

## API usage

List seeded merchants:

```bash
curl http://localhost:8000/api/v1/merchants/
```

Get dashboard:

```bash
curl "http://localhost:8000/api/v1/dashboard/?merchant_id=1" \
  -H "X-Merchant-Id: 1"
```

Create payout:

```bash
curl -X POST http://localhost:8000/api/v1/payouts/ \
  -H "Content-Type: application/json" \
  -H "X-Merchant-Id: 1" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"amount_paise": 5000, "bank_account_id": 1}'
```

## Tests

```bash
cd backend
pytest
```

Important tests:

- `test_two_parallel_60_rupee_payouts_only_one_succeeds`
- `test_idempotency_returns_same_response_and_no_duplicate_payout`

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Set backend URL in `.env`:

```text
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Railway deployment

1. Push this repo to GitHub.
2. Create a new Railway project.
3. Add PostgreSQL plugin.
4. Add Redis plugin.
5. Deploy backend service from `/backend`.
6. Set environment variables:

```text
SECRET_KEY=your-secret
DEBUG=False
POSTGRES_DB=${{Postgres.PGDATABASE}}
POSTGRES_USER=${{Postgres.PGUSER}}
POSTGRES_PASSWORD=${{Postgres.PGPASSWORD}}
POSTGRES_HOST=${{Postgres.PGHOST}}
POSTGRES_PORT=${{Postgres.PGPORT}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
CORS_ALLOW_ALL_ORIGINS=True
```

7. Start command for web service:

```bash
python manage.py migrate && python manage.py seed && gunicorn payout_engine.wsgi:application --bind 0.0.0.0:$PORT
```

8. Add a second Railway service for worker with start command:

```bash
celery -A payout_engine worker -l info
```

## Render deployment

1. Create PostgreSQL and Redis instances.
2. Create Web Service from `/backend`.
3. Build command:

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

4. Start command:

```bash
python manage.py migrate && python manage.py seed && gunicorn payout_engine.wsgi:application --bind 0.0.0.0:$PORT
```

5. Create Background Worker with command:

```bash
celery -A payout_engine worker -l info
```
