from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


# ---- City ----

class CityIn(BaseModel):
    name: str

class CityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# ---- Stage Template ----

class StageTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    attributes_schema: dict = Field(default_factory=dict)

class StageTemplateIn(BaseModel):
    code: str
    name: str
    attributes_schema: dict = Field(default_factory=dict)


# ---- Performer ----

class PerformerStageIn(BaseModel):
    stage_template_id: int
    cost: float
    duration_hours: float

class PerformerStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stage_template_id: int
    cost: float
    duration_hours: float
    stage_template: StageTemplateOut

class PerformerIn(BaseModel):
    name: str
    city_id: int
    specialization: str = ""
    contact: str = ""
    active: bool = True
    workdays: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    skills: List[PerformerStageIn] = Field(default_factory=list)

class PerformerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    city_id: int
    city: CityOut
    specialization: str
    contact: str
    active: bool
    workdays: List[int]
    skills: List[PerformerStageOut]


# ---- Route ----

class RouteIn(BaseModel):
    origin_id: int
    destination_id: int
    mode: str
    cost: float
    duration_hours: float
    handover_hours: float = 1.0
    pickup_hours: float = 1.0

class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    origin_id: int
    destination_id: int
    origin: CityOut
    destination: CityOut
    mode: str
    cost: float
    duration_hours: float
    handover_hours: float
    pickup_hours: float


# ---- Order / Stage ----

class StageCandidateIn(BaseModel):
    performer_id: int

class StageCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    performer_id: int
    performer: PerformerOut

class StageIn(BaseModel):
    stage_template_id: int
    order_index: int
    name: str
    attributes: dict = Field(default_factory=dict)
    candidate_performer_ids: List[int] = Field(default_factory=list)

class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stage_template_id: int
    template: StageTemplateOut
    order_index: int
    name: str
    attributes: dict
    status: str
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    actual_performer_id: Optional[int]
    candidates: List[StageCandidateOut]

class OrderIn(BaseModel):
    name: str
    description: str = ""
    customer: str = ""
    deadline: date
    material: str = ""
    weight_g: float = 0.0
    start_city_id: Optional[int] = None
    stages: List[StageIn] = Field(default_factory=list)

class OrderShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    customer: str
    deadline: date
    status: str
    estimated_cost: float
    actual_cost: float

class OrderOut(OrderShort):
    description: str
    material: str
    weight_g: float
    created_at: datetime
    start_city_id: Optional[int]
    start_city: Optional[CityOut]
    stages: List[StageOut]


# ---- Plan ----

class PlanStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stage_id: int
    performer_id: int
    start_at: datetime
    end_at: datetime
    cost: float
    performer: PerformerOut
    stage: StageOut

class PlanMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    route_id: int
    from_stage_id: Optional[int]
    to_stage_id: Optional[int]
    start_at: datetime
    end_at: datetime
    cost: float
    courier_index: Optional[int]
    route: RouteOut

class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    created_at: datetime
    total_cost: float
    production_cost: float
    logistics_cost: float
    completion_date: Optional[date]
    feasible: bool
    is_active: bool
    explanation: dict
    plan_stages: List[PlanStageOut]
    movements: List[PlanMovementOut]


# ---- Optimization ----

class OptimizeResult(BaseModel):
    """Результат оценки/планирования заказа."""
    feasible: bool
    completion_date: Optional[date]
    total_cost: float
    production_cost: float
    logistics_cost: float
    explanation: dict
    plan_id: Optional[int] = None
    message: str = ""


# ---- History ----

class OrderHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    event_type: str
    payload: dict
    note: str


# ---- Dashboard ----

class DashboardOut(BaseModel):
    active_orders: int
    done_orders: int
    at_risk_orders: int
    overdue_orders: int
    couriers_total: int
    couriers_load_pct: float
    performers_active: int
    total_production_cost: float
    total_logistics_cost: float
    savings_vs_naive_pct: Optional[float] = None


# ---- Stage status update ----

class StageStatusUpdate(BaseModel):
    status: str
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    actual_performer_id: Optional[int] = None
