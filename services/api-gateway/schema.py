from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

import httpx
import strawberry
from strawberry.fastapi import BaseContext
from strawberry.schema.config import StrawberryConfig
from fastapi import Request, Response
from graphql import GraphQLError
from strawberry.dataloader import DataLoader
from strawberry.types import Info

from config import settings
from limiter import enforce_rate_limit


DecimalScalar = strawberry.scalar(
    Decimal,
    name="Decimal",
    serialize=str,
    parse_value=Decimal,
)


@dataclass
class GatewayContext(BaseContext):  # Strawberry exige BaseContext (o un dict) como contexto
    request: Request
    response: Response
    user: dict[str, Any] | None
    session_id: str | None
    flight_offer_loader: DataLoader[tuple[str, tuple[str, ...]], dict[str, Any] | None]
    hotel_offer_loader: DataLoader[tuple[str, tuple[str, ...]], dict[str, Any] | None]
    car_offer_loader: DataLoader[tuple[str, tuple[str, ...]], dict[str, Any] | None]


@strawberry.enum
class FailurePoint(str, Enum):
    FLIGHT = "FLIGHT"
    HOTEL = "HOTEL"
    CAR = "CAR"
    PAYMENT = "PAYMENT"


@strawberry.enum
class CabinClass(str, Enum):
    ECONOMY = "ECONOMY"
    PREMIUM_ECONOMY = "PREMIUM_ECONOMY"
    BUSINESS = "BUSINESS"
    FIRST = "FIRST"


@strawberry.enum
class RoomType(str, Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    TWIN = "TWIN"
    SUITE = "SUITE"
    FAMILY = "FAMILY"


@strawberry.enum
class CarCategory(str, Enum):
    ECONOMY = "ECONOMY"
    COMPACT = "COMPACT"
    SUV = "SUV"
    VAN = "VAN"
    LUXURY = "LUXURY"


@strawberry.enum
class Transmission(str, Enum):
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"


@strawberry.enum
class OfferSort(str, Enum):
    PRICE_ASC = "PRICE_ASC"
    PRICE_DESC = "PRICE_DESC"
    DEPARTURE_ASC = "DEPARTURE_ASC"
    RATING_DESC = "RATING_DESC"


@strawberry.enum
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@strawberry.enum
class SagaStatus(str, Enum):
    STARTED = "STARTED"
    COMPENSATING = "COMPENSATING"
    COMPLETED = "COMPLETED"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"


@strawberry.enum
class SagaStepName(str, Enum):
    RESERVE_FLIGHT = "RESERVE_FLIGHT"
    RESERVE_HOTEL = "RESERVE_HOTEL"
    RESERVE_CAR = "RESERVE_CAR"
    PROCESS_PAYMENT = "PROCESS_PAYMENT"
    CONFIRM_FLIGHT = "CONFIRM_FLIGHT"
    CONFIRM_HOTEL = "CONFIRM_HOTEL"
    CONFIRM_CAR = "CONFIRM_CAR"
    ISSUE_INVOICE = "ISSUE_INVOICE"


@strawberry.enum
class SagaAction(str, Enum):
    EXECUTE = "EXECUTE"
    COMPENSATE = "COMPENSATE"


@strawberry.enum
class SagaStepStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@strawberry.enum
class PaymentStatus(str, Enum):
    CAPTURED = "CAPTURED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


@strawberry.type
class FlightOffer:
    id: strawberry.ID
    source: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    duration_minutes: int
    cabin_class: CabinClass
    price: Decimal
    currency: str
    seats_available: int
    scraped_at: datetime


@strawberry.type
class HotelOffer:
    id: strawberry.ID
    source: str
    hotel_name: str
    city_code: str
    address: str | None
    stars: int
    rating: float | None
    room_type: RoomType
    max_guests: int
    check_in: date
    check_out: date
    nights: int
    price_per_night: Decimal
    price_total: Decimal
    currency: str
    rooms_available: int
    scraped_at: datetime


@strawberry.type
class CarOffer:
    id: strawberry.ID
    source: str
    company: str
    model: str
    category: CarCategory
    transmission: Transmission
    seats: int
    city_code: str
    pickup_date: date
    dropoff_date: date
    days: int
    price_per_day: Decimal
    price_total: Decimal
    currency: str
    units_available: int
    scraped_at: datetime


@strawberry.input
class PackageSearchInput:
    origin: str
    destination: str
    departure_date: date
    return_date: date
    passengers: int = 1
    rooms: int = 1
    max_budget: Decimal | None = None
    min_hotel_stars: int | None = None
    car_category: CarCategory | None = None
    cabin_class: CabinClass | None = None
    limit: int = 10


@strawberry.type
class PackagePriceBreakdown:
    flight: Decimal
    hotel: Decimal
    car: Decimal
    subtotal: Decimal
    taxes: Decimal
    total: Decimal


@strawberry.type
class TravelPackage:
    flight: FlightOffer
    hotel: HotelOffer
    car: CarOffer
    passengers: int
    rooms: int
    estimated_price: PackagePriceBreakdown
    currency: str


@strawberry.type
class CatalogSourceStatus:
    catalog: str
    total_offers: int
    last_sync_at: datetime | None


def _selection_names(info: Info[GatewayContext, Any], allowed_fields: set[str]) -> set[str]:
    names = {
        _camel_to_snake(field.name)
        for field in info.selected_fields[0].selections
        if _camel_to_snake(field.name) in allowed_fields
    }
    if not names:
        names.add("id")
    if "duration_minutes" in names:
        names.update({"arrival_at", "departure_at"})
    return names


def _nested_selection_names(
    info: Info[GatewayContext, Any],
    parent_name: str,
    allowed_fields: set[str],
) -> set[str]:
    return next(
        (
            {
                _camel_to_snake(child.name)
                for child in field.selections
                if _camel_to_snake(child.name) in allowed_fields
            }
            for field in info.selected_fields[0].selections
            if _camel_to_snake(field.name) == parent_name
        ),
        set(),
    )


@strawberry.input
class FlightSearchInput:
    origin: str
    destination: str
    departure_date: date
    passengers: int = 1
    cabin_class: CabinClass | None = None
    max_price: Decimal | None = None
    sort_by: OfferSort = OfferSort.PRICE_ASC
    limit: int = 20
    offset: int = 0


@strawberry.input
class HotelSearchInput:
    city_code: str
    check_in: date
    check_out: date
    guests: int = 1
    rooms: int = 1
    min_stars: int | None = None
    max_price: Decimal | None = None
    sort_by: OfferSort = OfferSort.PRICE_ASC
    limit: int = 20
    offset: int = 0


@strawberry.input
class CarSearchInput:
    city_code: str
    pickup_date: date
    dropoff_date: date
    category: CarCategory | None = None
    max_price: Decimal | None = None
    sort_by: OfferSort = OfferSort.PRICE_ASC
    limit: int = 20
    offset: int = 0


@strawberry.type
class User:
    id: strawberry.ID
    email: str
    full_name: str
    created_at: datetime


@strawberry.type
class AuthPayload:
    user: User


@strawberry.type
class SagaStep:
    step: SagaStepName
    action: SagaAction
    status: SagaStepStatus
    attempt: int
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


@strawberry.type
class Saga:
    id: strawberry.ID
    status: SagaStatus
    current_step: SagaStepName | None
    failure_reason: str | None
    simulate_failure_at: FailurePoint | None
    steps: list[SagaStep]


@strawberry.type
class Payment:
    status: PaymentStatus
    amount: Decimal
    currency: str
    provider_ref: str | None


@strawberry.type
class Invoice:
    number: str
    subtotal: Decimal
    taxes: Decimal
    total: Decimal
    currency: str
    issued_at: datetime


@strawberry.type
class Order:
    id: strawberry.ID
    status: OrderStatus
    flight_offer_id: strawberry.Private[str]
    hotel_offer_id: strawberry.Private[str]
    car_offer_id: strawberry.Private[str]
    passengers: int
    rooms: int
    subtotal: Decimal | None
    taxes: Decimal | None
    total_amount: Decimal | None
    currency: str
    saga: Saga
    payment: Payment | None
    invoice: Invoice | None
    created_at: datetime
    updated_at: datetime

    @strawberry.field
    async def flight(self, info: Info[GatewayContext, None]) -> FlightOffer | None:
        fields = _selection_names(info, {
            "id", "source", "airline", "flight_number", "origin", "destination",
            "departure_at", "arrival_at", "cabin_class", "price", "currency",
            "seats_available", "scraped_at", "duration_minutes",
        })
        return await info.context.flight_offer_loader.load((self.flight_offer_id, tuple(sorted(fields))))

    @strawberry.field
    async def hotel(self, info: Info[GatewayContext, None]) -> HotelOffer | None:
        fields = _selection_names(info, {
            "id", "source", "hotel_name", "city_code", "address", "stars", "rating",
            "room_type", "max_guests", "check_in", "check_out", "nights",
            "price_per_night", "price_total", "currency", "rooms_available", "scraped_at",
        })
        return await info.context.hotel_offer_loader.load((self.hotel_offer_id, tuple(sorted(fields))))

    @strawberry.field
    async def car(self, info: Info[GatewayContext, None]) -> CarOffer | None:
        fields = _selection_names(info, {
            "id", "source", "company", "model", "category", "transmission", "seats",
            "city_code", "pickup_date", "dropoff_date", "days", "price_per_day",
            "price_total", "currency", "units_available", "scraped_at",
        })
        return await info.context.car_offer_loader.load((self.car_offer_id, tuple(sorted(fields))))


@strawberry.type
class BookPackagePayload:
    order: Order


@strawberry.input
class RegisterInput:
    email: str
    password: str
    full_name: str


@strawberry.input
class LoginInput:
    email: str
    password: str


@strawberry.input
class BookPackageInput:
    flight_offer_id: strawberry.ID
    hotel_offer_id: strawberry.ID
    car_offer_id: strawberry.ID
    passengers: int
    idempotency_key: str
    rooms: int = 1
    simulate_failure_at: FailurePoint | None = None


@strawberry.type
class Query:
    @strawberry.field
    async def hello(self) -> str:
        return "API Gateway GraphQL activo"

    @strawberry.field
    async def search_flights(
        self,
        info: Info[GatewayContext, None],
        input: FlightSearchInput,
    ) -> list[FlightOffer]:
        if (
            input.passengers < 1
            or input.passengers > 9
            or (input.max_price is not None and input.max_price < 0)
        ):
            raise GraphQLError("Invalid flight search parameters", extensions={"code": "BAD_USER_INPUT"})
        departure_start = datetime.combine(input.departure_date, time.min, tzinfo=timezone.utc)
        where: dict[str, Any] = {
            "origin": {"_eq": input.origin.upper()},
            "destination": {"_eq": input.destination.upper()},
            "departure_at": {
                "_gte": departure_start.isoformat(),
                "_lt": (departure_start + timedelta(days=1)).isoformat(),
            },
            "seats_available": {"_gte": input.passengers},
        }
        if input.cabin_class is not None:
            where["cabin_class"] = {"_eq": input.cabin_class.value}
        if input.max_price is not None:
            where["price"] = {"_lte": float(input.max_price)}
        order_by = {
            OfferSort.PRICE_ASC: "price: asc",
            OfferSort.PRICE_DESC: "price: desc",
            OfferSort.DEPARTURE_ASC: "departure_at: asc",
            OfferSort.RATING_DESC: "price: asc",
        }[input.sort_by]
        return await _search_catalog(
            info,
            table="flight_offers",
            where=where,
            limit=input.limit,
            offset=input.offset,
            order_by=order_by,
            allowed_fields={
                "id", "source", "airline", "flight_number", "origin", "destination",
                "departure_at", "arrival_at", "cabin_class", "price", "currency",
                "seats_available", "scraped_at", "duration_minutes",
            },
        )

    @strawberry.field
    async def search_hotels(
        self,
        info: Info[GatewayContext, None],
        input: HotelSearchInput,
    ) -> list[HotelOffer]:
        if (
            input.check_out <= input.check_in
            or input.guests < 1
            or input.rooms < 1
            or (input.min_stars is not None and not 1 <= input.min_stars <= 5)
            or (input.max_price is not None and input.max_price < 0)
        ):
            raise GraphQLError("Invalid hotel search parameters", extensions={"code": "BAD_USER_INPUT"})
        where: dict[str, Any] = {
            "city_code": {"_eq": input.city_code.upper()},
            "check_in": {"_eq": input.check_in.isoformat()},
            "check_out": {"_eq": input.check_out.isoformat()},
            "max_guests": {"_gte": input.guests},
            "rooms_available": {"_gte": input.rooms},
        }
        if input.min_stars is not None:
            where["stars"] = {"_gte": input.min_stars}
        if input.max_price is not None:
            where["price_total"] = {"_lte": float(input.max_price)}
        order_by = {
            OfferSort.PRICE_ASC: "price_total: asc",
            OfferSort.PRICE_DESC: "price_total: desc",
            OfferSort.RATING_DESC: "rating: desc",
            OfferSort.DEPARTURE_ASC: "price_total: asc",
        }[input.sort_by]
        return await _search_catalog(
            info,
            table="room_offers",
            where=where,
            limit=input.limit,
            offset=input.offset,
            order_by=order_by,
            allowed_fields={
                "id", "source", "hotel_name", "city_code", "address", "stars", "rating",
                "room_type", "max_guests", "check_in", "check_out", "nights",
                "price_per_night", "price_total", "currency", "rooms_available", "scraped_at",
            },
        )

    @strawberry.field
    async def search_cars(
        self,
        info: Info[GatewayContext, None],
        input: CarSearchInput,
    ) -> list[CarOffer]:
        if (
            input.dropoff_date <= input.pickup_date
            or (input.max_price is not None and input.max_price < 0)
        ):
            raise GraphQLError("Invalid car search parameters", extensions={"code": "BAD_USER_INPUT"})
        where: dict[str, Any] = {
            "city_code": {"_eq": input.city_code.upper()},
            "pickup_date": {"_eq": input.pickup_date.isoformat()},
            "dropoff_date": {"_eq": input.dropoff_date.isoformat()},
            "units_available": {"_gte": 1},
        }
        if input.category is not None:
            where["category"] = {"_eq": input.category.value}
        if input.max_price is not None:
            where["price_total"] = {"_lte": float(input.max_price)}
        order_by = {
            OfferSort.PRICE_ASC: "price_total: asc",
            OfferSort.PRICE_DESC: "price_total: desc",
            OfferSort.DEPARTURE_ASC: "price_total: asc",
            OfferSort.RATING_DESC: "price_total: asc",
        }[input.sort_by]
        return await _search_catalog(
            info,
            table="car_offers",
            where=where,
            limit=input.limit,
            offset=input.offset,
            order_by=order_by,
            allowed_fields={
                "id", "source", "company", "model", "category", "transmission", "seats",
                "city_code", "pickup_date", "dropoff_date", "days", "price_per_day",
                "price_total", "currency", "units_available", "scraped_at",
            },
        )

    @strawberry.field
    async def search_packages(
        self,
        info: Info[GatewayContext, None],
        input: PackageSearchInput,
    ) -> list[TravelPackage]:
        if (
            input.limit < 1
            or input.limit > settings.graphql_max_limit
            or input.passengers < 1
            or input.passengers > 9
            or input.rooms < 1
            or input.rooms > 5
            or input.return_date <= input.departure_date
            or (input.max_budget is not None and input.max_budget < 0)
            or (input.min_hotel_stars is not None and not 1 <= input.min_hotel_stars <= 5)
        ):
            raise GraphQLError("Invalid package search parameters", extensions={"code": "BAD_USER_INPUT"})

        flight_allowed_fields = {
            "id", "source", "airline", "flight_number", "origin", "destination",
            "departure_at", "arrival_at", "duration_minutes", "cabin_class",
            "price", "currency", "seats_available", "scraped_at",
        }
        hotel_allowed_fields = {
            "id", "source", "hotel_name", "city_code", "address", "stars", "rating",
            "room_type", "max_guests", "check_in", "check_out", "nights",
            "price_per_night", "price_total", "currency", "rooms_available", "scraped_at",
        }
        car_allowed_fields = {
            "id", "source", "company", "model", "category", "transmission", "seats",
            "city_code", "pickup_date", "dropoff_date", "days", "price_per_day",
            "price_total", "currency", "units_available", "scraped_at",
        }
        flight_fields = _nested_selection_names(
            info, "flight", flight_allowed_fields
        ) | {"price", "currency"}
        hotel_fields = _nested_selection_names(
            info, "hotel", hotel_allowed_fields
        ) | {"price_total"}
        car_fields = _nested_selection_names(
            info, "car", car_allowed_fields
        ) | {"price_total"}
        departure_start = datetime.combine(input.departure_date, time.min, tzinfo=timezone.utc)
        flight_where: dict[str, Any] = {
            "origin": {"_eq": input.origin.upper()},
            "destination": {"_eq": input.destination.upper()},
            "departure_at": {
                "_gte": departure_start.isoformat(),
                "_lt": (departure_start + timedelta(days=1)).isoformat(),
            },
            "seats_available": {"_gte": input.passengers},
        }
        if input.cabin_class is not None:
            flight_where["cabin_class"] = {"_eq": input.cabin_class.value}
        hotel_where: dict[str, Any] = {
            "city_code": {"_eq": input.destination.upper()},
            "check_in": {"_eq": input.departure_date.isoformat()},
            "check_out": {"_eq": input.return_date.isoformat()},
            "max_guests": {"_gte": input.passengers},
            "rooms_available": {"_gte": input.rooms},
        }
        if input.min_hotel_stars is not None:
            hotel_where["stars"] = {"_gte": input.min_hotel_stars}
        car_where: dict[str, Any] = {
            "city_code": {"_eq": input.destination.upper()},
            "pickup_date": {"_eq": input.departure_date.isoformat()},
            "dropoff_date": {"_eq": input.return_date.isoformat()},
            "units_available": {"_gte": 1},
        }
        if input.car_category is not None:
            car_where["category"] = {"_eq": input.car_category.value}

        flights = await _search_catalog(
            info,
            table="flight_offers",
            where=flight_where,
            limit=input.limit,
            offset=0,
            order_by="price: asc",
            allowed_fields=flight_fields,
            selected_fields=flight_fields,
        )
        hotels = await _search_catalog(
            info,
            table="room_offers",
            where=hotel_where,
            limit=input.limit,
            offset=0,
            order_by="price_total: asc",
            allowed_fields=hotel_fields,
            selected_fields=hotel_fields,
        )
        cars = await _search_catalog(
            info,
            table="car_offers",
            where=car_where,
            limit=input.limit,
            offset=0,
            order_by="price_total: asc",
            allowed_fields=car_fields,
            selected_fields=car_fields,
        )

        packages: list[tuple[Decimal, TravelPackage]] = []
        for flight in flights:
            for hotel in hotels:
                for car in cars:
                    flight_price = flight["price"] * input.passengers
                    hotel_price = hotel["price_total"] * input.rooms
                    car_price = car["price_total"]
                    subtotal = flight_price + hotel_price + car_price
                    taxes = (subtotal * settings.tax_rate).quantize(Decimal("0.01"))
                    total = subtotal + taxes
                    if input.max_budget is not None and total > input.max_budget:
                        continue
                    package = TravelPackage(
                        flight=flight,
                        hotel=hotel,
                        car=car,
                        passengers=input.passengers,
                        rooms=input.rooms,
                        estimated_price=PackagePriceBreakdown(
                            flight=flight_price,
                            hotel=hotel_price,
                            car=car_price,
                            subtotal=subtotal,
                            taxes=taxes,
                            total=total,
                        ),
                        currency=str(flight["currency"]),
                    )
                    packages.append((total, package))
        packages.sort(key=lambda item: item[0])
        return [package for _, package in packages[: input.limit]]

    @strawberry.field
    async def flight_offer(
        self,
        info: Info[GatewayContext, None],
        id: strawberry.ID,
    ) -> FlightOffer | None:
        fields = _selection_names(info, {
            "id", "source", "airline", "flight_number", "origin", "destination",
            "departure_at", "arrival_at", "duration_minutes", "cabin_class",
            "price", "currency", "seats_available", "scraped_at",
        })
        return await info.context.flight_offer_loader.load((str(id), tuple(sorted(fields))))

    @strawberry.field
    async def hotel_offer(
        self,
        info: Info[GatewayContext, None],
        id: strawberry.ID,
    ) -> HotelOffer | None:
        fields = _selection_names(info, {
            "id", "source", "hotel_name", "city_code", "address", "stars", "rating",
            "room_type", "max_guests", "check_in", "check_out", "nights",
            "price_per_night", "price_total", "currency", "rooms_available", "scraped_at",
        })
        return await info.context.hotel_offer_loader.load((str(id), tuple(sorted(fields))))

    @strawberry.field
    async def car_offer(
        self,
        info: Info[GatewayContext, None],
        id: strawberry.ID,
    ) -> CarOffer | None:
        fields = _selection_names(info, {
            "id", "source", "company", "model", "category", "transmission", "seats",
            "city_code", "pickup_date", "dropoff_date", "days", "price_per_day",
            "price_total", "currency", "units_available", "scraped_at",
        })
        return await info.context.car_offer_loader.load((str(id), tuple(sorted(fields))))

    @strawberry.field
    async def catalog_status(self, info: Info[GatewayContext, None]) -> list[CatalogSourceStatus]:
        query = """
          query CatalogStatus {
            flights: flight_offers_aggregate {
              aggregate { count max { scraped_at } }
            }
            hotels: room_offers_aggregate {
              aggregate { count max { scraped_at } }
            }
            cars: car_offers_aggregate {
              aggregate { count max { scraped_at } }
            }
          }
        """
        try:
            response = await info.context.request.app.state.http_client.post(
                settings.hasura_graphql_url,
                json={"query": query},
                headers={
                    "X-Hasura-Admin-Secret": settings.hasura_admin_secret.get_secret_value(),
                    "X-Hasura-Role": "gateway",
                    "X-Correlation-ID": getattr(info.context.request.state, "correlation_id", str(uuid4())),
                },
            )
        except httpx.RequestError as error:
            raise GraphQLError("Catalog service is unavailable", extensions={"code": "INTERNAL"}) from error
        if response.is_error:
            raise GraphQLError("Catalog service could not complete the query", extensions={"code": "INTERNAL"})
        try:
            payload = response.json()
        except ValueError as error:
            raise GraphQLError("Catalog service returned invalid data", extensions={"code": "INTERNAL"}) from error
        if not isinstance(payload, dict) or payload.get("errors"):
            raise GraphQLError("Catalog service could not complete the query", extensions={"code": "INTERNAL"})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise GraphQLError("Catalog service returned an invalid response", extensions={"code": "INTERNAL"})
        statuses: list[CatalogSourceStatus] = []
        for catalog, key in (("flights", "flights"), ("hotels", "hotels"), ("cars", "cars")):
            aggregate = data.get(key)
            aggregate_data = aggregate.get("aggregate") if isinstance(aggregate, dict) else None
            if not isinstance(aggregate_data, dict):
                raise GraphQLError("Catalog service returned an invalid response", extensions={"code": "INTERNAL"})
            maximum = aggregate_data.get("max")
            last_sync = maximum.get("scraped_at") if isinstance(maximum, dict) else None
            statuses.append(
                CatalogSourceStatus(
                    catalog=catalog,
                    total_offers=int(aggregate_data.get("count", 0)),
                    last_sync_at=_as_optional_datetime(last_sync),
                )
            )
        return statuses

    @strawberry.field
    async def me(self, info: Info[GatewayContext, None]) -> User | None:
        user = info.context.user
        return _as_user(user) if user is not None else None

    @strawberry.field
    async def order(
        self,
        info: Info[GatewayContext, None],
        id: strawberry.ID,
    ) -> Order | None:
        user = _require_user(info.context)
        response = await _request(
            info.context,
            "GET",
            f"{settings.orders_service_url}/orders/{id}",
            headers={"X-User-ID": str(user["id"])},
        )
        if response.status_code == 404:
            return None
        data = _json_response(response)
        return _as_order(data)

    @strawberry.field
    async def my_orders(
        self,
        info: Info[GatewayContext, None],
        limit: int = 20,
        offset: int = 0,
    ) -> list[Order]:
        user = _require_user(info.context)
        if limit < 1 or limit > settings.graphql_max_limit or offset < 0:
            raise GraphQLError(
                "Invalid pagination parameters",
                extensions={"code": "BAD_USER_INPUT"},
            )
        response = await _request(
            info.context,
            "GET",
            f"{settings.orders_service_url}/orders",
            params={"limit": limit, "offset": offset},
            headers={"X-User-ID": str(user["id"])},
        )
        data = _json_response(response)
        return [_as_order(item) for item in data["items"]]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def register(
        self,
        info: Info[GatewayContext, None],
        input: RegisterInput,
    ) -> AuthPayload:
        _require_csrf(info.context)
        await enforce_rate_limit(
            info.context,
            "register",
            _client_ip(info.context.request),
            settings.rate_limit_register,
        )
        create_response = await _request(
            info.context,
            "POST",
            f"{settings.auth_service_url}/users",
            json={
                "email": input.email,
                "password": input.password,
                "full_name": input.full_name,
            },
        )
        user_data = _json_response(create_response, expected_status=201)
        session = await _create_session(info.context, input.email, input.password)
        info.context.user = session["user"]
        info.context.session_id = str(session["session_id"])
        _set_session_cookie(info.context.response, session["session_id"])
        return AuthPayload(user=_as_user(user_data))

    @strawberry.mutation
    async def login(
        self,
        info: Info[GatewayContext, None],
        input: LoginInput,
    ) -> AuthPayload:
        _require_csrf(info.context)
        await enforce_rate_limit(
            info.context,
            "login",
            _client_ip(info.context.request),
            settings.rate_limit_login,
        )
        session = await _create_session(info.context, input.email, input.password)
        info.context.user = session["user"]
        info.context.session_id = str(session["session_id"])
        _set_session_cookie(info.context.response, session["session_id"])
        return AuthPayload(user=_as_user(session["user"]))

    @strawberry.mutation
    async def logout(self, info: Info[GatewayContext, None]) -> bool:
        _require_csrf(info.context)
        if info.context.session_id:
            await _request(
                info.context,
                "DELETE",
                f"{settings.auth_service_url}/sessions/{info.context.session_id}",
                expected_status=204,
            )
        _delete_session_cookie(info.context.response)
        info.context.user = None
        return True

    @strawberry.mutation
    async def book_package(
        self,
        info: Info[GatewayContext, None],
        input: BookPackageInput,
    ) -> BookPackagePayload:
        _require_csrf(info.context)
        user = _require_user(info.context)
        await enforce_rate_limit(
            info.context,
            "bookPackage",
            str(user["id"]),
            settings.rate_limit_booking,
        )
        failure = input.simulate_failure_at.value if input.simulate_failure_at else None
        response = await _request(
            info.context,
            "POST",
            f"{settings.orders_service_url}/orders",
            json={
                "flight_offer_id": str(input.flight_offer_id),
                "hotel_offer_id": str(input.hotel_offer_id),
                "car_offer_id": str(input.car_offer_id),
                "passengers": input.passengers,
                "rooms": input.rooms,
                "idempotency_key": input.idempotency_key,
                "simulate_failure_at": failure,
            },
            headers={"X-User-ID": str(user["id"])},
            expected_statuses={200, 202},
        )
        return BookPackagePayload(order=_as_order(_json_response(response)))


async def get_context(request: Request, response: Response) -> GatewayContext:
    session_id = request.cookies.get(settings.session_cookie_name)
    context = _new_context(request, response, None, session_id)
    await enforce_rate_limit(
        context,
        "graphql",
        _client_ip(request),
        settings.rate_limit_default,
    )
    user = None
    if session_id:
        validation = await _request(
            context,
            "GET",
            f"{settings.auth_service_url}/sessions/{session_id}",
        )
        if validation.status_code == 404:
            _delete_session_cookie(response)
            session_id = None
        else:
            session_data = _json_response(validation)
            user = session_data["user"]
    context.user = user
    context.session_id = session_id
    return context


def _new_context(
    request: Request,
    response: Response,
    user: dict[str, Any] | None,
    session_id: str | None,
) -> GatewayContext:
    return GatewayContext(
        request=request,
        response=response,
        user=user,
        session_id=session_id,
        flight_offer_loader=_offer_loader(request, "flight_offers"),
        hotel_offer_loader=_offer_loader(request, "room_offers"),
        car_offer_loader=_offer_loader(request, "car_offers"),
    )


def _offer_loader(
    request: Request,
    table: str,
) -> DataLoader[tuple[str, tuple[str, ...]], dict[str, Any] | None]:
    async def load_offers(
        keys: list[tuple[str, tuple[str, ...]]],
    ) -> list[dict[str, Any] | None]:
        ids = list(dict.fromkeys(offer_id for offer_id, _ in keys))
        fields = set().union(*(set(selected) for _, selected in keys))
        fields.add("id")
        if "duration_minutes" in fields:
            fields.update({"arrival_at", "departure_at"})
        columns = " ".join(sorted(fields - {"duration_minutes"}))
        query = f"""
          query GetOffers($ids: [uuid!]!) {{
            {table}(where: {{id: {{_in: $ids}}}}) {{
              {columns}
            }}
          }}
        """
        try:
            response = await request.app.state.http_client.post(
                settings.hasura_graphql_url,
                json={"query": query, "variables": {"ids": ids}},
                headers={
                    "X-Hasura-Admin-Secret": settings.hasura_admin_secret.get_secret_value(),
                    "X-Hasura-Role": "gateway",
                    "X-Correlation-ID": getattr(request.state, "correlation_id", str(uuid4())),
                },
            )
        except httpx.RequestError as error:
            raise GraphQLError(
                "Catalog service is unavailable",
                extensions={"code": "INTERNAL"},
            ) from error
        if response.is_error:
            raise GraphQLError(
                "Catalog service could not complete the query",
                extensions={"code": "INTERNAL"},
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise GraphQLError(
                "Catalog service returned invalid data",
                extensions={"code": "INTERNAL"},
            ) from error
        if not isinstance(payload, dict) or payload.get("errors"):
            raise GraphQLError(
                "Catalog service could not complete the query",
                extensions={"code": "INTERNAL"},
            )
        data = payload.get("data")
        rows = data.get(table) if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise GraphQLError(
                "Catalog service returned an invalid response",
                extensions={"code": "INTERNAL"},
            )
        rows_by_id = {
            str(row["id"]): _hydrate_catalog_row(table, row, fields)
            for row in rows
            if isinstance(row, dict) and "id" in row
        }
        return [rows_by_id.get(offer_id) for offer_id, _ in keys]

    return DataLoader(load_fn=load_offers)


async def _create_session(
    context: GatewayContext,
    email: str,
    password: str,
) -> dict[str, Any]:
    response = await _request(
        context,
        "POST",
        f"{settings.auth_service_url}/sessions",
        json={
            "email": email,
            "password": password,
            "previous_session_id": context.session_id,
            "ip": _client_ip(context.request),
            "user_agent": context.request.headers.get("user-agent"),
        },
        expected_status=201,
    )
    return _json_response(response)


async def _request(
    context: GatewayContext,
    method: str,
    url: str,
    *,
    expected_status: int | None = None,
    expected_statuses: set[int] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}))
    headers["X-Internal-Token"] = settings.internal_api_token.get_secret_value()
    headers.setdefault(
        "X-Correlation-ID",
        getattr(context.request.state, "correlation_id", str(uuid4())),
    )
    try:
        response = await context.request.app.state.http_client.request(
            method, url, headers=headers, **kwargs
        )
    except httpx.RequestError as error:
        raise GraphQLError(
            "An upstream service is unavailable",
            extensions={"code": "INTERNAL"},
        ) from error

    allowed = expected_statuses or ({expected_status} if expected_status is not None else None)
    if allowed is not None and response.status_code not in allowed:
        _raise_service_error(response)
    return response


def _json_response(
    response: httpx.Response,
    *,
    expected_status: int | None = None,
) -> dict[str, Any]:
    if expected_status is not None and response.status_code != expected_status:
        _raise_service_error(response)
    if response.is_error:
        _raise_service_error(response)
    try:
        data = response.json()
    except ValueError as error:
        raise GraphQLError(
            "An upstream service returned an invalid response",
            extensions={"code": "INTERNAL"},
        ) from error
    if not isinstance(data, dict):
        raise GraphQLError(
            "An upstream service returned an invalid response",
            extensions={"code": "INTERNAL"},
        )
    return data


def _raise_service_error(response: httpx.Response) -> None:
    code = {
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "BAD_USER_INPUT",
        429: "RATE_LIMITED",
    }.get(response.status_code, "INTERNAL")
    if response.status_code == 401:
        message = "Invalid credentials"
    elif response.status_code == 409:
        message = "The request conflicts with existing data"
    elif response.status_code == 422:
        message = "The request contains invalid data"
    else:
        message = "The request could not be completed"
    extensions: dict[str, Any] = {"code": code}
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "1")
        extensions["retryAfter"] = int(retry_after)
    raise GraphQLError(message, extensions=extensions)


def _require_user(context: GatewayContext) -> dict[str, Any]:
    if context.user is None:
        raise GraphQLError("Authentication required", extensions={"code": "UNAUTHENTICATED"})
    return context.user


def _require_csrf(context: GatewayContext) -> None:
    if context.request.headers.get("X-WanderSync-CSRF") != "1":
        raise GraphQLError("CSRF validation failed", extensions={"code": "FORBIDDEN"})


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_absolute_timeout_seconds,
        httponly=True,
        secure=settings.session_cookie_secure or settings.environment == "production",
        samesite="strict",
        path="/",
    )


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure or settings.environment == "production",
        httponly=True,
        samesite="strict",
    )


def _as_user(data: dict[str, Any]) -> User:
    return User(
        id=strawberry.ID(str(data["id"])),
        email=str(data["email"]),
        full_name=str(data["full_name"]),
        created_at=_as_datetime(data["created_at"]),
    )


def _as_order(data: dict[str, Any]) -> Order:
    saga_data = data["saga"]
    saga = Saga(
        id=strawberry.ID(str(saga_data["id"])),
        status=SagaStatus(str(saga_data["status"])),
        current_step=(
            SagaStepName(str(saga_data["current_step"]))
            if saga_data.get("current_step") is not None else None
        ),
        failure_reason=saga_data.get("failure_reason"),
        simulate_failure_at=(
            FailurePoint(str(saga_data["simulate_failure_at"]))
            if saga_data.get("simulate_failure_at") is not None else None
        ),
        steps=[
            SagaStep(
                step=SagaStepName(str(step["step"])),
                action=SagaAction(str(step["action"])),
                status=SagaStepStatus(str(step["status"])),
                attempt=int(step["attempt"]),
                error_code=step.get("error_code"),
                error_message=step.get("error_message"),
                started_at=_as_datetime(step["started_at"]),
                finished_at=_as_optional_datetime(step.get("finished_at")),
            )
            for step in saga_data["steps"]
        ],
    )
    payment_data = data.get("payment")
    invoice_data = data.get("invoice")
    return Order(
        id=strawberry.ID(str(data["id"])),
        status=OrderStatus(str(data["status"])),
        flight_offer_id=str(data["flight_offer_id"]),
        hotel_offer_id=str(data["hotel_offer_id"]),
        car_offer_id=str(data["car_offer_id"]),
        passengers=int(data["passengers"]),
        rooms=int(data["rooms"]),
        subtotal=_as_optional_decimal(data.get("subtotal")),
        taxes=_as_optional_decimal(data.get("taxes")),
        total_amount=_as_optional_decimal(data.get("total_amount")),
        currency=str(data["currency"]),
        saga=saga,
        payment=(
            Payment(
                status=PaymentStatus(str(payment_data["status"])),
                amount=Decimal(str(payment_data["amount"])),
                currency=str(payment_data["currency"]),
                provider_ref=payment_data.get("provider_ref"),
            )
            if payment_data is not None else None
        ),
        invoice=(
            Invoice(
                number=str(invoice_data["number"]),
                subtotal=Decimal(str(invoice_data["subtotal"])),
                taxes=Decimal(str(invoice_data["taxes"])),
                total=Decimal(str(invoice_data["total"])),
                currency=str(invoice_data["currency"]),
                issued_at=_as_datetime(invoice_data["issued_at"]),
            )
            if invoice_data is not None else None
        ),
        created_at=_as_datetime(data["created_at"]),
        updated_at=_as_datetime(data["updated_at"]),
    )


def _as_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _as_optional_datetime(value: str | datetime | None) -> datetime | None:
    return _as_datetime(value) if value is not None else None


def _as_optional_decimal(value: str | Decimal | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


async def _search_catalog(
    info: Info[GatewayContext, None],
    *,
    table: str,
    where: dict[str, Any],
    limit: int,
    offset: int,
    order_by: str,
    allowed_fields: set[str],
    selected_fields: set[str] | None = None,
) -> list[dict[str, Any]]:
    if limit < 1 or limit > settings.graphql_max_limit or offset < 0:
        raise GraphQLError("Invalid pagination parameters", extensions={"code": "BAD_USER_INPUT"})

    selected = selected_fields or {
        _camel_to_snake(field.name)
        for field in info.selected_fields[0].selections
        if _camel_to_snake(field.name) in allowed_fields
    }
    query_fields = set(selected)
    if "duration_minutes" in query_fields:
        query_fields.update({"arrival_at", "departure_at"})
        query_fields.discard("duration_minutes")
    if not query_fields:
        raise GraphQLError("At least one offer field must be selected", extensions={"code": "BAD_USER_INPUT"})

    columns = " ".join(sorted(query_fields))
    query = f"""
      query SearchOffers($where: {table}_bool_exp!, $limit: Int!, $offset: Int!) {{
        {table}(where: $where, limit: $limit, offset: $offset, order_by: {{{order_by}}}) {{
          {columns}
        }}
      }}
    """
    request = info.context.request
    headers = {
        "X-Hasura-Admin-Secret": settings.hasura_admin_secret.get_secret_value(),
        "X-Hasura-Role": "gateway",
        "X-Correlation-ID": getattr(request.state, "correlation_id", str(uuid4())),
    }
    try:
        response = await request.app.state.http_client.post(
            settings.hasura_graphql_url,
            json={
                "query": query,
                "variables": {"where": where, "limit": limit, "offset": offset},
            },
            headers=headers,
        )
    except httpx.RequestError as error:
        raise GraphQLError("Catalog service is unavailable", extensions={"code": "INTERNAL"}) from error

    if response.is_error:
        raise GraphQLError("Catalog service could not complete the query", extensions={"code": "INTERNAL"})
    try:
        payload = response.json()
    except ValueError as error:
        raise GraphQLError("Catalog service returned invalid data", extensions={"code": "INTERNAL"}) from error
    if not isinstance(payload, dict) or payload.get("errors"):
        raise GraphQLError("Catalog service could not complete the query", extensions={"code": "INTERNAL"})
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get(table), list):
        raise GraphQLError("Catalog service returned an invalid response", extensions={"code": "INTERNAL"})

    return [
        _hydrate_catalog_row(table, row, selected)
        for row in data[table]
        if isinstance(row, dict)
    ]


def _hydrate_catalog_row(
    table: str,
    row: dict[str, Any],
    selected: set[str],
) -> dict[str, Any]:
    hydrated = dict(row)
    decimal_fields = {
        "flight_offers": {"price"},
        "room_offers": {"price_per_night", "price_total"},
        "car_offers": {"price_per_day", "price_total"},
    }[table]
    datetime_fields = {
        "flight_offers": {"departure_at", "arrival_at", "scraped_at"},
        "room_offers": {"scraped_at"},
        "car_offers": {"scraped_at"},
    }[table]
    date_fields = {
        "flight_offers": set(),
        "room_offers": {"check_in", "check_out"},
        "car_offers": {"pickup_date", "dropoff_date"},
    }[table]

    for field in decimal_fields.intersection(hydrated):
        hydrated[field] = Decimal(str(hydrated[field]))
    for field in datetime_fields.intersection(hydrated):
        hydrated[field] = _as_datetime(hydrated[field])
    for field in date_fields.intersection(hydrated):
        hydrated[field] = date.fromisoformat(str(hydrated[field]))
    if "duration_minutes" in selected:
        hydrated["duration_minutes"] = int(
            (hydrated["arrival_at"] - hydrated["departure_at"]).total_seconds() // 60
        )
    return hydrated


def _camel_to_snake(value: str) -> str:
    output: list[str] = []
    for character in value:
        if character.isupper():
            output.extend(("_", character.lower()))
        else:
            output.append(character)
    return "".join(output).lstrip("_")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _default_resolver(root: Any, field_name: str) -> Any:
    # Los resolvers devuelven diccionarios con SOLO los campos pedidos a Hasura (sin
    # over-fetching); Strawberry por defecto lee atributos, así que se acepta también un dict.
    if isinstance(root, dict):
        return root.get(field_name)
    return getattr(root, field_name)


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    scalar_overrides={Decimal: DecimalScalar},
    config=StrawberryConfig(default_resolver=_default_resolver),
)
