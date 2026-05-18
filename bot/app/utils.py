from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CITY_TIMEZONES: dict[str, str] = {
    "москва": "Europe/Moscow",
    "мск": "Europe/Moscow",
    "moscow": "Europe/Moscow",
    "msk": "Europe/Moscow",
    "санкт-петербург": "Europe/Moscow",
    "санкт петербург": "Europe/Moscow",
    "питер": "Europe/Moscow",
    "спб": "Europe/Moscow",
    "нижний новгород": "Europe/Moscow",
    "казань": "Europe/Moscow",
    "воронеж": "Europe/Moscow",
    "ростов-на-дону": "Europe/Moscow",
    "ростов на дону": "Europe/Moscow",
    "краснодар": "Europe/Moscow",
    "сочи": "Europe/Moscow",
    "калининград": "Europe/Kaliningrad",
    "самара": "Europe/Samara",
    "саратов": "Europe/Saratov",
    "ульяновск": "Europe/Ulyanovsk",
    "астрахань": "Europe/Astrakhan",
    "волгоград": "Europe/Volgograd",
    "екатеринбург": "Asia/Yekaterinburg",
    "пермь": "Asia/Yekaterinburg",
    "уфа": "Asia/Yekaterinburg",
    "челябинск": "Asia/Yekaterinburg",
    "тюмень": "Asia/Yekaterinburg",
    "курган": "Asia/Yekaterinburg",
    "омск": "Asia/Omsk",
    "томск": "Asia/Tomsk",
    "новосибирск": "Asia/Novosibirsk",
    "барнаул": "Asia/Barnaul",
    "красноярск": "Asia/Krasnoyarsk",
    "абакан": "Asia/Krasnoyarsk",
    "кемерово": "Asia/Novokuznetsk",
    "новокузнецк": "Asia/Novokuznetsk",
    "иркутск": "Asia/Irkutsk",
    "улан-удэ": "Asia/Irkutsk",
    "якутск": "Asia/Yakutsk",
    "чита": "Asia/Chita",
    "благовещенск": "Asia/Yakutsk",
    "владивосток": "Asia/Vladivostok",
    "хабаровск": "Asia/Vladivostok",
    "уссурийск": "Asia/Vladivostok",
    "магадан": "Asia/Magadan",
    "южно-сахалинск": "Asia/Sakhalin",
    "сахалин": "Asia/Sakhalin",
    "камчатка": "Asia/Kamchatka",
    "петропавловск-камчатский": "Asia/Kamchatka",
    "петропавловск камчатский": "Asia/Kamchatka",
}

UTC_ALIASES: dict[str, str] = {
    "utc": "UTC",
    "gmt": "UTC",
    "utc+2": "Etc/GMT-2",
    "utc+3": "Europe/Moscow",
    "utc+4": "Europe/Samara",
    "utc+5": "Asia/Yekaterinburg",
    "utc+6": "Asia/Omsk",
    "utc+7": "Asia/Tomsk",
    "utc+8": "Asia/Irkutsk",
    "utc+9": "Asia/Yakutsk",
    "utc+10": "Asia/Vladivostok",
    "utc+11": "Asia/Magadan",
    "utc+12": "Asia/Kamchatka",
    "gmt+2": "Etc/GMT-2",
    "gmt+3": "Europe/Moscow",
    "gmt+4": "Europe/Samara",
    "gmt+5": "Asia/Yekaterinburg",
    "gmt+6": "Asia/Omsk",
    "gmt+7": "Asia/Tomsk",
    "gmt+8": "Asia/Irkutsk",
    "gmt+9": "Asia/Yakutsk",
    "gmt+10": "Asia/Vladivostok",
    "gmt+11": "Asia/Magadan",
    "gmt+12": "Asia/Kamchatka",
    "мск+0": "Europe/Moscow",
    "мск": "Europe/Moscow",
    "мск+1": "Europe/Samara",
    "мск+2": "Asia/Yekaterinburg",
    "мск+3": "Asia/Omsk",
    "мск+4": "Asia/Tomsk",
    "мск+5": "Asia/Irkutsk",
    "мск+6": "Asia/Yakutsk",
    "мск+7": "Asia/Vladivostok",
    "мск+8": "Asia/Magadan",
    "мск+9": "Asia/Kamchatka",
}


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().replace("ё", "е").replace("—", "-").split())


def parse_timezone(value: str | None) -> str | None:
    if not value:
        return None

    raw = value.strip()
    key = _normalize(raw)

    if key in CITY_TIMEZONES:
        return CITY_TIMEZONES[key]

    compact_key = key.replace(" ", "")
    if compact_key in UTC_ALIASES:
        return UTC_ALIASES[compact_key]

    try:
        ZoneInfo(raw)
        return raw
    except ZoneInfoNotFoundError:
        return None


def user_today(timezone_name: str) -> date:
    return datetime.now(ZoneInfo(timezone_name)).date()


def user_now(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def parse_time(value: str) -> time | None:
    raw = value.strip().replace(".", ":")
    parts = raw.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return None

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    return time(hour=hour, minute=minute)


def water_status(next_watering_on: date, today: date) -> str:
    delta = (next_watering_on - today).days
    if delta > 1:
        return f"🟢 Полить через {delta} дней"
    if delta == 1:
        return "🟢 Полить завтра"
    if delta == 0:
        return "🟡 Пора поливать сегодня"
    return f"🔴 Просрочено на {abs(delta)} дней"


def next_date_from_today(days: int, timezone_name: str) -> date:
    return user_today(timezone_name) + timedelta(days=days)
