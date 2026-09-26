"""Shared test doubles: a scripted LLMPort and stub repositories.

Every unit and integration test drives the application through these doubles,
so no test can ever reach a real LLM provider or a real network call — the
plan's rule is "LLM port faked in every test".
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel

from config.settings import AppSettings, DatabaseSettings, LLMSettings, SessionSettings, Settings
from models.inputs.car import NormalizedCarQuery
from models.inputs.response import ResponseWording
from models.inputs.schedule import ScheduleExtraction
from models.inputs.task import TaskDecision
from models.outputs.car import CarRecord, CarSearchResult
from models.outputs.dealer import DealerRecord, DealerWithCars
from models.outputs.schedule import ScheduleRecord

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    """Scripted LLMPort double.

    Responses are queued per output schema. The first queued item for a schema
    wins, so multi-turn scripts read top to bottom. When a queue is empty the
    fake answers with a default instance of the requested schema — exactly what
    the real adapter's deterministic fallback produces on a dead provider.

    Anything queued as an exception is raised instead of answered, to simulate
    a provider that breaks its "never raise" contract.
    """

    def __init__(self) -> None:
        """Initialize empty response queues."""
        self.prompts: list[str] = []
        self.calls: list[str] = []
        self._queues: dict[type[BaseModel], deque[BaseModel | Exception]] = defaultdict(deque)

    def enqueue(
        self,
        response: BaseModel | Exception,
        output_type: type[BaseModel] | None = None,
    ) -> None:
        """Queue one scripted response (or failure) for an output schema.

        Args:
            response: A pydantic instance to return, or an exception to raise.
            output_type: The schema the response belongs to; inferred from the
                response itself when omitted (required for exceptions).
        """
        key = output_type or type(response)
        self._queues[key].append(response)

    def structured_completion(self, prompt: str, output_type: type[T]) -> T:
        """Return the next scripted response for the requested schema.

        Args:
            prompt: The prompt under test (recorded for assertions).
            output_type: The pydantic schema the caller expects.

        Returns:
            The scripted instance, or an all-default instance when unscripted.

        Raises:
            Exception: When an exception was scripted for this schema.
        """
        self.prompts.append(prompt)
        self.calls.append(output_type.__name__)

        queue = self._queues.get(output_type)
        if queue:
            item = queue.popleft()
            if isinstance(item, Exception):
                raise item
            if not isinstance(item, output_type):  # pragma: no cover - test bug guard
                raise AssertionError(
                    f"scripted {type(item).__name__} is not a {output_type.__name__}"
                )
            return item

        return output_type()  # same shape as the adapter's deterministic fallback


class RaisingLLM:
    """LLMPort double that always raises — the 'dead provider' case."""

    def __init__(self, exc: Exception | None = None) -> None:
        """Initialize with the failure to raise.

        Args:
            exc: The exception to raise on every call.
        """
        self.exc = exc or RuntimeError("LLM provider is down")
        self.prompts: list[str] = []

    def structured_completion(self, prompt: str, output_type: type[T]) -> T:
        """Always raise, simulating a provider that broke the port contract.

        Args:
            prompt: The prompt under test.
            output_type: Unused.

        Raises:
            Exception: Always.
        """
        self.prompts.append(prompt)
        raise self.exc


class StubCarRepository:
    """CarRepository double returning a scripted search result."""

    def __init__(
        self,
        result: CarSearchResult | None = None,
        *,
        by_id: dict[str, CarRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        """Initialize the stub.

        Args:
            result: The result every search returns.
            by_id: Optional car records by id for get_by_id.
            error: Exception raised by every operation, when set.
        """
        self.result = result if result is not None else CarSearchResult(status="not_found")
        self.by_id = by_id or {}
        self.error = error
        self.queries: list[NormalizedCarQuery] = []

    def search(self, query: NormalizedCarQuery) -> CarSearchResult:
        """Return the scripted result and record the normalized query.

        Args:
            query: The normalized query under test.

        Returns:
            The scripted search result.

        Raises:
            Exception: When the stub was configured with an error.
        """
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.result

    def get_by_id(self, car_id: str) -> CarRecord | None:
        """Return a scripted car record.

        Args:
            car_id: The car identifier.

        Returns:
            The record when scripted, otherwise None.
        """
        if self.error:
            raise self.error
        return self.by_id.get(car_id)

    def search_by_alias(self, alias: str) -> list[str]:
        """Return no alias expansions.

        Args:
            alias: The alias under test.

        Returns:
            An empty list.
        """
        return []


class StubDealerRepository:
    """DealerRepository double returning scripted dealer records."""

    def __init__(
        self,
        *,
        by_id: dict[str, DealerRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        """Initialize the stub.

        Args:
            by_id: Dealer records keyed by dealer id.
            error: Exception raised by every operation, when set.
        """
        self.by_id = by_id or {}
        self.error = error
        self.requested: list[str] = []

    def get_by_id(self, dealer_id: str) -> DealerRecord | None:
        """Return a scripted dealer record.

        Args:
            dealer_id: The dealer identifier.

        Returns:
            The record when scripted, otherwise None.

        Raises:
            Exception: When the stub was configured with an error.
        """
        self.requested.append(dealer_id)
        if self.error:
            raise self.error
        return self.by_id.get(dealer_id)

    def get_with_cars(self, dealer_id: str) -> DealerWithCars | None:
        """Return a dealer with an empty car list.

        Args:
            dealer_id: The dealer identifier.

        Returns:
            DealerWithCars when scripted, otherwise None.
        """
        dealer = self.get_by_id(dealer_id)
        return DealerWithCars(dealer=dealer, cars=[]) if dealer else None

    def search_by_city(self, city: str) -> list[DealerRecord]:
        """Return dealers whose city matches exactly.

        Args:
            city: The city to filter on.

        Returns:
            Matching dealer records.
        """
        return [d for d in self.by_id.values() if d.city == city]


class StubScheduleRepository:
    """ScheduleRepository double recording every saved schedule."""

    def __init__(self, *, error: Exception | None = None) -> None:
        """Initialize the stub.

        Args:
            error: Exception raised by save, when set.
        """
        self.error = error
        self.saved: list[ScheduleRecord] = []

    def save(self, record: ScheduleRecord) -> ScheduleRecord:
        """Record the schedule, or fail as scripted.

        Args:
            record: The schedule to persist.

        Returns:
            The same record.

        Raises:
            Exception: When the stub was configured with an error.
        """
        if self.error:
            raise self.error
        self.saved.append(record)
        return record


# ---------------------------------------------------------------------------
# Record builders — small, explicit, and shared across suites.
# ---------------------------------------------------------------------------


def make_car(
    car_id: str = "C-0003",
    make: str = "BMW",
    model: str = "3 Series",
    variant: str | None = "320i",
    year: int = 2021,
    dealer_id: str = "D-003",
    price_min: float | None = 3_500_000,
    price_max: float | None = 4_100_000,
) -> CarRecord:
    """Build a car record with sane defaults.

    Args:
        car_id: Car identifier.
        make: Car make.
        model: Car model.
        variant: Car variant, or None when the row has none.
        year: Model year.
        dealer_id: Selling dealer's identifier.
        price_min: Lower price bound.
        price_max: Upper price bound.

    Returns:
        The car record.
    """
    return CarRecord(
        car_id=car_id,
        make=make,
        model=model,
        variant=variant,
        year=year,
        dealer_id=dealer_id,
        price_min=price_min,
        price_max=price_max,
    )


def make_dealer(
    dealer_id: str = "D-003",
    name: str = "Prestige Cars",
    city: str = "Bangalore",
    address: str = "78 MG Road",
    phone: str = "+91-80-2552-1003",
    email: str = "sales@prestigecars.example",
    rating: float | None = 4.7,
) -> DealerRecord:
    """Build a dealer record with sane defaults.

    Args:
        dealer_id: Dealer identifier.
        name: Dealer name.
        city: City.
        address: Street address.
        phone: Phone number.
        email: Email address (empty string models a partial row).
        rating: Average rating, or None when unrated.

    Returns:
        The dealer record.
    """
    return DealerRecord(
        dealer_id=dealer_id,
        dealer_name=name,
        city=city,
        address=address,
        phone=phone,
        email=email,
        rating=rating,
    )


def make_test_settings(database_url: str = "sqlite:///:memory:") -> Settings:
    """Build a Settings instance without reading the developer's .env.

    Every sub-settings object is constructed with explicit values and
    ``_env_file=None``, so a real `.env` (or leaked environment variables)
    can never steer a test.

    Args:
        database_url: SQLAlchemy URL for the test database.

    Returns:
        A fully populated Settings container.
    """
    settings = Settings.__new__(Settings)
    settings.llm_settings = LLMSettings(
        _env_file=None,
        provider="openai_compatible",
        base_url="https://llm.test.invalid/v1",
        api_key="sk-test-key-not-real",
        model="test-model",
        temperature=0.0,
        timeout_seconds=5,
        max_retries=0,
    )
    settings.app_settings = AppSettings(
        _env_file=None, env="test", host="127.0.0.1", port=8000
    )
    settings.database_settings = DatabaseSettings(_env_file=None, url=database_url, echo=False)
    settings.session_settings = SessionSettings(_env_file=None, ttl_seconds=3600)
    return settings


def scripted_response(output_type: type[BaseModel], **fields: object) -> BaseModel:
    """Build a scripted LLM response for an output schema.

    Args:
        output_type: The pydantic schema to build.
        **fields: Field values for the schema.

    Returns:
        An instance of output_type with the given fields.
    """
    return output_type.model_validate(fields)


def wording_reply(text: str) -> ResponseWording:
    """Build a ResponseWording script entry.

    Args:
        text: The reply text ("" forces the deterministic fallback wording).

    Returns:
        The ResponseWording instance.
    """
    return ResponseWording(reply=text)


def schedule_extraction(
    date_raw: str | None = None,
    time_raw: str | None = None,
    timezone: str | None = None,
) -> ScheduleExtraction:
    """Build a ScheduleExtraction script entry.

    Args:
        date_raw: Raw date text as extracted, or None.
        time_raw: Raw time text as extracted, or None.
        timezone: Raw timezone text as extracted, or None.

    Returns:
        The ScheduleExtraction instance.
    """
    return ScheduleExtraction(date_raw=date_raw, time_raw=time_raw, timezone=timezone)


def task_decision(task_type: str, confidence: float = 0.9) -> TaskDecision:
    """Build a TaskDecision script entry.

    Args:
        task_type: One of the TaskType values (or any string to test rejection).
        confidence: Classification confidence.

    Returns:
        The TaskDecision instance.
    """
    return TaskDecision(task_type=task_type, confidence=confidence, reason="scripted")


def now_utc() -> datetime:
    """Current naive UTC timestamp (the app's storage convention)."""
    return datetime.now(UTC).replace(tzinfo=None)
