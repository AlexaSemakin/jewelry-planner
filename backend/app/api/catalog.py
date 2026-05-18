from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db import get_db
from app.models import City, StageTemplate, Performer, PerformerStage, Route
from app.schemas.schemas import (
    CityIn, CityOut,
    StageTemplateIn, StageTemplateOut,
    PerformerIn, PerformerOut, PerformerStageIn,
    RouteIn, RouteOut,
)

router = APIRouter()


# ---- Cities ----

@router.get("/cities", response_model=List[CityOut])
def list_cities(db: Session = Depends(get_db)):
    return db.query(City).order_by(City.name).all()


@router.post("/cities", response_model=CityOut)
def create_city(payload: CityIn, db: Session = Depends(get_db)):
    if db.query(City).filter(City.name == payload.name).first():
        raise HTTPException(409, "City with this name already exists")
    c = City(name=payload.name)
    db.add(c); db.commit(); db.refresh(c)
    return c


@router.delete("/cities/{city_id}")
def delete_city(city_id: int, db: Session = Depends(get_db)):
    c = db.query(City).filter(City.id == city_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    db.delete(c); db.commit()
    return {"ok": True}


# ---- Stage templates ----

@router.get("/stage-templates", response_model=List[StageTemplateOut])
def list_stage_templates(db: Session = Depends(get_db)):
    return db.query(StageTemplate).order_by(StageTemplate.name).all()


@router.post("/stage-templates", response_model=StageTemplateOut)
def create_stage_template(payload: StageTemplateIn, db: Session = Depends(get_db)):
    if db.query(StageTemplate).filter(StageTemplate.code == payload.code).first():
        raise HTTPException(409, "Template code already exists")
    t = StageTemplate(**payload.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    return t


# ---- Performers ----

@router.get("/performers", response_model=List[PerformerOut])
def list_performers(db: Session = Depends(get_db)):
    return db.query(Performer).order_by(Performer.name).all()


@router.get("/performers/{performer_id}", response_model=PerformerOut)
def get_performer(performer_id: int, db: Session = Depends(get_db)):
    p = db.query(Performer).filter(Performer.id == performer_id).first()
    if not p:
        raise HTTPException(404, "Not found")
    return p


@router.post("/performers", response_model=PerformerOut)
def create_performer(payload: PerformerIn, db: Session = Depends(get_db)):
    p = Performer(
        name=payload.name,
        city_id=payload.city_id,
        specialization=payload.specialization,
        contact=payload.contact,
        active=payload.active,
        workdays=payload.workdays,
    )
    db.add(p); db.flush()
    for skill in payload.skills:
        db.add(PerformerStage(
            performer_id=p.id,
            stage_template_id=skill.stage_template_id,
            cost=skill.cost,
            duration_hours=skill.duration_hours,
        ))
    db.commit(); db.refresh(p)
    return p


@router.put("/performers/{performer_id}", response_model=PerformerOut)
def update_performer(performer_id: int, payload: PerformerIn, db: Session = Depends(get_db)):
    p = db.query(Performer).filter(Performer.id == performer_id).first()
    if not p:
        raise HTTPException(404, "Not found")
    p.name = payload.name
    p.city_id = payload.city_id
    p.specialization = payload.specialization
    p.contact = payload.contact
    p.active = payload.active
    p.workdays = payload.workdays
    # Заменим скиллы целиком
    for s in list(p.skills):
        db.delete(s)
    db.flush()
    for skill in payload.skills:
        db.add(PerformerStage(
            performer_id=p.id,
            stage_template_id=skill.stage_template_id,
            cost=skill.cost,
            duration_hours=skill.duration_hours,
        ))
    db.commit(); db.refresh(p)
    return p


@router.delete("/performers/{performer_id}")
def delete_performer(performer_id: int, db: Session = Depends(get_db)):
    p = db.query(Performer).filter(Performer.id == performer_id).first()
    if not p:
        raise HTTPException(404, "Not found")
    db.delete(p); db.commit()
    return {"ok": True}


# ---- Routes ----

@router.get("/routes", response_model=List[RouteOut])
def list_routes(db: Session = Depends(get_db)):
    return db.query(Route).all()


@router.post("/routes", response_model=RouteOut)
def create_route(payload: RouteIn, db: Session = Depends(get_db)):
    r = Route(**payload.model_dump())
    db.add(r); db.commit(); db.refresh(r)
    return r


@router.delete("/routes/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db)):
    r = db.query(Route).filter(Route.id == route_id).first()
    if not r:
        raise HTTPException(404, "Not found")
    db.delete(r); db.commit()
    return {"ok": True}
