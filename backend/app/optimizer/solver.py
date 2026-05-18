"""
Оптимизационный модуль (п.8 ТЗ).

Модель: расширенный RCPSP с альтернативными ресурсами и логистикой.

Переменные:
  - x[s,p] ∈ {0,1} — выбран ли исполнитель p для этапа s (ровно один на этап).
  - opt_interval[s,p] — опциональный интервал выполнения этапа s исполнителем p
    (присутствует ⇔ x[s,p] = 1). Длительность зависит от p.
  - main_interval[s] — итоговый интервал этапа s (start/end синхронизированы
    с активным opt_interval).
  - y[(s_prev, s_next), r] ∈ {0,1} — выбран ли маршрут r для перевозки между
    двумя последовательными этапами (если города исполнителей различаются).
  - opt_move_interval[...]  — опциональные интервалы перевозок.

Ограничения:
  1. Каждый этап имеет ровно одного исполнителя (sum x[s,*] = 1).
  2. Прецедентность: end(stage_i) + ([handover/pickup] если есть перевозка)
     ≤ start(stage_{i+1}).
  3. NoOverlap на каждом исполнителе (он делает одно изделие за раз).
  4. Cumulative по курьерам: одновременно не больше COURIERS_TOTAL перевозок.
  5. Календари: forbidden ranges на интервалах исполнителей.
  6. Дедлайн: end(последний этап) ≤ deadline_in_steps. Если нарушение —
     попадает в soft-режим и решение помечается infeasible.

Цель:
  Минимизировать суммарную стоимость = производство + логистика.
  Если уложиться в срок невозможно — режим 2: минимизировать просрочку,
  отчёт пользователю в виде «минимальный срок и причина».

Объяснимость:
  Для каждого этапа собираем альтернативы (исполнители + стоимости + сроки),
  помечаем выбранного и сохраняем в plan.explanation.

Многозаказное планирование:
  В одну модель помещаются все активные заказы. Их этапы и перевозки делят
  один пул исполнителей и один пул курьеров.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Order, Stage, Performer, PerformerStage, Route, City, Plan, PlanStage, PlanMovement,
)
from app.services.transport import TransportAdapter, TransportOption
from app.optimizer.timeline import (
    horizon_start, hours_to_steps, to_steps, from_steps,
    total_horizon_steps, offwork_intervals,
)


# ---------- Внутренние структуры ----------

@dataclass
class CandidateInfo:
    performer_id: int
    city_id: int
    cost: float
    duration_hours: float
    duration_steps: int
    workdays: List[int]


@dataclass
class StageInfo:
    stage_id: int
    order_id: int
    order_index: int
    name: str
    candidates: List[CandidateInfo]   # все возможные исполнители
    # Заполняется решателем:
    chosen_performer_id: Optional[int] = None
    start_step: Optional[int] = None
    end_step: Optional[int] = None
    chosen_cost: float = 0.0


@dataclass
class MoveInfo:
    from_stage_idx: Optional[int]   # индекс в массиве этапов (None = старт)
    to_stage_idx: int
    order_id: int
    from_stage_id: Optional[int] = None
    to_stage_id: Optional[int] = None
    # Заполняется решателем:
    route_id: Optional[int] = None
    start_step: Optional[int] = None
    end_step: Optional[int] = None
    cost: float = 0.0
    origin_city_id: Optional[int] = None
    destination_city_id: Optional[int] = None


@dataclass
class OrderResult:
    order_id: int
    feasible: bool
    completion_step: Optional[int]
    completion_date: Optional[date]
    deadline: date
    production_cost: float
    logistics_cost: float
    total_cost: float
    stage_assignments: List[StageInfo]
    movements: List[MoveInfo]
    explanation: dict


@dataclass
class SolveResult:
    status: str   # "OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID"
    objective: float
    per_order: Dict[int, OrderResult]
    message: str = ""
    # Если деадлайн нарушен — здесь минимально достижимый срок (по заказу)
    min_completion: Dict[int, date] = field(default_factory=dict)


# ---------- Сборка модели ----------

class JewelryScheduler:
    """
    Один экземпляр = одна сессия планирования.
    Можно строить как multi-order, так и для одного заказа (estimate).
    """

    def __init__(self, db: Session, orders: List[Order], couriers_total: int):
        self.db = db
        self.orders = orders
        self.couriers_total = max(1, int(couriers_total))
        self.horizon = total_horizon_steps()

        self.model = cp_model.CpModel()
        # Структуры
        self.stages: List[StageInfo] = []
        self.stage_to_idx: Dict[int, int] = {}
        # ((order_id, order_index) → stage_idx)
        self.order_index: Dict[Tuple[int, int], int] = {}

        self.opt_intervals: Dict[Tuple[int, int], cp_model.IntervalVar] = {}  # (stage_idx, performer_id)
        self.x: Dict[Tuple[int, int], cp_model.IntVar] = {}                   # (stage_idx, performer_id)
        self.main_start: Dict[int, cp_model.IntVar] = {}
        self.main_end: Dict[int, cp_model.IntVar] = {}
        self.main_interval: Dict[int, cp_model.IntervalVar] = {}
        # Перевозки
        self.moves: List[MoveInfo] = []
        # (move_idx, route_id) → opt interval
        self.move_opt: Dict[Tuple[int, int], cp_model.IntervalVar] = {}
        self.move_y: Dict[Tuple[int, int], cp_model.IntVar] = {}
        self.move_route_options: Dict[int, List[TransportOption]] = {}
        # Главные интервалы перевозок (для cumulative по курьерам)
        self.move_interval: Dict[int, cp_model.IntervalVar] = {}
        self.move_start: Dict[int, cp_model.IntVar] = {}
        self.move_end: Dict[int, cp_model.IntVar] = {}
        self.move_present: Dict[int, cp_model.IntVar] = {}

    # ---------- Шаг 1. Прочесть данные ----------

    def _collect_candidates(self, stage: Stage) -> List[CandidateInfo]:
        result: List[CandidateInfo] = []
        for cand in stage.candidates:
            performer = cand.performer
            if not performer.active:
                continue
            # Стоимость и длительность этапа у данного исполнителя
            ps: Optional[PerformerStage] = None
            for skill in performer.skills:
                if skill.stage_template_id == stage.stage_template_id:
                    ps = skill
                    break
            if ps is None:
                # У исполнителя нет такого навыка — пропускаем
                continue
            result.append(CandidateInfo(
                performer_id=performer.id,
                city_id=performer.city_id,
                cost=ps.cost,
                duration_hours=ps.duration_hours,
                duration_steps=hours_to_steps(ps.duration_hours),
                workdays=performer.workdays or [0, 1, 2, 3, 4],
            ))
        return result

    def _build_stage_index(self) -> bool:
        for order in self.orders:
            for stage in order.stages:
                # Только этапы, ещё не завершённые. Для прототипа — все.
                cands = self._collect_candidates(stage)
                if not cands:
                    # Нет ни одного исполнителя — модель невыполнима
                    return False
                idx = len(self.stages)
                info = StageInfo(
                    stage_id=stage.id,
                    order_id=order.id,
                    order_index=stage.order_index,
                    name=stage.name,
                    candidates=cands,
                )
                self.stages.append(info)
                self.stage_to_idx[stage.id] = idx
                self.order_index[(order.id, stage.order_index)] = idx
        return True

    # ---------- Шаг 2. Переменные этапов ----------

    def _add_stage_variables(self) -> None:
        for s_idx, s in enumerate(self.stages):
            # Главные start/end для этапа
            start = self.model.NewIntVar(0, self.horizon, f"start_s{s_idx}")
            end = self.model.NewIntVar(0, self.horizon, f"end_s{s_idx}")
            self.main_start[s_idx] = start
            self.main_end[s_idx] = end

            # Альтернативные опциональные интервалы по каждому кандидату
            for cand in s.candidates:
                key = (s_idx, cand.performer_id)
                present = self.model.NewBoolVar(f"x_s{s_idx}_p{cand.performer_id}")
                # Опциональный интервал с фиксированной длительностью
                opt_start = self.model.NewIntVar(0, self.horizon, f"os_s{s_idx}_p{cand.performer_id}")
                opt_end = self.model.NewIntVar(0, self.horizon, f"oe_s{s_idx}_p{cand.performer_id}")
                opt_iv = self.model.NewOptionalIntervalVar(
                    opt_start, cand.duration_steps, opt_end, present,
                    f"iv_s{s_idx}_p{cand.performer_id}"
                )
                self.x[key] = present
                self.opt_intervals[key] = opt_iv
                # Связь с главными start/end
                self.model.Add(opt_start == start).OnlyEnforceIf(present)
                self.model.Add(opt_end == end).OnlyEnforceIf(present)

            # Ровно один кандидат активен
            self.model.AddExactlyOne([self.x[(s_idx, c.performer_id)] for c in s.candidates])

            # Главный (нефиксированный по длительности) интервал — для удобства,
            # длительность вычисляется как (end - start), >= 0.
            # Это не используется как ресурс — ресурсами выступают opt_intervals.
            duration = self.model.NewIntVar(0, self.horizon, f"dur_s{s_idx}")
            self.model.Add(duration == end - start)
            self.main_interval[s_idx] = self.model.NewIntervalVar(
                start, duration, end, f"main_iv_s{s_idx}"
            )

    # ---------- Шаг 3. Прецедентность и перевозки ----------

    def _add_precedence_and_moves(self) -> None:
        # Группируем индексы этапов по заказу и сортируем по order_index
        by_order: Dict[int, List[int]] = {}
        for idx, s in enumerate(self.stages):
            by_order.setdefault(s.order_id, []).append(idx)
        for ids in by_order.values():
            ids.sort(key=lambda i: self.stages[i].order_index)

        for order in self.orders:
            ids = by_order.get(order.id, [])
            if not ids:
                continue
            # Стартовый "виртуальный" этап — старт из start_city
            start_city_id = order.start_city_id
            # Создаём перевозки между парами (prev, next), а также «вход» (None → первый)
            prev_idx: Optional[int] = None
            prev_city_id: Optional[int] = start_city_id
            for cur_idx in ids:
                self._add_move(order.id, prev_idx, cur_idx, prev_city_id)
                prev_idx = cur_idx
                # Город после этапа равен городу исполнителя — но он зависит от выбора.
                # Город как переменная не нужен: city_id есть у каждого кандидата.
                prev_city_id = None  # дальше определяется из выбранного исполнителя
        # После определения перевозок добавим логические связи прецедентности.

    def _add_move(
        self,
        order_id: int,
        from_idx: Optional[int],
        to_idx: int,
        explicit_origin_city: Optional[int],
    ) -> None:
        """
        Добавляет переменные перевозки между from_idx и to_idx.

        Логика выбора маршрута:
          - Если from_idx is None: город отправления = explicit_origin_city (или None — без перевозки).
          - Иначе: город отправления = город исполнителя from_idx.
          - Город назначения = город исполнителя to_idx.

        Для каждой пары (perf_from, perf_to) перечисляем варианты маршрутов из БД.
        Если города совпадают → перевозка не нужна, present = 0.
        """
        move_idx = len(self.moves)
        m_info = MoveInfo(
            from_stage_idx=from_idx,
            to_stage_idx=to_idx,
            order_id=order_id,
            from_stage_id=self.stages[from_idx].stage_id if from_idx is not None else None,
            to_stage_id=self.stages[to_idx].stage_id,
        )
        self.moves.append(m_info)

        # Собираем все возможные (origin_city, destination_city) пары
        to_stage = self.stages[to_idx]
        if from_idx is None:
            # Один origin (или ничего)
            origin_options: List[Tuple[Optional[int], Optional[int]]] = [(None, explicit_origin_city)]
            # (performer_id или None, city_id или None)
        else:
            from_stage = self.stages[from_idx]
            origin_options = [(c.performer_id, c.city_id) for c in from_stage.candidates]

        dest_options = [(c.performer_id, c.city_id) for c in to_stage.candidates]

        # Главные start/end перевозки + признак присутствия
        m_start = self.model.NewIntVar(0, self.horizon, f"ms_m{move_idx}")
        m_end = self.model.NewIntVar(0, self.horizon, f"me_m{move_idx}")
        m_present = self.model.NewBoolVar(f"mp_m{move_idx}")
        # Длительность зависит от выбранного маршрута, но мы используем
        # альтернативные опциональные интервалы и привязываем к m_start/m_end.
        self.move_start[move_idx] = m_start
        self.move_end[move_idx] = m_end
        self.move_present[move_idx] = m_present

        # Опциональные интервалы по комбинациям (origin_perf, dest_perf, route)
        route_keys: List[cp_model.IntVar] = []
        no_move_keys: List[cp_model.IntVar] = []
        options_for_move: List[TransportOption] = []

        for from_perf_id, from_city_id in origin_options:
            for to_perf_id, to_city_id in dest_options:
                # Триггер активности: соответствующие исполнители выбраны
                trigger_vars: List[cp_model.IntVar] = []
                if from_perf_id is not None:
                    trigger_vars.append(self.x[(from_idx, from_perf_id)])
                if to_perf_id is not None:
                    trigger_vars.append(self.x[(to_idx, to_perf_id)])

                if from_city_id == to_city_id and from_city_id is not None:
                    # Перевозка не нужна — фиксируем "no move" вариант
                    no_move = self.model.NewBoolVar(f"nomv_m{move_idx}_f{from_perf_id}_t{to_perf_id}")
                    no_move_keys.append(no_move)
                    # Если оба триггера = 1, то и no_move = 1
                    if trigger_vars:
                        self.model.AddBoolAnd(trigger_vars).OnlyEnforceIf(no_move)
                        self.model.AddBoolOr([v.Not() for v in trigger_vars]).OnlyEnforceIf(no_move.Not())
                    else:
                        self.model.Add(no_move == 1)
                    continue

                if from_city_id is None or to_city_id is None:
                    # Не должно случаться при корректной модели
                    continue

                # Запрашиваем маршруты от логистического модуля
                opts = TransportAdapter.options(self.db, from_city_id, to_city_id)
                for opt in opts:
                    duration = hours_to_steps(opt.total_hours)
                    r_present = self.model.NewBoolVar(
                        f"r_m{move_idx}_f{from_perf_id}_t{to_perf_id}_r{opt.route_id}"
                    )
                    r_start = self.model.NewIntVar(0, self.horizon, f"rs_{r_present.Name()}")
                    r_end = self.model.NewIntVar(0, self.horizon, f"re_{r_present.Name()}")
                    r_iv = self.model.NewOptionalIntervalVar(
                        r_start, duration, r_end, r_present, f"riv_{r_present.Name()}"
                    )
                    self.move_opt[(move_idx, len(options_for_move))] = r_iv
                    self.move_y[(move_idx, len(options_for_move))] = r_present
                    options_for_move.append(opt)
                    route_keys.append(r_present)
                    # Связь с главным start/end перевозки
                    self.model.Add(r_start == m_start).OnlyEnforceIf(r_present)
                    self.model.Add(r_end == m_end).OnlyEnforceIf(r_present)
                    # r_present ⇒ оба триггера активны
                    for tv in trigger_vars:
                        self.model.AddImplication(r_present, tv)

        self.move_route_options[move_idx] = options_for_move

        # Ровно одна опция: либо одна из перевозок, либо "no move"
        all_keys = route_keys + no_move_keys
        if all_keys:
            self.model.AddExactlyOne(all_keys)
            # m_present = 1 ⇔ выбран маршрут (не no_move)
            if route_keys:
                self.model.Add(sum(route_keys) == m_present)
            else:
                self.model.Add(m_present == 0)
        else:
            # Нет ни одного варианта — модель будет infeasible
            self.model.Add(m_present == 0)

        # Главный интервал перевозки для cumulative по курьерам
        m_dur = self.model.NewIntVar(0, self.horizon, f"md_m{move_idx}")
        self.model.Add(m_dur == m_end - m_start)
        m_iv = self.model.NewOptionalIntervalVar(m_start, m_dur, m_end, m_present, f"miv_m{move_idx}")
        self.move_interval[move_idx] = m_iv

        # Прецедентность: end(from_stage) ≤ start(move); end(move) ≤ start(to_stage).
        # Если перевозки нет (no_move): end(from_stage) ≤ start(to_stage).
        to_start = self.main_start[to_idx]
        if from_idx is not None:
            from_end = self.main_end[from_idx]
            # При m_present: from_end ≤ m_start, m_end ≤ to_start
            self.model.Add(from_end <= m_start).OnlyEnforceIf(m_present)
            self.model.Add(m_end <= to_start).OnlyEnforceIf(m_present)
            # При not m_present: from_end ≤ to_start (общее ограничение)
            self.model.Add(from_end <= to_start).OnlyEnforceIf(m_present.Not())
        else:
            # Стартовая перевозка: m_end ≤ to_start; иначе to_start ≥ 0 (всегда).
            self.model.Add(m_end <= to_start).OnlyEnforceIf(m_present)

    # ---------- Шаг 4. Ресурсы ----------

    def _add_resource_constraints(self) -> None:
        # NoOverlap по каждому исполнителю
        by_performer: Dict[int, List[cp_model.IntervalVar]] = {}
        for (s_idx, p_id), iv in self.opt_intervals.items():
            by_performer.setdefault(p_id, []).append(iv)
        for p_id, ivs in by_performer.items():
            self.model.AddNoOverlap(ivs)

        # Курьеры: cumulative с requirement=1, capacity=COURIERS_TOTAL
        all_move_ivs = [self.move_interval[i] for i in range(len(self.moves))]
        if all_move_ivs:
            demands = [1] * len(all_move_ivs)
            self.model.AddCumulative(all_move_ivs, demands, self.couriers_total)

    def _add_calendar_constraints(self) -> None:
        """Запрещённые интервалы для каждого исполнителя."""
        for (s_idx, p_id), iv in self.opt_intervals.items():
            # Достаём workdays кандидата
            stage = self.stages[s_idx]
            cand = next(c for c in stage.candidates if c.performer_id == p_id)
            forb = offwork_intervals(cand.workdays)
            if not forb:
                continue
            present = self.x[(s_idx, p_id)]
            start_var = iv.StartExpr()
            end_var = iv.EndExpr()
            # Для каждого forbidden интервала [a,b): start ≥ b OR end ≤ a (если интервал активен)
            for (a, b) in forb:
                # Используем bool variables
                before = self.model.NewBoolVar(f"cal_bef_s{s_idx}_p{p_id}_{a}")
                after = self.model.NewBoolVar(f"cal_aft_s{s_idx}_p{p_id}_{a}")
                self.model.Add(end_var <= a).OnlyEnforceIf(before)
                self.model.Add(end_var > a).OnlyEnforceIf(before.Not())
                self.model.Add(start_var >= b).OnlyEnforceIf(after)
                self.model.Add(start_var < b).OnlyEnforceIf(after.Not())
                # Если этап у этого исполнителя активен — должен быть до или после интервала
                self.model.AddBoolOr([before, after, present.Not()])

    # ---------- Шаг 5. Цель и дедлайн ----------

    def _build_objective(self, soft_deadline: bool) -> Tuple[cp_model.IntVar, Dict[int, cp_model.IntVar]]:
        """
        soft_deadline=False — жёсткий дедлайн (end ≤ deadline).
        soft_deadline=True — минимизируется сумма просрочек.

        Возвращает: (общая_стоимость_x100, dict order_id → completion_var)
        Стоимость умножаем на 100, чтобы остаться в целых числах (копейки).
        """
        SCALE = 100

        # Стоимость производства
        prod_terms = []
        for (s_idx, p_id), present in self.x.items():
            cand = next(c for c in self.stages[s_idx].candidates if c.performer_id == p_id)
            cost = int(round(cand.cost * SCALE))
            prod_terms.append(cost * present)

        # Стоимость логистики
        log_terms = []
        for m_idx in range(len(self.moves)):
            opts = self.move_route_options[m_idx]
            for opt_idx, opt in enumerate(opts):
                key = (m_idx, opt_idx)
                if key in self.move_y:
                    log_terms.append(int(round(opt.cost * SCALE)) * self.move_y[key])

        total_cost = self.model.NewIntVar(0, 10**12, "total_cost")
        self.model.Add(total_cost == sum(prod_terms) + sum(log_terms))

        # Дедлайны: для каждого заказа берём end последнего этапа
        completion: Dict[int, cp_model.IntVar] = {}
        tardiness_terms = []
        horizon_start_dt = horizon_start()
        for order in self.orders:
            ids = sorted(
                [i for i, s in enumerate(self.stages) if s.order_id == order.id],
                key=lambda i: self.stages[i].order_index,
            )
            if not ids:
                continue
            last_end = self.main_end[ids[-1]]
            # Дедлайн в шагах — конец дня deadline
            dl_dt = datetime.combine(order.deadline, datetime.min.time()) + timedelta(days=1)
            dl_steps = max(0, min(self.horizon, to_steps(dl_dt)))
            completion[order.id] = last_end
            if soft_deadline:
                tardy = self.model.NewIntVar(0, self.horizon, f"tardy_o{order.id}")
                self.model.Add(tardy >= last_end - dl_steps)
                self.model.Add(tardy >= 0)
                tardiness_terms.append(tardy)
            else:
                self.model.Add(last_end <= dl_steps)

        if soft_deadline:
            # Сильно штрафуем просрочку, чтобы она минимизировалась в первую очередь
            BIG = 10**9
            total_tardy = self.model.NewIntVar(0, self.horizon * len(self.orders) + 1, "total_tardy")
            self.model.Add(total_tardy == sum(tardiness_terms) if tardiness_terms else 0)
            objective = self.model.NewIntVar(0, 10**18, "objective")
            self.model.Add(objective == BIG * total_tardy + total_cost)
            self.model.Minimize(objective)
        else:
            self.model.Minimize(total_cost)

        return total_cost, completion

    # ---------- Шаг 6. Запуск ----------

    def solve(self, soft_deadline: bool = False) -> SolveResult:
        if not self._build_stage_index():
            return SolveResult(
                status="INFEASIBLE",
                objective=0.0,
                per_order={},
                message="Нет ни одного исполнителя для одного из этапов.",
            )
        self._add_stage_variables()
        self._add_precedence_and_moves()
        self._add_resource_constraints()
        self._add_calendar_constraints()
        total_cost_var, completion = self._build_objective(soft_deadline=soft_deadline)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(settings.OPT_TIME_LIMIT_SEC)
        solver.parameters.num_search_workers = 4
        status = solver.Solve(self.model)
        status_name = solver.StatusName(status)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Нет решения даже в soft-режиме (что странно, но возможно при отсутствии маршрутов)
            return SolveResult(
                status=status_name,
                objective=0.0,
                per_order={},
                message="Не удалось найти решение (проверьте маршруты, кандидатов, календари).",
            )

        # Извлекаем решение
        for s_idx, s in enumerate(self.stages):
            for cand in s.candidates:
                if solver.BooleanValue(self.x[(s_idx, cand.performer_id)]):
                    s.chosen_performer_id = cand.performer_id
                    s.chosen_cost = cand.cost
                    s.start_step = solver.Value(self.main_start[s_idx])
                    s.end_step = solver.Value(self.main_end[s_idx])
                    break

        # Перевозки
        for m_idx, m in enumerate(self.moves):
            if solver.Value(self.move_present[m_idx]) == 1:
                m.start_step = solver.Value(self.move_start[m_idx])
                m.end_step = solver.Value(self.move_end[m_idx])
                # Какой маршрут выбран
                opts = self.move_route_options[m_idx]
                for opt_idx, opt in enumerate(opts):
                    if solver.Value(self.move_y[(m_idx, opt_idx)]) == 1:
                        m.route_id = opt.route_id
                        m.cost = opt.cost
                        m.origin_city_id = opt.origin_id
                        m.destination_city_id = opt.destination_id
                        break

        # Группируем по заказам
        per_order: Dict[int, OrderResult] = {}
        min_completion: Dict[int, date] = {}
        for order in self.orders:
            stage_assignments = [s for s in self.stages if s.order_id == order.id]
            stage_assignments.sort(key=lambda s: s.order_index)
            movements = [m for m in self.moves if m.order_id == order.id]
            prod_sum = sum(s.chosen_cost for s in stage_assignments)
            log_sum = sum(m.cost for m in movements if m.route_id is not None)
            completion_step = solver.Value(completion[order.id]) if order.id in completion else None
            if completion_step is not None:
                completion_dt = from_steps(completion_step)
                completion_d = completion_dt.date()
            else:
                completion_d = None

            feasible = completion_d is not None and completion_d <= order.deadline
            if not feasible:
                min_completion[order.id] = completion_d
            # Объяснение: для каждого этапа — выбранный + альтернативы
            explanation = self._build_explanation(stage_assignments, movements)
            per_order[order.id] = OrderResult(
                order_id=order.id,
                feasible=feasible,
                completion_step=completion_step,
                completion_date=completion_d,
                deadline=order.deadline,
                production_cost=prod_sum,
                logistics_cost=log_sum,
                total_cost=prod_sum + log_sum,
                stage_assignments=stage_assignments,
                movements=movements,
                explanation=explanation,
            )

        return SolveResult(
            status=status_name,
            objective=solver.ObjectiveValue(),
            per_order=per_order,
            min_completion=min_completion,
            message="OK",
        )

    def _build_explanation(self, stages: List[StageInfo], movements: List[MoveInfo]) -> dict:
        """Объяснимость (п.8 ТЗ): почему выбраны эти исполнители и маршруты."""
        stage_explanations = []
        for s in stages:
            alternatives = []
            for c in s.candidates:
                alternatives.append({
                    "performer_id": c.performer_id,
                    "cost": c.cost,
                    "duration_hours": c.duration_hours,
                    "city_id": c.city_id,
                    "chosen": c.performer_id == s.chosen_performer_id,
                })
            chosen = next((a for a in alternatives if a["chosen"]), None)
            reasons = []
            if chosen and alternatives:
                cheaper = [a for a in alternatives if a["cost"] < chosen["cost"]]
                faster = [a for a in alternatives if a["duration_hours"] < chosen["duration_hours"]]
                if not cheaper and not faster:
                    reasons.append("единственный или доминирующий по цене и сроку вариант")
                else:
                    if cheaper:
                        reasons.append(
                            "более дешёвые альтернативы отвергнуты из-за конфликта по календарю, "
                            "загрузке исполнителя или удлинения логистики"
                        )
                    if faster:
                        reasons.append(
                            "более быстрые альтернативы отвергнуты из-за стоимости или ресурсных конфликтов"
                        )
            stage_explanations.append({
                "stage_id": s.stage_id,
                "stage_name": s.name,
                "chosen_performer_id": s.chosen_performer_id,
                "alternatives": alternatives,
                "reasons": reasons,
            })
        move_explanations = []
        for m in movements:
            move_explanations.append({
                "from_stage_id": self.stages[m.from_stage_idx].stage_id if m.from_stage_idx is not None else None,
                "to_stage_id": self.stages[m.to_stage_idx].stage_id,
                "route_id": m.route_id,
                "cost": m.cost,
                "skipped": m.route_id is None,
            })
        return {"stages": stage_explanations, "movements": move_explanations}
