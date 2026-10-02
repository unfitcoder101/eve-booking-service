from fastapi import FastAPI

from app.routers import auth, centres

app = FastAPI(title="EVE Booking Service")
app.include_router(auth.router)
app.include_router(centres.router)