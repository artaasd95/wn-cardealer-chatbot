"""Schedule domain entity, natural date/time parsing and validation.

Everything here is pure domain logic: no I/O, no framework imports. The
schedule use case feeds it the raw text the LLM extracted and gets back either
a concrete datetime or the exact question to ask the user next.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from domain.exceptions import InvalidScheduleError

_WEEKDAYS: dict[str, int] = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tues": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thurs": 3,
    "thur": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_MONTHS: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_PART_OF_DAY: dict[str, tuple[int, int]] = {
    "morning": (6, 11),
    "midday": (11, 13),
    "noon": (12, 12),
    "afternoon": (12, 17),
    "evening": (17, 21),
    "night": (19, 23),
}

_TIMEZONE_ALIASES: dict[str, str] = {
    "UTC": "UTC",
    "GMT": "UTC",
    "Z": "UTC",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "BST": "Europe/London",
    "CET": "Europe/Berlin",
    "CEST": "Europe/Berlin",
    "IST": "Asia/Kolkata",
    "JST": "Asia/Tokyo",
    "AEST": "Australia/Sydney",
    "SGT": "Asia/Singapore",
    "MSK": "Europe/Moscow",
}


def utc_now_naive() -> datetime:
    """Current UTC time as a naive datetime (the app's storage convention)."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class Schedule:
    """Domain entity representing a scheduled call."""

    schedule_id: str
    dealer_id: str
    car_id: str
    scheduled_for: datetime
    timezone: str
    status: str = "confirmed"
    user_id: str | None = None
    created_at: datetime | None = None

    def validate(self) -> None:
        """Validate the schedule; raise InvalidScheduleError if invalid.

        Checks:
        - scheduled_for is not in the past
        - timezone is non-empty
        - status is one of: confirmed, pending, cancelled
        """
        now = utc_now_naive()
        if self.scheduled_for < now:
            raise InvalidScheduleError(f"Scheduled time {self.scheduled_for} is in the past")

        if not self.timezone or not self.timezone.strip():
            raise InvalidScheduleError("Timezone is required and cannot be empty")

        valid_statuses = {"confirmed", "pending", "cancelled"}
        if self.status not in valid_statuses:
            raise InvalidScheduleError(f"Status must be one of {valid_statuses}, got {self.status}")

    def is_future(self) -> bool:
        """Check if the scheduled time is in the future.

        Returns:
            True if scheduled_for > now.
        """
        return self.scheduled_for > utc_now_naive()

    def time_until_scheduled(self) -> int:
        """Return seconds until the scheduled call.

        Returns:
            Total seconds remaining, or negative if in the past.
        """
        delta = self.scheduled_for - utc_now_naive()
        return int(delta.total_seconds())


@dataclass(frozen=True)
class ScheduleParse:
    """Outcome of parsing the raw date/time text of one scheduling turn.

    Exactly one of these holds:
    - ``value``: a concrete local datetime — proceed to validation
    - ``missing``: which piece of information is absent (``date``/``time``/
      ``datetime``), with ``clarification`` asking only for that piece
    - ``clarification``: the text to ask the user (ambiguous or unreadable input),
      with ``kind`` saying which of the two it is
    """

    value: datetime | None = None
    missing: str | None = None
    clarification: str | None = None
    kind: str | None = None  # "ambiguous" | "invalid"


def resolve_timezone(text: str | None) -> str | None:
    """Resolve a timezone name to an IANA identifier.

    Args:
        text: Raw timezone text (``UTC``, ``EST``, ``Europe/Berlin``, ...).
            Empty or missing means UTC.

    Returns:
        An IANA timezone name, or None when the text cannot be recognized.
    """
    if text is None or not text.strip():
        return "UTC"

    raw = text.strip()
    name = _TIMEZONE_ALIASES.get(raw.upper(), raw)
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None
    return name


def to_utc_naive(local: datetime, tz_name: str) -> datetime:
    """Convert a wall-clock datetime in ``tz_name`` to naive UTC.

    Args:
        local: Naive wall-clock datetime as the user meant it.
        tz_name: IANA timezone name the wall clock belongs to.

    Returns:
        Naive UTC datetime (the storage convention used everywhere in the app).
    """
    return local.replace(tzinfo=ZoneInfo(tz_name)).astimezone(UTC).replace(tzinfo=None)


def _clean(text: str) -> str:
    """Lowercase, strip punctuation noise and collapse whitespace."""
    out = text.strip().lower().replace(".", "").replace(",", " ")
    out = re.sub(r"\b([ap])\s+m\b", r"\1m", out)
    return re.sub(r"\s+", " ", out).strip()


def _strip_ordinal(value: str) -> str:
    """Drop English ordinal suffixes: ``5th`` → ``5``."""
    return re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", value)


def _parse_date(text: str, today: date) -> tuple[date | None, str | None]:
    """Parse one raw date expression.

    Args:
        text: Raw date text from the extraction.
        today: Reference date for relative expressions.

    Returns:
        ``(date, error)`` where error is ``ambiguous``, ``invalid`` or None.
    """
    t = _clean(text).strip()
    if not t:
        return None, "missing"

    if t in {"today", "tonight"}:
        return today, None
    if t.startswith("tomorrow"):
        return today + timedelta(days=1), None
    if "next week" in t:
        return today + timedelta(days=7), None

    # Weekday names: "friday", "next monday", "this tuesday"
    if "/" not in t and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        names = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
        m = re.search(rf"\b(?:(next|this)\s+)?({names})\b", t)
        if m:
            ahead = (_WEEKDAYS[m.group(2)] - today.weekday()) % 7
            if m.group(1) == "next":
                ahead += 7
            return today + timedelta(days=ahead), None

    # ISO date
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        try:
            return date.fromisoformat(t), None
        except ValueError:
            return None, "invalid"

    # Numeric date: 10/01/2026, 25.12.2026, 10/01
    m = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?", t)
    if m:
        first, second = int(m.group(1)), int(m.group(2))
        if first <= 12 and second <= 12 and first != second:
            return None, "ambiguous"
        year = int(m.group(3)) if m.group(3) else today.year
        if year < 100:
            year += 2000
        if first > 12:
            day, month = first, second
        else:
            month, day = first, second
        try:
            return date(year, month, day), None
        except ValueError:
            return None, "invalid"

    # Month-name dates, parsed token-wise (avoids strptime's year-less warning):
    # "5 october", "october 5 2026", "5 oct", "oct 5th"
    tokens = _strip_ordinal(t).split()
    year = today.year
    if tokens and re.fullmatch(r"\d{4}", tokens[-1]):
        year = int(tokens[-1])
        tokens = tokens[:-1]
    if len(tokens) == 2:
        day_token, month_token = tokens
        if day_token in _MONTHS and re.fullmatch(r"\d{1,2}", month_token):
            month, day = _MONTHS[day_token], int(month_token)
        elif month_token in _MONTHS and re.fullmatch(r"\d{1,2}", day_token):
            day, month = int(day_token), _MONTHS[month_token]
        else:
            month = day = 0
        if month:
            try:
                return date(year, month, day), None
            except ValueError:
                return None, "invalid"

    return None, "invalid"


def _parse_time(text: str) -> tuple[str, int | None, int | None, str | None]:
    """Parse one raw time expression.

    Returns:
        ``(kind, hour, minute, part_of_day)`` where kind is one of
        ``clock`` (resolved), ``part`` (only a part of day, no clock time),
        ``ambiguous`` (hour without am/pm), ``invalid`` (unreadable).
    """
    t = _clean(text)
    if not t:
        return "invalid", None, None, None
    if t in {"noon", "midday", "12 noon"}:
        return "clock", 12, 0, None
    if t == "midnight":
        return "clock", 0, 0, None

    part = next((word for word in _PART_OF_DAY if re.search(rf"\b{word}\b", t)), None)
    md = re.search(r"([ap])m\b", t)
    meridiem = md.group(1) if md else None

    nm = re.search(r"(\d{1,2})(?::(\d{2}))?", t)
    if not nm:
        if part:
            return "part", None, None, part
        return "invalid", None, None, None

    hour = int(nm.group(1))
    minute = int(nm.group(2) or 0)
    if minute > 59 or hour > 24:
        return "invalid", None, None, None

    if meridiem:
        if hour < 1 or hour > 12:
            return "invalid", None, None, None
        resolved = hour % 12 + (12 if meridiem == "p" else 0)
        return "clock", resolved, minute, part

    if part:
        if part in {"noon", "midday"}:
            resolved = 12 if hour >= 12 else hour + 12
        elif part == "morning":
            resolved = 0 if hour == 12 else hour
        else:  # afternoon / evening / night
            resolved = hour if hour >= 12 else hour + 12
        if resolved > 23:
            return "invalid", None, None, None
        return "clock", resolved, minute, part

    if hour >= 13:
        return "clock", hour, minute, None
    if hour == 0:
        return "clock", 0, minute, None
    # Two-digit hours ("10:00", "09:30") read as 24-hour notation; a bare
    # single-digit hour ("3", "2:30") is genuinely ambiguous without am/pm.
    if len(nm.group(1)) >= 2:
        return "clock", hour, minute, None
    return "ambiguous", hour, minute, None


def parse_schedule_when(
    date_raw: str | None,
    time_raw: str | None,
    *,
    now: datetime | None = None,
) -> ScheduleParse:
    """Parse raw date/time text into a concrete local datetime.

    Missing information asks only for what is missing; ambiguous or unreadable
    input produces a clarification question instead of a guess.

    Args:
        date_raw: Raw date text (may be None/empty).
        time_raw: Raw time text (may be None/empty).
        now: Reference timestamp; defaults to the current UTC time.

    Returns:
        A ScheduleParse carrying the datetime, the missing field, or the
        question to ask the user.
    """
    reference = now or utc_now_naive()
    date_text = (date_raw or "").strip()
    time_text = (time_raw or "").strip()

    if not date_text and not time_text:
        return ScheduleParse(
            missing="datetime",
            clarification="What date and time would you like the call?",
        )
    if not date_text:
        return ScheduleParse(
            missing="date",
            clarification=f"What date would you like the call? (You mentioned {time_text}.)",
        )
    if not time_text:
        return ScheduleParse(
            missing="time",
            clarification=f"What time on {date_text} would you like the call?",
        )

    parsed_date, date_error = _parse_date(date_text, reference.date())
    if date_error == "ambiguous":
        return ScheduleParse(
            clarification=(
                f'Is "{date_text}" day-first or month-first? Could you say it as e.g. "2026-10-01"?'
            ),
            kind="ambiguous",
        )
    if parsed_date is None:
        return ScheduleParse(
            clarification=(
                f'I could not read the date "{date_text}" — '
                'try "tomorrow", "Friday" or "2026-10-01".'
            ),
            kind="invalid",
        )

    kind, hour, minute, part = _parse_time(time_text)
    if kind == "invalid":
        return ScheduleParse(
            clarification=f'I could not read the time "{time_text}" — try "3pm" or "15:00".',
            kind="invalid",
        )
    if kind == "part":
        return ScheduleParse(
            clarification=f"What time in the {part}? For example 9am or 3pm.",
            kind="ambiguous",
        )
    if kind == "ambiguous":
        return ScheduleParse(
            clarification=(f"Should the call be at {hour} in the morning or in the afternoon?"),
            kind="ambiguous",
        )

    if hour is None or minute is None:
        # Defensive: kind == "clock" always carries both.
        return ScheduleParse(
            clarification=f'I could not read the time "{time_text}" — try "3pm" or "15:00".',
            kind="invalid",
        )
    return ScheduleParse(value=datetime.combine(parsed_date, time(hour, minute)))
