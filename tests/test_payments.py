from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Payment, WebhookEvent

SECRET = {"x-webhook-secret": "dev-webhook-secret"}


def pay(client, user, booking_id, simulate=None):
    body = {"booking_id": booking_id}
    if simulate:
        body["simulate"] = simulate
    return client.post("/payments/", json=body, headers=user)


def status_of(client, user, booking_id):
    return client.get(f"/bookings/{booking_id}", headers=user).json()["status"]


def webhook(client, event_id, reference, status="SUCCESS", headers=SECRET):
    body = {"event_id": event_id, "provider_reference": reference, "status": status}
    return client.post("/payments/webhook/", json=body, headers=headers)


def row_count(model):
    db = SessionLocal()
    n = db.scalar(select(func.count()).select_from(model))
    db.close()
    return n


def test_successful_payment_confirms_booking(client, user, booking):
    r = pay(client, user, booking["id"], "SUCCESS")
    assert r.status_code == 201
    assert r.json()["booking_status"] == "CONFIRMED"


def test_failed_payment_marks_booking_failed_then_retry_works(client, user, booking):
    assert pay(client, user, booking["id"], "FAILED").json()["booking_status"] == "FAILED"
    assert pay(client, user, booking["id"], "SUCCESS").json()["booking_status"] == "CONFIRMED"


def test_paid_booking_cannot_be_paid_again(client, user, booking):
    pay(client, user, booking["id"], "SUCCESS")
    assert pay(client, user, booking["id"], "SUCCESS").status_code == 409
    assert row_count(Payment) == 1


def test_cancelled_booking_cannot_be_paid(client, user, booking):
    client.post(f"/bookings/{booking['id']}/cancel", headers=user)
    assert pay(client, user, booking["id"]).status_code == 409


def test_cannot_pay_someone_elses_booking(client, booking, other_user):
    assert pay(client, other_user, booking["id"]).status_code == 404


def test_payment_requires_login(client, booking):
    r = client.post("/payments/", json={"booking_id": booking["id"]})
    assert r.status_code in (401, 403)


def test_webhook_confirms_failed_booking(client, user, booking):
    ref = pay(client, user, booking["id"], "FAILED").json()["provider_reference"]
    assert webhook(client, "evt_1", ref).json() == {"result": "processed"}
    assert status_of(client, user, booking["id"]) == "CONFIRMED"


def test_webhook_is_idempotent(client, user, booking):
    ref = pay(client, user, booking["id"], "FAILED").json()["provider_reference"]
    results = [webhook(client, "evt_1", ref).json()["result"] for _ in range(3)]
    assert results == ["processed", "duplicate_ignored", "duplicate_ignored"]
    assert row_count(WebhookEvent) == 1
    assert row_count(Payment) == 1
    assert status_of(client, user, booking["id"]) == "CONFIRMED"


def test_webhook_rejects_wrong_or_missing_secret(client, user, booking):
    ref = pay(client, user, booking["id"], "FAILED").json()["provider_reference"]
    assert webhook(client, "evt_1", ref, headers={"x-webhook-secret": "wrong"}).status_code == 401
    assert webhook(client, "evt_1", ref, headers={}).status_code == 401
    assert status_of(client, user, booking["id"]) == "FAILED"


def test_webhook_unknown_reference_returns_404(client):
    assert webhook(client, "evt_1", "mock_does_not_exist").status_code == 404


def test_webhook_invalid_body_returns_422(client):
    r = client.post("/payments/webhook/", json={"event_id": "evt_1"}, headers=SECRET)
    assert r.status_code == 422


def test_late_failed_webhook_cannot_undo_success(client, user, booking):
    ref = pay(client, user, booking["id"], "SUCCESS").json()["provider_reference"]
    webhook(client, "evt_9", ref, status="FAILED")
    assert status_of(client, user, booking["id"]) == "CONFIRMED"


def test_get_own_payment(client, user, booking):
    payment = pay(client, user, booking["id"], "SUCCESS").json()
    r = client.get(f"/payments/{payment['id']}", headers=user)
    assert r.status_code == 200
    assert r.json()["provider_reference"] == payment["provider_reference"]


def test_cannot_view_someone_elses_payment(client, user, booking, other_user):
    payment = pay(client, user, booking["id"], "SUCCESS").json()
    assert client.get(f"/payments/{payment['id']}", headers=other_user).status_code == 404


def test_unknown_payment_returns_404(client, user):
    assert client.get("/payments/99999", headers=user).status_code == 404


def test_get_own_payment(client, user, booking):
    payment = pay(client, user, booking["id"], "SUCCESS").json()
    r = client.get(f"/payments/{payment['id']}", headers=user)
    assert r.status_code == 200
    assert r.json()["provider_reference"] == payment["provider_reference"]


def test_cannot_view_someone_elses_payment(client, user, booking, other_user):
    payment = pay(client, user, booking["id"], "SUCCESS").json()
    assert client.get(f"/payments/{payment['id']}", headers=other_user).status_code == 404


def test_unknown_payment_returns_404(client, user):
    assert client.get("/payments/99999", headers=user).status_code == 404
