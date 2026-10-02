import hmac
import os
import random
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, Payment, PaymentStatus, User, WebhookEvent
from app.schemas import PaymentCreate, PaymentOut, WebhookIn, WebhookOut

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret")
PAYABLE = (BookingStatus.PENDING, BookingStatus.FAILED)  # FAILED allows a retry

router = APIRouter(prefix="/payments", tags=["payments"])


def to_out(payment: Payment, booking: Booking) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        booking_id=payment.booking_id,
        amount=payment.amount,
        status=payment.status,
        provider_reference=payment.provider_reference,
        booking_status=booking.status,
    )


@router.post("/", response_model=PaymentOut, status_code=201)
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Lock the booking row so two simultaneous clicks cannot both pay it.
    booking = db.scalar(select(Booking).where(Booking.id == data.booking_id).with_for_update())
    if not booking or booking.user_id != user.id:
        raise HTTPException(404, "Booking not found")
    if booking.status not in PAYABLE:
        raise HTTPException(409, f"Booking is {booking.status.value} and cannot be paid")

    outcome = data.simulate or random.choices(
        [PaymentStatus.SUCCESS, PaymentStatus.FAILED], weights=[7, 3]
    )[0]

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        status=outcome,
        provider_reference=f"mock_{uuid.uuid4().hex}",
    )
    db.add(payment)
    booking.status = (
        BookingStatus.CONFIRMED if outcome == PaymentStatus.SUCCESS else BookingStatus.FAILED
    )
    db.commit()
    db.refresh(payment)
    return to_out(payment, booking)


@router.post("/webhook/", response_model=WebhookOut)
def payment_webhook(
    data: WebhookIn,
    x_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # 1. Only the real provider knows the secret.
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, WEBHOOK_SECRET):
        raise HTTPException(401, "Invalid webhook secret")

    payment = db.scalar(select(Payment).where(Payment.provider_reference == data.provider_reference))
    if not payment:
        raise HTTPException(404, "Unknown payment reference")

    # 2. Record the event ID first. The unique rule on event_id means a
    #    second copy of the same event fails right here, and we skip it.
    db.add(WebhookEvent(event_id=data.event_id, payload=data.model_dump(mode="json")))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return WebhookOut(result="duplicate_ignored")

    # 3. Apply the result inside the same transaction as the event record.
    booking = db.scalar(select(Booking).where(Booking.id == payment.booking_id).with_for_update())
    if payment.status != PaymentStatus.SUCCESS:  # a successful payment is never downgraded
        payment.status = data.status
        if data.status == PaymentStatus.SUCCESS and booking.status in PAYABLE:
            booking.status = BookingStatus.CONFIRMED
        elif data.status == PaymentStatus.FAILED and booking.status == BookingStatus.PENDING:
            booking.status = BookingStatus.FAILED
        # a CANCELLED booking is never changed by a webhook

    db.commit()
    return WebhookOut(result="processed")