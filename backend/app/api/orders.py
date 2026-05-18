from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

from app.db import get_db
from app.core.config import settings
from app.models import (
    Order, Stage, StageCandidate, Plan, PlanStage, PlanMovement, OrderHistory, Performer
)
from app.schemas.schemas import (
    OrderIn, OrderOut, OrderShort,
    PlanOut, OptimizeResult,
    OrderHistoryOut, DashboardOut, StageStatusUpdate,
)
from app.services.planning import PlanningService

router = APIRouter()


def _load_order(db: Session, order_id: int) -> Order:
    o = (
        db.query(Order)
        .options(
            selectinload(Order.stages).selectinload(Stage.template),
            selectinload(Order.stages).selectinload(Stage.candidates).selectinload(StageCandidate.performer),
            selectinload(Order.start_city),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not o:
        raise HTTPException(404, "Order not found")
    return o


@router.get("/orders", response_model=List[OrderShort])
def list_orders(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Order).order_by(Order.created_at.desc())
    if status:
        q = q.filter(Order.status == status)
    return q.all()


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    return _load_order(db, order_id)


@router.post("/orders", response_model=OrderOut)
def create_order(payload: OrderIn, db: Session = Depends(get_db)):
    o = Order(
        name=payload.name,
        description=payload.description,
        customer=payload.customer,
        deadline=payload.deadline,
        material=payload.material,
        weight_g=payload.weight_g,
        start_city_id=payload.start_city_id,
        status="draft",
    )
    db.add(o); db.flush()
    for st in payload.stages:
        s = Stage(
            order_id=o.id,
            stage_template_id=st.stage_template_id,
            order_index=st.order_index,
            name=st.name,
            attributes=st.attributes,
            status="pending",
        )
        db.add(s); db.flush()
        for pid in st.candidate_performer_ids:
            db.add(StageCandidate(stage_id=s.id, performer_id=pid))
    db.add(OrderHistory(order_id=o.id, event_type="created", payload={}))
    db.commit()
    return _load_order(db, o.id)


@router.put("/orders/{order_id}", response_model=OrderOut)
def update_order(order_id: int, payload: OrderIn, db: Session = Depends(get_db)):
    o = _load_order(db, order_id)
    if o.status not in ("draft", "estimated"):
        raise HTTPException(400, "Можно редактировать только заказ в статусе draft или estimated")
    o.name = payload.name
    o.description = payload.description
    o.customer = payload.customer
    o.deadline = payload.deadline
    o.material = payload.material
    o.weight_g = payload.weight_g
    o.start_city_id = payload.start_city_id
    # Перезалить этапы целиком
    for s in list(o.stages):
        db.delete(s)
    db.flush()
    for st in payload.stages:
        s = Stage(
            order_id=o.id,
            stage_template_id=st.stage_template_id,
            order_index=st.order_index,
            name=st.name,
            attributes=st.attributes,
            status="pending",
        )
        db.add(s); db.flush()
        for pid in st.candidate_performer_ids:
            db.add(StageCandidate(stage_id=s.id, performer_id=pid))
    db.add(OrderHistory(order_id=o.id, event_type="updated", payload={}))
    db.commit()
    return _load_order(db, o.id)


@router.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    o = _load_order(db, order_id)
    if o.status in ("in_production", "at_risk"):
        raise HTTPException(400, "Нельзя удалить заказ в работе")
    db.delete(o); db.commit()
    return {"ok": True}


@router.post("/orders/{order_id}/estimate", response_model=OptimizeResult)
def estimate_order(order_id: int, persist: bool = False, db: Session = Depends(get_db)):
    o = _load_order(db, order_id)
    if not o.stages:
        raise HTTPException(400, "У заказа нет этапов")
    service = PlanningService(db)
    res = service.estimate(o.id, persist=persist)
    if o.id not in res.per_order:
        return OptimizeResult(
            feasible=False, completion_date=None,
            total_cost=0, production_cost=0, logistics_cost=0,
            explanation={}, message=res.message or "Не удалось построить план",
        )
    target = res.per_order[o.id]
    # Сохраним оценочную стоимость в самом заказе
    o.estimated_cost = target.total_cost
    if o.status == "draft":
        o.status = "estimated"
    db.add(OrderHistory(order_id=o.id, event_type="estimated",
                        payload={"feasible": target.feasible,
                                 "total_cost": target.total_cost,
                                 "completion_date": str(target.completion_date) if target.completion_date else None}))
    db.commit()
    # Если в estimate был persist=True, последний план — то, что нам нужно
    plan_id = None
    if persist:
        last_plan = db.query(Plan).filter(Plan.order_id == o.id).order_by(Plan.id.desc()).first()
        plan_id = last_plan.id if last_plan else None
    return OptimizeResult(
        feasible=target.feasible,
        completion_date=target.completion_date,
        total_cost=target.total_cost,
        production_cost=target.production_cost,
        logistics_cost=target.logistics_cost,
        explanation=target.explanation,
        plan_id=plan_id,
        message=res.message or ("OK" if target.feasible else "Срок невыполним"),
    )


@router.post("/orders/{order_id}/confirm", response_model=OrderOut)
def confirm_order(order_id: int, db: Session = Depends(get_db)):
    """Подтвердить заказ: перевести в confirmed и запустить общий пересчёт."""
    o = _load_order(db, order_id)
    if o.status not in ("estimated", "draft"):
        raise HTTPException(400, "Заказ уже подтверждён или в работе")
    o.status = "confirmed"
    db.add(OrderHistory(order_id=o.id, event_type="confirmed", payload={}))
    db.commit()
    # Сразу пересчёт активного плана
    PlanningService(db).replan_active()
    return _load_order(db, o.id)


@router.post("/orders/{order_id}/start", response_model=OrderOut)
def start_order(order_id: int, db: Session = Depends(get_db)):
    """Запустить заказ в производство."""
    o = _load_order(db, order_id)
    if o.status not in ("confirmed", "estimated"):
        raise HTTPException(400, "Заказ должен быть подтверждён, чтобы запустить его")
    o.status = "in_production"
    db.add(OrderHistory(order_id=o.id, event_type="started", payload={}))
    db.commit()
    PlanningService(db).replan_active()
    return _load_order(db, o.id)


@router.post("/orders/{order_id}/replan")
def replan_order(order_id: int, db: Session = Depends(get_db)):
    """Пересчитать план по всем активным заказам (включая указанный)."""
    _ = _load_order(db, order_id)
    res = PlanningService(db).replan_active()
    return {"status": res.status, "message": res.message,
            "orders_planned": list(res.per_order.keys())}


@router.post("/replan")
def replan_all(db: Session = Depends(get_db)):
    res = PlanningService(db).replan_active()
    return {"status": res.status, "message": res.message,
            "orders_planned": list(res.per_order.keys())}


# ---- Stage execution tracking ----

@router.patch("/stages/{stage_id}/status", response_model=OrderOut)
def update_stage_status(stage_id: int, payload: StageStatusUpdate, db: Session = Depends(get_db)):
    s = db.query(Stage).filter(Stage.id == stage_id).first()
    if not s:
        raise HTTPException(404, "Stage not found")
    s.status = payload.status
    if payload.actual_start:
        s.actual_start = payload.actual_start
    if payload.actual_end:
        s.actual_end = payload.actual_end
    if payload.actual_performer_id:
        s.actual_performer_id = payload.actual_performer_id
    # Если все этапы заказа done — закрываем заказ
    order = db.query(Order).filter(Order.id == s.order_id).first()
    if order and all(st.status == "done" for st in order.stages):
        order.status = "done"
        # Зафиксируем фактическую стоимость как сумму план-стейджей активного плана
        plan = db.query(Plan).filter(Plan.order_id == order.id, Plan.is_active == True).first()
        if plan:
            order.actual_cost = plan.total_cost
        db.add(OrderHistory(order_id=order.id, event_type="completed", payload={}))
    db.add(OrderHistory(order_id=s.order_id, event_type="stage_status",
                        payload={"stage_id": s.id, "status": s.status}))
    db.commit()
    return _load_order(db, s.order_id)


# ---- Plans ----

@router.get("/orders/{order_id}/plans", response_model=List[PlanOut])
def list_plans(order_id: int, db: Session = Depends(get_db)):
    plans = (
        db.query(Plan)
        .options(
            selectinload(Plan.plan_stages).selectinload(PlanStage.performer),
            selectinload(Plan.plan_stages).selectinload(PlanStage.stage).selectinload(Stage.template),
            selectinload(Plan.plan_stages).selectinload(PlanStage.stage).selectinload(Stage.candidates).selectinload(StageCandidate.performer),
            selectinload(Plan.movements).selectinload(PlanMovement.route),
        )
        .filter(Plan.order_id == order_id)
        .order_by(Plan.created_at.desc())
        .all()
    )
    return plans


@router.get("/orders/{order_id}/plans/active", response_model=Optional[PlanOut])
def get_active_plan(order_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Plan)
        .options(
            selectinload(Plan.plan_stages).selectinload(PlanStage.performer),
            selectinload(Plan.plan_stages).selectinload(PlanStage.stage).selectinload(Stage.template),
            selectinload(Plan.plan_stages).selectinload(PlanStage.stage).selectinload(Stage.candidates).selectinload(StageCandidate.performer),
            selectinload(Plan.movements).selectinload(PlanMovement.route),
        )
        .filter(Plan.order_id == order_id, Plan.is_active == True)
        .first()
    )


# ---- History ----

@router.get("/orders/{order_id}/history", response_model=List[OrderHistoryOut])
def order_history(order_id: int, db: Session = Depends(get_db)):
    return (
        db.query(OrderHistory)
        .filter(OrderHistory.order_id == order_id)
        .order_by(OrderHistory.created_at.desc())
        .all()
    )


# ---- Dashboard ----

@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    active = db.query(Order).filter(Order.status.in_(("confirmed", "in_production", "at_risk"))).count()
    done = db.query(Order).filter(Order.status == "done").count()
    at_risk = db.query(Order).filter(Order.status == "at_risk").count()
    overdue = db.query(Order).filter(Order.status == "overdue").count()
    performers_active = db.query(Performer).filter(Performer.active == True).count()

    # Загрузка курьеров: считаем суммарно (часы перевозок) / (горизонт * курьеры)
    plans = db.query(Plan).filter(Plan.is_active == True).all()
    total_prod = sum(p.production_cost for p in plans)
    total_log = sum(p.logistics_cost for p in plans)

    # Расчёт экономии относительно «наивного» варианта
    service = PlanningService(db)
    naive_sum = 0.0
    saved_known = True
    for p in plans:
        n = service.naive_cost(p.order_id)
        if n is None:
            saved_known = False
            break
        naive_sum += n
    savings_pct = None
    if saved_known and naive_sum > 0:
        savings_pct = round(100.0 * (naive_sum - (total_prod + total_log)) / naive_sum, 1)

    # Загрузка курьеров — упрощённо: количество движений в активных планах / лимит
    movements_count = sum(len(p.movements) for p in plans)
    capacity = max(1, settings.COURIERS_TOTAL) * max(1, active)
    load_pct = round(100.0 * min(1.0, movements_count / capacity), 1)

    return DashboardOut(
        active_orders=active,
        done_orders=done,
        at_risk_orders=at_risk,
        overdue_orders=overdue,
        couriers_total=settings.COURIERS_TOTAL,
        couriers_load_pct=load_pct,
        performers_active=performers_active,
        total_production_cost=total_prod,
        total_logistics_cost=total_log,
        savings_vs_naive_pct=savings_pct,
    )
