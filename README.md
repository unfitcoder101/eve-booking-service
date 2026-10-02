# EVE Booking Service

Backend for booking diagnostic tests, with a simulated payment service and an idempotent payment webhook. Built with FastAPI, PostgreSQL and SQLAlchemy.

## Run locally

Requires Python 3.12 and PostgreSQL 16.

```bash
git clone https://github.com/unfitcoder101/eve-booking-service.git
cd eve-booking-service
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

createdb eve_booking
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(engine)"
python seed.py                      # sample centres and tests
python -m uvicorn app.main:app --reload
```

Interactive docs (Swagger): http://127.0.0.1:8000/docs

Optional environment variables: `DATABASE_URL` (default `postgresql+psycopg2://localhost/eve_booking`), `SECRET_KEY` (JWT signing key), `WEBHOOK_SECRET` (default `dev-webhook-secret`). Change both secrets outside local development.

### Run the tests

```bash
createdb eve_booking_test
python -m pytest -q
```

The tests use a separate database (`eve_booking_test`) that is wiped for every test, and they refuse to run against any other database.

## API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/signup` | no | Create an account |
| POST | `/auth/login` | no | Get a JWT |
| GET | `/auth/me` | JWT | Current user |
| GET | `/centres` | no | List centres with tests and prices (`location`, `skip`, `limit`) |
| GET | `/centres/{id}` | no | One centre |
| POST | `/centres` | JWT | Create a centre |
| POST | `/centres/{id}/tests` | JWT | Add a test with a price to a centre |
| POST | `/bookings` | JWT | Book a test (starts as PENDING) |
| GET | `/bookings` | JWT | My bookings (`status`, `skip`, `limit`) |
| GET | `/bookings/{id}` | JWT | One of my bookings |
| POST | `/bookings/{id}/cancel` | JWT | Cancel a booking |
| POST | `/payments/` | JWT | Simulated payment (SUCCESS or FAILED) |
| POST | `/payments/webhook/` | secret header | Payment status update from the provider |

### Example requests

```bash
# Sign up and log in
curl -X POST localhost:8000/auth/signup -H "Content-Type: application/json" \
  -d '{"email":"a@example.com","password":"Password123","full_name":"Asha"}'
curl -X POST localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"a@example.com","password":"Password123"}'
# -> {"access_token":"<JWT>","token_type":"bearer"}

# Book a test (price comes from the centre, not the client)
curl -X POST localhost:8000/bookings -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"centre_id":1,"test_id":1,"appointment_at":"2026-12-01T10:00:00+05:30"}'

# Pay. "simulate" is optional and forces an outcome; without it the result is random (70% success)
curl -X POST localhost:8000/payments/ -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" -d '{"booking_id":1,"simulate":"SUCCESS"}'

# Webhook from the payment provider
curl -X POST localhost:8000/payments/webhook/ \
  -H "x-webhook-secret: dev-webhook-secret" -H "Content-Type: application/json" \
  -d '{"event_id":"evt_001","provider_reference":"mock_...","status":"SUCCESS"}'
# -> {"result":"processed"}   (sending it again -> {"result":"duplicate_ignored"})
```

## Database design

| Table | Purpose |
|---|---|
| `users` | Email (unique), bcrypt password hash, name |
| `centres` | Centre name and location |
| `tests` | Test catalogue (unique names) |
| `centre_tests` | Which centre offers which test, and its price. Unique on (centre, test) |
| `bookings` | User, centre_test, appointment time, amount, status |
| `payments` | One row per payment attempt. `provider_reference` is unique |
| `webhook_events` | Every processed webhook `event_id` (unique) plus its payload |

Design choices:
- **Price is copied into the booking** when it is created, so later price changes never alter past bookings, and the client can never choose its own price.
- **Tests and centres are separate tables joined by `centre_tests`**, because the same test (e.g. Blood Sugar) is offered by many centres at different prices.
- **Money uses `NUMERIC(10,2)`** in the database.
- **Unique constraints** on event IDs, payment references and (centre, test) pairs mean the database itself blocks duplicates even if application code has a bug.

### Booking states

`PENDING` -> `CONFIRMED` (payment success) or `FAILED` (payment failed). A `FAILED` booking can be paid again. `PENDING` or `CONFIRMED` can be `CANCELLED`. A cancelled booking cannot be paid or changed by a webhook.

## Webhook idempotency

1. The shared secret header is checked first (constant-time comparison).
2. The `event_id` is inserted into `webhook_events`, which has a unique constraint. If the insert fails, the event was already handled: nothing changes and the endpoint still returns `200` (`duplicate_ignored`), so the provider stops retrying.
3. The payment and booking updates happen in the same transaction as the event insert, so they succeed or fail together.
4. The booking row is locked (`SELECT ... FOR UPDATE`) while it is updated, so two concurrent requests cannot corrupt it.
5. A successful payment is never downgraded by a late `FAILED` event, and a cancelled booking is never changed by a webhook.

## Edge cases handled

- Invalid or missing fields: `422` (Pydantic validation, including password length and valid email)
- Duplicate signup email: `409`
- Wrong email or password: `401` with the same message for both cases
- Missing or expired token: `401`/`403`
- Unknown booking, or someone else's booking: `404` (the same answer, so IDs cannot be probed)
- Booking a test the centre does not offer, or an appointment in the past: `404` / `422`
- Paying a confirmed or cancelled booking: `409`
- Wrong webhook secret: `401`; unknown payment reference: `404`

## Assumptions

- Payments are all in a single currency (INR) and a full payment is required to confirm.
- Any logged-in user can create centres and tests (there is no admin role).
- Naive appointment times are treated as UTC.
- A failed payment may be retried on the same booking.

## What I would improve with more time

- Roles (admin vs patient) for managing centres and tests
- Alembic migrations instead of `create_all`
- Verify webhooks with an HMAC signature and timestamp instead of a shared secret
- Slot capacity per centre to prevent double booking the same time
- Refunds when a confirmed booking is cancelled
- Docker and docker-compose, Redis caching for centre listings, rate limiting on login, and structured logging
