from sqlalchemy import select

from app.database import SessionLocal
from app.models import Centre, CentreTest, Test

DATA = {
    ("City Diagnostics", "Jaipur"): {"Blood Sugar": 300, "Lipid Profile": 700, "Thyroid Panel": 650},
    ("HealthFirst Labs", "Jaipur"): {"Blood Sugar": 250, "CBC": 400},
    ("Metro Path Lab", "Delhi"): {"CBC": 450, "Vitamin D": 1200},
}


def run():
    db = SessionLocal()
    if db.scalar(select(Centre).limit(1)):
        print("Already seeded, skipping")
        return
    for (name, location), tests in DATA.items():
        centre = Centre(name=name, location=location)
        db.add(centre)
        db.flush()
        for test_name, price in tests.items():
            test = db.scalar(select(Test).where(Test.name == test_name))
            if not test:
                test = Test(name=test_name)
                db.add(test)
                db.flush()
            db.add(CentreTest(centre_id=centre.id, test_id=test.id, price=price))
    db.commit()
    print("Seeded")


if __name__ == "__main__":
    run()