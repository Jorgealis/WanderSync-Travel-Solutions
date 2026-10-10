import os
import time
from collections.abc import Iterator
from uuid import uuid4

import httpx
import pytest

GRAPHQL_URL = os.getenv("WANDERSYNC_GATEWAY_URL", "http://127.0.0.1:3000/graphql")
EMAIL = os.getenv("WANDERSYNC_E2E_EMAIL")
PASSWORD = os.getenv("WANDERSYNC_E2E_PASSWORD")
FLIGHT_OFFER_ID = os.getenv("WANDERSYNC_E2E_FLIGHT_OFFER_ID")
HOTEL_OFFER_ID = os.getenv("WANDERSYNC_E2E_HOTEL_OFFER_ID")
CAR_OFFER_ID = os.getenv("WANDERSYNC_E2E_CAR_OFFER_ID")
PASSENGERS = int(os.getenv("WANDERSYNC_E2E_PASSENGERS", "1"))
ROOMS = int(os.getenv("WANDERSYNC_E2E_ROOMS", "1"))
TIMEOUT_SECONDS = float(os.getenv("WANDERSYNC_E2E_TIMEOUT_SECONDS", "120"))
CSRF_HEADERS = {"X-WanderSync-CSRF": "1"}

LOGIN = """
mutation Login($input: LoginInput!) {
  login(input: $input) {
    user { id }
  }
}
"""

SNAPSHOT = """
query OfferInventory($flightId: ID!, $hotelId: ID!, $carId: ID!) {
  flightOffer(id: $flightId) { id seatsAvailable }
  hotelOffer(id: $hotelId) { id roomsAvailable }
  carOffer(id: $carId) { id unitsAvailable }
}
"""

BOOK_PACKAGE = """
mutation BookPackage($input: BookPackageInput!) {
  bookPackage(input: $input) {
    order {
      id
      status
      saga { status steps { step action status } }
    }
  }
}
"""

ORDER = """
query Order($id: ID!) {
  order(id: $id) {
    id
    status
    saga { status steps { step action status } }
  }
}
"""


def _required_configuration() -> list[str]:
    values = {
        "WANDERSYNC_E2E_EMAIL": EMAIL,
        "WANDERSYNC_E2E_PASSWORD": PASSWORD,
        "WANDERSYNC_E2E_FLIGHT_OFFER_ID": FLIGHT_OFFER_ID,
        "WANDERSYNC_E2E_HOTEL_OFFER_ID": HOTEL_OFFER_ID,
        "WANDERSYNC_E2E_CAR_OFFER_ID": CAR_OFFER_ID,
    }
    return [name for name, value in values.items() if not value]


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    missing = _required_configuration()
    if missing:
        pytest.skip("Set E2E configuration variables: " + ", ".join(missing))

    with httpx.Client(timeout=15.0) as http:
        response = http.post(
            GRAPHQL_URL,
            headers=CSRF_HEADERS,
            json={
                "query": LOGIN,
                "variables": {"input": {"email": EMAIL, "password": PASSWORD}},
            },
        )
        payload = response.json()
        assert response.is_success, f"Gateway login returned HTTP {response.status_code}"
        assert not payload.get("errors"), f"Gateway login failed: {payload.get('errors')}"
        yield http


def _graphql(
    client: httpx.Client,
    query: str,
    variables: dict[str, object],
) -> tuple[dict[str, object] | None, list[dict[str, object]], httpx.Headers]:
    response = client.post(
        GRAPHQL_URL,
        headers=CSRF_HEADERS,
        json={"query": query, "variables": variables},
    )
    assert response.is_success, f"Gateway returned HTTP {response.status_code}"
    payload = response.json()
    return payload.get("data"), payload.get("errors", []), response.headers


def _inventory(client: httpx.Client) -> dict[str, int]:
    data, errors, _ = _graphql(
        client,
        SNAPSHOT,
        {
            "flightId": FLIGHT_OFFER_ID,
            "hotelId": HOTEL_OFFER_ID,
            "carId": CAR_OFFER_ID,
        },
    )
    assert not errors, f"Could not read offer inventory: {errors}"
    assert data is not None
    flight = data["flightOffer"]
    hotel = data["hotelOffer"]
    car = data["carOffer"]
    assert flight is not None and hotel is not None and car is not None, (
        "One or more configured offer IDs are missing from the catalog"
    )
    return {
        "flight": int(flight["seatsAvailable"]),
        "hotel": int(hotel["roomsAvailable"]),
        "car": int(car["unitsAvailable"]),
    }


def _book(
    client: httpx.Client,
    failure_at: str | None,
) -> dict[str, object]:
    idempotency_key = str(uuid4())
    variables = {
        "input": {
            "flightOfferId": FLIGHT_OFFER_ID,
            "hotelOfferId": HOTEL_OFFER_ID,
            "carOfferId": CAR_OFFER_ID,
            "passengers": PASSENGERS,
            "rooms": ROOMS,
            "idempotencyKey": idempotency_key,
            "simulateFailureAt": failure_at,
        }
    }
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        data, errors, headers = _graphql(client, BOOK_PACKAGE, variables)
        if not errors:
            assert data is not None
            return data["bookPackage"]["order"]

        error = errors[0]
        extensions = error.get("extensions", {})
        if extensions.get("code") != "RATE_LIMITED":
            pytest.fail(f"bookPackage failed: {errors}")

        retry_after = int(extensions.get("retryAfter", headers.get("Retry-After", "1")))
        if time.monotonic() + retry_after >= deadline:
            pytest.fail("Rate limit retry exceeded the E2E timeout")
        time.sleep(retry_after + 0.1)


def _wait_for_terminal_order(
    client: httpx.Client,
    order_id: str,
) -> dict[str, object]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        data, errors, _ = _graphql(client, ORDER, {"id": order_id})
        assert not errors, f"Could not read order {order_id}: {errors}"
        assert data is not None
        order = data["order"]
        assert order is not None, f"Order {order_id} was not found"
        if order["status"] in {"CONFIRMED", "CANCELLED", "FAILED"}:
            return order
        time.sleep(0.5)
    pytest.fail(f"Order {order_id} did not reach a terminal state")


def test_saga_happy_path_and_compensations(client: httpx.Client) -> None:
    scenarios = (
        (None, "CONFIRMED", "COMPLETED"),
        ("HOTEL", "CANCELLED", "COMPENSATED"),
        ("CAR", "CANCELLED", "COMPENSATED"),
        ("PAYMENT", "CANCELLED", "COMPENSATED"),
    )

    for failure_at, expected_order_status, expected_saga_status in scenarios:
        before = _inventory(client)
        assert before["flight"] >= PASSENGERS, "Not enough flight seats for this test"
        assert before["hotel"] >= ROOMS, "Not enough hotel rooms for this test"
        assert before["car"] >= 1, "No car units are available for this test"

        created_order = _book(client, failure_at)
        order = _wait_for_terminal_order(client, str(created_order["id"]))
        assert order["status"] == expected_order_status
        assert order["saga"]["status"] == expected_saga_status

        after = _inventory(client)
        if failure_at is None:
            assert after == {
                "flight": before["flight"] - PASSENGERS,
                "hotel": before["hotel"] - ROOMS,
                "car": before["car"] - 1,
            }, "Successful booking did not consume the expected inventory"
        else:
            assert after == before, (
                f"Inventory was not restored after simulated {failure_at} failure: "
                f"before={before}, after={after}"
            )
