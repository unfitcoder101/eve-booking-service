from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, CentreTest, User
from app.schemas import BookingCreate, BookingOut

router = APIRouter(prefix="/bookings", tags=["bookings"])


def to_out(b: Booking) -> BookingOut:
    ct = b.centre_test
    return BookingOut(
        id=b.id,
        centre_id=ct.centre_id,
        centre_name=ct.centre.name,
        test_id=ct.test_id,
        test_name=ct.test.name,
        appointment_at=b.appointment_at,
        amount=b.amount,
        status=b.status,
        created_at=b.created_at,
    )


def get_owned_booking(db: Session, booking_id: int, user: User) -> Booking:
    booking = db.get(Booking, booking_id)
    # Same 404 whether it doesn't exist or belongs to someone else,
    # so nobody can discover other people's booking IDs.
    if not booking or booking.user_id != user.id:
        raise HTTPException(404, "Booking not found")
    return booking


@router.post("", response_model=BookingOut, status_code=201)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    appointment = data.appointment_at
    if appointment.tzinfo is None:
        appointment = appointment.replace(tzinfo=timezone.utc)
    if appointment <= datetime.now(timezone.utc):
        raise HTTPException(422, "Appointment must be in the future")

    offering = db.scalar(
        select(CentreTest).where(
            CentreTest.centre_id == data.centre_id, CentreTest.test_id == data.test_id
        )
    )
    if not offering:
        raise HTTPException(404, "This centre does not offer that test")

    booking = Booking(
        user_id=user.id,
        centre_test_id=offering.id,
        appointment_at=appointment,
        amount=offering.price,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return to_out(booking)


@router.get("", response_model=list[BookingOut])
def list_my_bookings(
    status: BookingStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Booking).where(Booking.user_id == user.id)
    if status:
        query = query.where(Booking.status == status)
    query = query.order_by(Booking.id.desc()).offset(skip).limit(limit)
    return [to_out(b) for b in db.scalars(query)]


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return to_out(get_owned_booking(db, booking_id, user))


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = get_owned_booking(db, booking_id, user)
    if booking.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
        raise HTTPException(409, f"Cannot cancel a booking that is {booking.status.value}")
    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    return to_out(booking)