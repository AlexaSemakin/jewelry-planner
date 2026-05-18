"""
Сидер тестовых данных, представительных для приёмки.

Заливается, только если в БД ещё нет городов.
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.models import (
    City, StageTemplate, Performer, PerformerStage, Route,
    Order, Stage, StageCandidate,
)


def seed_if_empty(db: Session) -> None:
    if db.query(City).count() > 0:
        return

    # ---- Cities ----
    cities = {
        name: City(name=name)
        for name in ["Москва", "Санкт-Петербург", "Пермь", "Екатеринбург", "Киров", "Казань", "Кострома"]
    }
    db.add_all(cities.values())
    db.flush()

    # ---- Stage templates ----
    templates = {
        "base":     StageTemplate(code="base",     name="Изготовление основы",
                                  attributes_schema={"metal": "string", "method": "string"}),
        "stones":   StageTemplate(code="stones",   name="Работа с камнями",
                                  attributes_schema={"stone": "string", "carat": "number"}),
        "setting":  StageTemplate(code="setting",  name="Закрепка камней",
                                  attributes_schema={"setting_type": "string"}),
        "engraving":StageTemplate(code="engraving",name="Гравировка",
                                  attributes_schema={"text": "string", "depth": "number"}),
        "polish":   StageTemplate(code="polish",   name="Полировка",
                                  attributes_schema={"finish": "string"}),
        "qc":       StageTemplate(code="qc",       name="Контроль качества",
                                  attributes_schema={}),
    }
    db.add_all(templates.values())
    db.flush()

    # ---- Performers + skills ----
    def perf(name, city, spec, workdays, skills):
        p = Performer(
            name=name, city_id=city.id,
            specialization=spec, contact="",
            workdays=workdays, active=True,
        )
        db.add(p); db.flush()
        for code, cost, hrs in skills:
            db.add(PerformerStage(
                performer_id=p.id,
                stage_template_id=templates[code].id,
                cost=cost, duration_hours=hrs,
            ))
        return p

    performers = []
    # Основы — Пермь, Кострома, Москва
    performers.append(perf("Мастерская «Пермский литейщик»", cities["Пермь"], "Литьё, золото, серебро",
                           [0,1,2,3,4], [("base", 18000, 16), ("polish", 4000, 4)]))
    performers.append(perf("Костромская ювелирная фабрика", cities["Кострома"], "Литьё, золото",
                           [0,1,2,3,4,5], [("base", 21000, 12), ("polish", 4500, 5)]))
    performers.append(perf("MoscowCraft", cities["Москва"], "Литьё на заказ",
                           [0,1,2,3,4], [("base", 26000, 10)]))

    # Камни — Екатеринбург, СПб
    performers.append(perf("Уральские самоцветы", cities["Екатеринбург"], "Огранка и подбор камней",
                           [0,1,2,3,4], [("stones", 15000, 14), ("setting", 9000, 8)]))
    performers.append(perf("Питерская гранильная", cities["Санкт-Петербург"], "Бриллианты, изумруды",
                           [1,2,3,4,5], [("stones", 22000, 9), ("setting", 12000, 6)]))

    # Закрепка — Москва, Екатеринбург
    performers.append(perf("Закрепка Премиум (Москва)", cities["Москва"], "Микропавэ, инвизибл",
                           [0,1,2,3,4], [("setting", 11000, 7)]))

    # Гравировка — Киров, Москва
    performers.append(perf("Кировская гравёрная", cities["Киров"], "Ручная и лазерная гравировка",
                           [0,1,2,3,4], [("engraving", 3500, 4), ("polish", 3000, 3)]))
    performers.append(perf("MoscowEngrave", cities["Москва"], "Лазерная гравировка",
                           [0,1,2,3,4,5,6], [("engraving", 5500, 2)]))

    # Полировка + QC — Казань
    performers.append(perf("Казанский финиш", cities["Казань"], "Полировка, QC",
                           [0,1,2,3,4], [("polish", 3800, 4), ("qc", 2500, 2)]))
    performers.append(perf("ПитерQC", cities["Санкт-Петербург"], "Контроль качества",
                           [0,1,2,3,4], [("qc", 4000, 3)]))

    db.flush()

    # ---- Routes ----
    def add_routes(a, b, options):
        for mode, cost, hrs in options:
            db.add(Route(origin_id=a.id, destination_id=b.id,
                         mode=mode, cost=cost, duration_hours=hrs,
                         handover_hours=1.0, pickup_hours=1.0))
            db.add(Route(origin_id=b.id, destination_id=a.id,
                         mode=mode, cost=cost, duration_hours=hrs,
                         handover_hours=1.0, pickup_hours=1.0))

    add_routes(cities["Москва"], cities["Санкт-Петербург"], [
        ("rail", 1800, 4),
        ("air",  4500, 1.5),
        ("courier", 3500, 10),
    ])
    add_routes(cities["Москва"], cities["Пермь"], [
        ("rail", 3200, 22),
        ("air", 7800, 2.5),
    ])
    add_routes(cities["Москва"], cities["Екатеринбург"], [
        ("rail", 3500, 26),
        ("air", 7000, 2.5),
    ])
    add_routes(cities["Москва"], cities["Киров"], [
        ("rail", 2200, 13),
        ("courier", 5500, 16),
    ])
    add_routes(cities["Москва"], cities["Казань"], [
        ("rail", 2400, 12),
        ("air", 6500, 1.5),
    ])
    add_routes(cities["Москва"], cities["Кострома"], [
        ("rail", 1500, 6),
        ("courier", 3000, 8),
    ])
    add_routes(cities["Пермь"], cities["Екатеринбург"], [
        ("rail", 1700, 6),
        ("courier", 2500, 8),
    ])
    add_routes(cities["Екатеринбург"], cities["Киров"], [
        ("rail", 2200, 14),
        ("courier", 3500, 16),
    ])
    add_routes(cities["Киров"], cities["Казань"], [
        ("rail", 1500, 7),
    ])
    add_routes(cities["Казань"], cities["Санкт-Петербург"], [
        ("rail", 3000, 24),
        ("air", 6500, 2.5),
    ])
    add_routes(cities["Кострома"], cities["Санкт-Петербург"], [
        ("rail", 2400, 14),
    ])
    add_routes(cities["Пермь"], cities["Казань"], [
        ("rail", 2100, 14),
    ])
    add_routes(cities["Екатеринбург"], cities["Казань"], [
        ("rail", 2200, 12),
    ])
    add_routes(cities["Кострома"], cities["Москва"], [])  # уже добавлены выше
    db.flush()

    # ---- Demo orders ----
    def make_order(name, customer, deadline, material, weight, start_city, plan):
        o = Order(
            name=name, description="",
            customer=customer, deadline=deadline,
            material=material, weight_g=weight,
            status="estimated", start_city_id=start_city.id,
        )
        db.add(o); db.flush()
        for idx, (tcode, stage_name, attrs, candidate_names) in enumerate(plan):
            s = Stage(
                order_id=o.id,
                stage_template_id=templates[tcode].id,
                order_index=idx,
                name=stage_name,
                attributes=attrs,
                status="pending",
            )
            db.add(s); db.flush()
            for pname in candidate_names:
                perf_obj = next(p for p in performers if p.name == pname)
                db.add(StageCandidate(stage_id=s.id, performer_id=perf_obj.id))
        return o

    today = date.today()
    make_order(
        "Кольцо «Грань» с сапфиром",
        "Иванова А.",
        deadline=today + timedelta(days=21),
        material="Au 585",
        weight=6.5,
        start_city=cities["Москва"],
        plan=[
            ("base", "Изготовление основы кольца",
             {"metal": "Au 585", "method": "литьё"},
             ["Мастерская «Пермский литейщик»", "Костромская ювелирная фабрика", "MoscowCraft"]),
            ("stones", "Подбор и огранка сапфира",
             {"stone": "Sapphire", "carat": 0.8},
             ["Уральские самоцветы", "Питерская гранильная"]),
            ("setting", "Закрепка камня",
             {"setting_type": "крапан"},
             ["Уральские самоцветы", "Питерская гранильная", "Закрепка Премиум (Москва)"]),
            ("engraving", "Внутренняя гравировка имени",
             {"text": "А&Д", "depth": 0.1},
             ["Кировская гравёрная", "MoscowEngrave"]),
            ("polish", "Финишная полировка",
             {"finish": "глянец"},
             ["Казанский финиш", "Костромская ювелирная фабрика", "Кировская гравёрная"]),
            ("qc", "Контроль качества", {},
             ["Казанский финиш", "ПитерQC"]),
        ],
    )

    make_order(
        "Серьги «Каскад» с бриллиантами",
        "Семёнова К.",
        deadline=today + timedelta(days=35),
        material="Au 750 (белое)",
        weight=4.2,
        start_city=cities["Санкт-Петербург"],
        plan=[
            ("base", "Изготовление основы серёг",
             {"metal": "Au 750", "method": "литьё+ручная доводка"},
             ["Костромская ювелирная фабрика", "MoscowCraft"]),
            ("stones", "Подбор бриллиантов",
             {"stone": "Diamond", "carat": 1.2},
             ["Питерская гранильная", "Уральские самоцветы"]),
            ("setting", "Закрепка микропавэ",
             {"setting_type": "паве"},
             ["Закрепка Премиум (Москва)", "Питерская гранильная"]),
            ("polish", "Полировка",
             {"finish": "матово-глянец"},
             ["Казанский финиш", "Мастерская «Пермский литейщик»"]),
            ("qc", "Контроль качества", {},
             ["ПитерQC", "Казанский финиш"]),
        ],
    )

    make_order(
        "Подвеска «Монограмма»",
        "Свадебное агентство «Лето»",
        deadline=today + timedelta(days=14),
        material="Ag 925",
        weight=3.0,
        start_city=cities["Москва"],
        plan=[
            ("base", "Изготовление основы",
             {"metal": "Ag 925", "method": "штамповка"},
             ["Мастерская «Пермский литейщик»", "Костромская ювелирная фабрика"]),
            ("engraving", "Гравировка монограммы",
             {"text": "А♡Д", "depth": 0.15},
             ["MoscowEngrave", "Кировская гравёрная"]),
            ("polish", "Полировка",
             {"finish": "глянец"},
             ["Казанский финиш", "Кировская гравёрная"]),
        ],
    )

    db.commit()
