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