"""
PlanningService — высокоуровневое API над оптимизатором.

Использование:
  - estimate(order_id): только оценка, ничего не сохраняем (или сохраняем как неактивный план)
  - replan_active(): пересчитывает план для всех активных заказов и сохраняет
  - lock_plan(order_id, plan_id): фиксирует план, переводит заказ в работу
"""
from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Order, Plan, PlanStage, PlanMovement, OrderHistory,
)
from app.optimizer.solver import JewelryScheduler, SolveResult, OrderResult
from app.optimizer.timeline import from_steps


ACTIVE_STATUSES = ("confirmed", "in_production", "at_risk", "estimated")


class PlanningService:
    def __init__(self, db: Session, couriers_total: Optional[int] = None):
        self.db = db
        self.couriers_total = couriers_total or settings.COURIERS_TOTAL

    # ---------- Помощники ----------

    def _load_other_active_orders(self, exclude_order_id: Optional[int]) -> List[Order]:
        q = self.db.query(Order).filter(Order.status.in_(ACTIVE_STATUSES))
        if exclude_order_id is not None:
            q = q.filter(Order.id != exclude_order_id)
        return q.all()

    def _deactivate_plans(self, order_id: int) -> None:
        self.db.query(Plan).filter(Plan.order_id == order_id).update({"is_active": False})

    def _save_plan(self, order_id: int, order_res: OrderResult, set_active: bool) -> Plan:
        plan = Plan(
            order_id=order_id,
            total_cost=order_res.total_cost,
            production_cost=order_res.production_cost,
            logistics_cost=order_res.logistics_cost,
            completion_date=order_res.completion_date,
            feasible=order_res.feasible,
            explanation=order_res.explanation,
            is_active=set_active,
        )
        self.db.add(plan)
        self.db.flush()
        for s in order_res.stage_assignments:
            if s.start_step is None or s.end_step is None or s.chosen_performer_id is None:
                continue
            ps = PlanStage(
                plan_id=plan.id,
                stage_id=s.stage_id,
                performer_id=s.chosen_performer_id,
                start_at=from_steps(s.start_step),
                end_at=from_steps(s.end_step),
                cost=s.chosen_cost,
            )
            self.db.add(ps)
        # Курьеры в плане: упрощённо — округлим по номеру в порядке начала.
        # CP-SAT гарантирует одновременную загрузку ≤ COURIERS_TOTAL.
        movements_sorted = sorted(
            [m for m in order_res.movements if m.route_id is not None and m.start_step is not None],
            key=lambda m: m.start_step,
        )
        for i, m in enumerate(movements_sorted):
            pm = PlanMovement(
                plan_id=plan.id,
                route_id=m.route_id,
                from_stage_id=m.from_stage_id,
                to_stage_id=m.to_stage_id,
                start_at=from_steps(m.start_step),
                end_at=from_steps(m.end_step),
                cost=m.cost,
                courier_index=(i % self.couriers_total) + 1,
            )
            self.db.add(pm)
        return plan

    def _stage_id_at_index(self, *_args, **_kw):
        # Legacy helper, теперь не используется.
        return None

    # ---------- Публичные методы ----------

    def estimate(self, order_id: int, persist: bool = False) -> SolveResult:
        """
        Оценка заказа: пробуем уложиться в дедлайн (hard). Если не получилось —
        повторяем в soft-режиме, чтобы показать минимально возможный срок.
        """
        order = self.db.query(Order).filter(Order.id == order_id).one()
        others = self._load_other_active_orders(exclude_order_id=order.id)
        orders = [order] + others

        scheduler = JewelryScheduler(self.db, orders, self.couriers_total)
        result = scheduler.solve(soft_deadline=False)
        if not result.per_order or order.id not in result.per_order or not result.per_order[order.id].feasible:
            # Пробуем soft-режим — найти минимально возможный срок
            sched2 = JewelryScheduler(self.db, orders, self.couriers_total)
            result_soft = sched2.solve(soft_deadline=True)
            # Возьмём из soft-результата только нужное
            if order.id in result_soft.per_order:
                target = result_soft.per_order[order.id]
                if persist:
                    self._save_plan(order.id, target, set_active=False)
                    self.db.commit()
                # Прокидываем как infeasible
                result_soft.message = (
                    "Уложиться в срок невозможно. Минимально возможный срок выполнения: "
                    f"{target.completion_date}"
                )
                return result_soft
            return result

        if persist and order.id in result.per_order:
            self._save_plan(order.id, result.per_order[order.id], set_active=False)
            self.db.commit()
        return result

    def replan_active(self) -> SolveResult:
        """Пересчёт плана по всем активным заказам, сохраняем активный план."""
        orders = self.db.query(Order).filter(Order.status.in_(ACTIVE_STATUSES)).all()
        if not orders:
            return SolveResult(status="OPTIMAL", objective=0.0, per_order={}, message="Нет активных заказов")
        scheduler = JewelryScheduler(self.db, orders, self.couriers_total)
        result = scheduler.solve(soft_deadline=False)
        if not result.per_order:
            # soft fallback
            sched2 = JewelryScheduler(self.db, orders, self.couriers_total)
            result = sched2.solve(soft_deadline=True)

        if result.per_order:
            for order in orders:
                if order.id in result.per_order:
                    self._deactivate_plans(order.id)
                    plan = self._save_plan(order.id, result.per_order[order.id], set_active=True)
                    if not result.per_order[order.id].feasible:
                        order.status = "at_risk"
                    elif order.status in ("estimated", "confirmed", "at_risk"):
                        # сохраняем статус как есть; запуск в работу — отдельным действием
                        pass
                    self.db.add(OrderHistory(
                        order_id=order.id,
                        event_type="plan_recalculated",
                        payload={"plan_id": plan.id, "feasible": plan.feasible,
                                 "total_cost": plan.total_cost},
                    ))
            self.db.commit()
        return result

    def naive_cost(self, order_id: int) -> Optional[float]:
        """
        Грубая «неоптимизированная» стоимость для оценки экономии:
        для каждого этапа берём САМОГО дорогого исполнителя,
        и для каждого перемещения — самый дорогой маршрут.
        Это верхняя граница, она и используется как ориентир «без оптимизации».
        """
        order = self.db.query(Order).filter(Order.id == order_id).one()
        from app.services.transport import TransportAdapter
        total = 0.0
        prev_city: Optional[int] = order.start_city_id
        for stage in sorted(order.stages, key=lambda s: s.order_index):
            costs = []
            cities = []
            for cand in stage.candidates:
                p = cand.performer
                for skill in p.skills:
                    if skill.stage_template_id == stage.stage_template_id:
                        costs.append(skill.cost)
                        cities.append(p.city_id)
            if not costs:
                return None
            total += max(costs)
            chosen_city = cities[costs.index(max(costs))]
            if prev_city is not None and prev_city != chosen_city:
                opts = TransportAdapter.options(self.db, prev_city, chosen_city)
                if opts:
                    total += max(o.cost for o in opts)
            prev_city = chosen_city
        return total
