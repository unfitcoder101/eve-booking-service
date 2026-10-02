from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models import Centre, CentreTest, Test, User
from app.schemas import CentreCreate, CentreOut, OfferingCreate, OfferingOut

router = APIRouter(prefix="/centres", tags=["centres"])


def to_out(c: Centre) -> CentreOut:
    return CentreOut(
        id=c.id,
        name=c.name,
        location=c.location,
        tests=[
            OfferingOut(id=o.id, test_id=o.test_id, test_name=o.test.name, price=o.price)
            for o in c.offerings
        ],
    )


def load_options():
    return selectinload(Centre.offerings).selectinload(CentreTest.test)


@router.get("", response_model=list[CentreOut])
def list_centres(
    location: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Centre).options(load_options()).order_by(Centre.id).offset(skip).limit(limit)
    if location:
        query = query.where(Centre.location.ilike(f"%{location}%"))
    return [to_out(c) for c in db.scalars(query)]


@router.get("/{centre_id}", response_model=CentreOut)
def get_centre(centre_id: int, db: Session = Depends(get_db)):
    centre = db.scalar(select(Centre).options(load_options()).where(Centre.id == centre_id))
    if not centre:
        raise HTTPException(404, "Centre not found")
    return to_out(centre)


@router.post("", response_model=CentreOut, status_code=201)
def create_centre(
    data: CentreCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    centre = Centre(name=data.name, location=data.location)
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return to_out(centre)


@router.post("/{centre_id}/tests", response_model=OfferingOut, status_code=201)
def add_test_to_centre(
    centre_id: int,
    data: OfferingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    centre = db.get(Centre, centre_id)
    if not centre:
        raise HTTPException(404, "Centre not found")

    test = db.scalar(select(Test).where(Test.name == data.test_name))
    if not test:
        test = Test(name=data.test_name)
        db.add(test)
        db.flush()

    exists = db.scalar(
        select(CentreTest).where(CentreTest.centre_id == centre_id, CentreTest.test_id == test.id)
    )
    if exists:
        raise HTTPException(409, "This centre already offers that test")

    offering = CentreTest(centre_id=centre_id, test_id=test.id, price=data.price)
    db.add(offering)
    db.commit()
    db.refresh(offering)
    return OfferingOut(id=offering.id, test_id=test.id, test_name=test.name, price=offering.price)