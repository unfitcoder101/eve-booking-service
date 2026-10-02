from fastapi import FastAPI

from app.routers import auth, bookings, centres, payments

app = FastAPI(title="EVE Booking Service")
app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)