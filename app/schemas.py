from datetime import datetime

from app.models import BookingStatus, PaymentStatus

from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    full_name: str = Field(min_length=1, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    model_config = {"from_attributes": True}

class OfferingCreate(BaseModel):
    test_name: str = Field(min_length=1, max_length=150)
    price: float = Field(gt=0)


class OfferingOut(BaseModel):
    id: int
    test_id: int
    test_name: str
    price: float


class CentreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    location: str = Field(min_length=1, max_length=150)


class CentreOut(BaseModel):
    id: int
    name: str
    location: str
    tests: list[OfferingOut]

class BookingCreate(BaseModel):
    centre_id: int
    test_id: int
    appointment_at: datetime


class BookingOut(BaseModel):
    id: int
    centre_id: int
    centre_name: str
    test_id: int
    test_name: str
    appointment_at: datetime
    amount: float
    status: BookingStatus
    created_at: datetime

class PaymentCreate(BaseModel):
    booking_id: int
    simulate: PaymentStatus | None = None  # optional: force an outcome (for testing)


class PaymentOut(BaseModel):
    id: int
    booking_id: int
    amount: float
    status: PaymentStatus
    provider_reference: str
    booking_status: BookingStatus


class WebhookIn(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    provider_reference: str = Field(min_length=1, max_length=100)
    status: PaymentStatus


class WebhookOut(BaseModel):
    result: str