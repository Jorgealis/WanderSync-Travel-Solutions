"""Pruebas de seguridad automatizadas (tarea 5.3) contra el stack REAL.

Cubren los requisitos de "Ciberseguridad por diseño" del enunciado:
- Session Fixation: el ID de sesión SIEMPRE se regenera tras autenticarse y el anterior deja
  de servir; logout invalida la sesión en el servidor; cookie HttpOnly + SameSite=Strict.
- Contraseñas con Argon2id (parámetros de alto costo) y política de longitud mínima.
- Rate limiting en login (por IP), checkout (por usuario) y pago en orders-service (5.2).
- Además: CSRF, autorización entre usuarios, no enumeración de usuarios, límite de
  profundidad de las consultas y cabeceras de seguridad.

Se ejecutan con:  python scripts/run_service_tests.py security
(contenedor conectado a las redes `backend` y `frontend`). Cada prueba usa su propia IP de
cliente (X-Forwarded-For directo al gateway) para que los límites no interfieran entre sí.
"""

import os
import random
import uuid

import httpx
import psycopg
import pytest

GATEWAY = os.environ.get("GATEWAY_URL", "http://api-gateway:8000/graphql")
FRONTEND = os.environ.get("FRONTEND_URL", "http://frontend:8080")
ORDERS = os.environ.get("ORDERS_URL", "http://orders-service:8000")
COOKIE = os.environ.get("SESSION_COOKIE_NAME", "ws_session")
CSRF = {"X-WanderSync-CSRF": "1"}

REGISTER = "mutation($i: RegisterInput!){ register(input:$i){ user{ id email } } }"
LOGIN = "mutation($i: LoginInput!){ login(input:$i){ user{ id email } } }"
LOGOUT = "mutation{ logout }"
ME = "{ me { id email } }"
BOOK = "mutation($i: BookPackageInput!){ bookPackage(input:$i){ order{ id status } } }"


class Client:
    """Cliente GraphQL con una IP de origen propia y la cookie de sesión manejada a mano."""

    def __init__(self, url: str = GATEWAY, ip: str | None = None) -> None:
        self.url = url
        self.ip = ip or f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        self.http = httpx.Client(timeout=20)

    def gql(self, query, variables=None, *, csrf=True, session=None, extra_headers=None):
        headers = {"X-Forwarded-For": self.ip, **(CSRF if csrf else {}), **(extra_headers or {})}
        if session is not None:
            headers["Cookie"] = f"{COOKIE}={session}"
        response = self.http.post(self.url, json={"query": query, "variables": variables or {}}, headers=headers)
        return response.json(), response

    @staticmethod
    def new_session(response: httpx.Response) -> str | None:
        """El último ID de sesión no vacío que fija la respuesta (la primera puede ser un borrado)."""
        values = [h.split(";")[0].split("=", 1)[1] for h in response.headers.get_list("set-cookie")
                  if h.startswith(f"{COOKIE}=")]
        return next((v for v in reversed(values) if v and v != '""'), None)

    def me(self, session: str | None) -> dict | None:
        data, _ = self.gql(ME, session=session, csrf=False)
        return (data.get("data") or {}).get("me")


def code(payload: dict) -> str | None:
    errors = payload.get("errors") or []
    return errors[0].get("extensions", {}).get("code") if errors else None


@pytest.fixture
def account():
    email = f"sec-{uuid.uuid4().hex[:10]}@example.com"
    password = f"Segura-{uuid.uuid4().hex[:12]}"
    data, _ = Client().gql(REGISTER, {"i": {"email": email, "password": password, "fullName": "Prueba Seguridad"}})
    assert not data.get("errors"), data
    return email, password


def login(client: Client, email: str, password: str, session: str | None = None) -> str:
    data, response = client.gql(LOGIN, {"i": {"email": email, "password": password}}, session=session)
    assert not data.get("errors"), data
    sid = Client.new_session(response)
    assert sid
    return sid


# --------------------------------------------------------------------------- contraseñas

def test_password_stored_with_argon2id(account):
    email, password = account
    with psycopg.connect(host=os.environ.get("POSTGRES_HOST", "postgres"), dbname=os.environ.get("POSTGRES_DB", "wandersync"),
                         user=os.environ["AUTH_DB_USER"], password=os.environ["AUTH_DB_PASSWORD"]) as conn:
        (stored,) = conn.execute("SELECT password_hash FROM auth.users WHERE email = %s", (email,)).fetchone()
    assert stored.startswith("$argon2id$v=19$m=65536,t=3,p=4$")  # Argon2id, 64 MiB, 3 iteraciones, 4 hilos
    assert password not in stored


def test_short_password_rejected():
    data, _ = Client().gql(REGISTER, {"i": {"email": f"x-{uuid.uuid4().hex[:8]}@example.com", "password": "corta123", "fullName": "X"}})
    assert code(data) == "BAD_USER_INPUT"


# --------------------------------------------------------------------------- sesiones

def test_session_fixation_planted_id_is_replaced(account):
    client = Client()
    planted = "SESION-FIJADA-POR-UN-ATACANTE"
    new = login(client, *account, session=planted)
    assert new != planted and len(new) >= 43  # secrets.token_urlsafe(32)
    assert client.me(planted) is None
    assert client.me(new)["email"] == account[0]


def test_each_login_rotates_and_revokes_previous_session(account):
    client = Client()
    first = login(client, *account)
    second = login(client, *account, session=first)  # el navegador envía la cookie anterior
    assert first != second
    assert client.me(first) is None
    assert client.me(second) is not None


def test_logout_invalidates_session_server_side(account):
    client = Client()
    sid = login(client, *account)
    data, _ = client.gql(LOGOUT, session=sid)
    assert data["data"]["logout"] is True
    assert client.me(sid) is None  # aunque el cliente conserve la cookie, ya no sirve


def test_session_cookie_flags(account):
    _, response = Client().gql(LOGIN, {"i": {"email": account[0], "password": account[1]}})
    cookie = next(h for h in reversed(response.headers.get_list("set-cookie")) if h.split(";")[0].split("=", 1)[1] not in ("", '""'))
    attributes = cookie.lower()
    assert "httponly" in attributes
    assert "samesite=strict" in attributes
    assert "path=/" in attributes


# --------------------------------------------------------------------------- CSRF, autorización y enumeración

def test_mutations_require_csrf_header(account):
    data, _ = Client().gql(LOGIN, {"i": {"email": account[0], "password": account[1]}}, csrf=False)
    assert code(data) == "FORBIDDEN"


def test_no_user_enumeration_on_login(account):
    client = Client()
    wrong_password, _ = client.gql(LOGIN, {"i": {"email": account[0], "password": "otra-contrasena-123"}})
    unknown_user, _ = client.gql(LOGIN, {"i": {"email": f"nadie-{uuid.uuid4().hex[:8]}@example.com", "password": "otra-contrasena-123"}})
    assert code(wrong_password) == code(unknown_user) == "UNAUTHENTICATED"
    assert wrong_password["errors"][0]["message"] == unknown_user["errors"][0]["message"]


def test_orders_are_private_between_users(account):
    owner = Client()
    owner_session = login(owner, *account)
    booked, _ = owner.gql(BOOK, {"i": {"flightOfferId": str(uuid.uuid4()), "hotelOfferId": str(uuid.uuid4()), "carOfferId": str(uuid.uuid4()),
                                       "passengers": 1, "rooms": 1, "idempotencyKey": str(uuid.uuid4())}}, session=owner_session)
    order_id = booked["data"]["bookPackage"]["order"]["id"]

    other_email, other_password = f"otro-{uuid.uuid4().hex[:8]}@example.com", f"Segura-{uuid.uuid4().hex[:12]}"
    intruder = Client()
    intruder.gql(REGISTER, {"i": {"email": other_email, "password": other_password, "fullName": "Otro"}})
    intruder_session = login(intruder, other_email, other_password)
    data, _ = intruder.gql("query($id: ID!){ order(id:$id){ id } }", {"id": order_id}, session=intruder_session, csrf=False)
    assert (data.get("data") or {}).get("order") is None  # no puede ver la orden ajena
    mine, _ = intruder.gql("{ myOrders { id } }", session=intruder_session, csrf=False)
    assert order_id not in [o["id"] for o in mine["data"]["myOrders"]]

    anonymous, _ = Client().gql("{ myOrders { id } }", csrf=False)
    assert code(anonymous) == "UNAUTHENTICATED"


# --------------------------------------------------------------------------- rate limiting

def test_login_rate_limited_per_ip(account):
    client = Client()
    results = [client.gql(LOGIN, {"i": {"email": account[0], "password": "incorrecta-123456"}}) for _ in range(6)]
    codes = [code(data) for data, _ in results]
    assert codes[:5] == ["UNAUTHENTICATED"] * 5
    assert codes[5] == "RATE_LIMITED"
    data, response = results[5]
    assert data["errors"][0]["extensions"]["retryAfter"] > 0
    assert int(response.headers["Retry-After"]) > 0

    # El límite es por cliente: otra IP puede seguir entrando con la contraseña correcta.
    assert login(Client(), *account)


def test_spoofed_forwarded_for_through_nginx_does_not_bypass_limit(account):
    # Nginx REEMPLAZA X-Forwarded-For con la IP real: falsificarla no da un contador nuevo.
    web = httpx.Client(timeout=20)
    codes = []
    for _ in range(7):
        response = web.post(f"{FRONTEND}/graphql", headers={**CSRF, "X-Forwarded-For": f"203.0.113.{random.randint(1, 254)}"},
                            json={"query": LOGIN, "variables": {"i": {"email": account[0], "password": "incorrecta-123456"}}})
        codes.append(code(response.json()))
    assert "RATE_LIMITED" in codes


def test_checkout_rate_limited_per_user(account):
    client = Client()
    sid = login(client, *account)
    codes = []
    for _ in range(4):
        data, _ = client.gql(BOOK, {"i": {"flightOfferId": str(uuid.uuid4()), "hotelOfferId": str(uuid.uuid4()), "carOfferId": str(uuid.uuid4()),
                                          "passengers": 1, "rooms": 1, "idempotencyKey": str(uuid.uuid4())}}, session=sid)
        codes.append(code(data))
    assert codes == [None, None, None, "RATE_LIMITED"]  # RATE_LIMIT_BOOKING = 3/minute


def test_payment_rate_limited_in_orders_service():
    # Defensa en profundidad (5.2): aunque se saltara el gateway, orders-service limita por usuario.
    user = str(uuid.uuid4())
    headers = {"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"], "X-User-ID": user}
    statuses = []
    with httpx.Client(timeout=20) as http:
        for _ in range(11):
            response = http.post(f"{ORDERS}/orders", headers=headers, json={
                "flight_offer_id": str(uuid.uuid4()), "hotel_offer_id": str(uuid.uuid4()), "car_offer_id": str(uuid.uuid4()),
                "passengers": 1, "rooms": 1, "idempotency_key": str(uuid.uuid4())})
            statuses.append(response.status_code)
    assert statuses[:10] == [202] * 10
    assert statuses[10] == 429  # RATE_LIMIT_PAYMENT = 10/minute


# --------------------------------------------------------------------------- superficie

def test_query_depth_limit():
    deep = "{ __schema { types { fields { type { ofType { ofType { ofType { ofType { name } } } } } } } } }"
    data, _ = Client().gql(deep, csrf=False)
    assert data.get("errors") and "depth" in data["errors"][0]["message"].lower()


def test_security_headers():
    _, gateway = Client().gql(ME, csrf=False)
    page = httpx.get(f"{FRONTEND}/search", timeout=20)
    for response in (gateway, page):
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in page.headers["Content-Security-Policy"]
