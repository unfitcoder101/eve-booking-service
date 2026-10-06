import os

# Must be set BEFORE app.database is imported, so tests never touch the dev database.
os.environ["DATABASE_URL"] = "postgresql+psycopg2://localhost/eve_booking_test"

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import models  # noqa: F401  (registers the tables)
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Centre, CentreTest, Test


@pytest.fixture(autouse=True)
def fresh_tables():                  
    assert "test" in str(engine.url), "Refusing to wipe a non-test database"               
    Base.metadata.drop_all(engine)                         
    Base.metadata.create_all(engine)                  


@pytest.fixture
def client():                             
    return TestClient(app)                              


@pytest.fixture
def future_date():                                 
    return (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()                             


def make_user(client, email):                                       
    client.post("/auth/signup", json={"email": email, "password": "Password123", "full_name": "T"})                       
    res = client.post("/auth/login", json={"email": email, "password": "Password123"})                     
    return {"Authorization": f"Bearer {res.json()['access_token']}"}                   


@pytest.fixture
def user(client):
    return make_user(client, "a@example.com")                            


@pytest.fixture
def other_user(client):                        
    return make_user(client, "b@example.com")                           


@pytest.fixture                   
def offering():                                  
    """One centre offering one test at price 300."""                            
    db = SessionLocal()                                  
    centre = Centre(name="Test Lab", location="Jaipur")                     
    test = Test(name="Blood Sugar")
    db.add_all([centre, test])                       
    db.flush()                           
    db.add(CentreTest(centre_id=centre.id, test_id=test.id, price=300))                 
    db.commit()                                  
    ids = {"centre_id": centre.id, "test_id": test.id}
    db.close()
    return ids


@pytest.fixture
def booking(client, user, offering, future_date):
    body = {**offering, "appointment_at": future_date}
    return client.post("/bookings", json=body, headers=user).json()
