def test_booking_uses_centre_price(client, user, offering, future_date):
    r = client.post("/bookings", json={**offering, "appointment_at": future_date}, headers=user)
    assert r.status_code == 201
    assert r.json()["status"] == "PENDING"
    assert r.json()["amount"] == 300


def test_past_appointment_rejected(client, user, offering):
    body = {**offering, "appointment_at": "2020-01-01T10:00:00+00:00"}
    assert client.post("/bookings", json=body, headers=user).status_code == 422


def test_test_not_offered_returns_404(client, user, offering, future_date):
    body = {"centre_id": offering["centre_id"], "test_id": 9999, "appointment_at": future_date}
    assert client.post("/bookings", json=body, headers=user).status_code == 404


def test_booking_requires_login(client, offering, future_date):
    r = client.post("/bookings", json={**offering, "appointment_at": future_date})
    assert r.status_code in (401, 403)


def test_other_users_booking_is_hidden(client, booking, other_user):
    assert client.get(f"/bookings/{booking['id']}", headers=other_user).status_code == 404
    assert client.post(f"/bookings/{booking['id']}/cancel", headers=other_user).status_code == 404


def test_unknown_booking_returns_404(client, user):
    assert client.get("/bookings/99999", headers=user).status_code == 404


def test_cancel_twice_returns_409(client, user, booking):
    assert client.post(f"/bookings/{booking['id']}/cancel", headers=user).status_code == 200
    assert client.post(f"/bookings/{booking['id']}/cancel", headers=user).status_code == 409