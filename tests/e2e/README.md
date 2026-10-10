# Rol A SAGA end-to-end test

The test exercises the public GraphQL gateway, authentication, order creation,
the SAGA, and catalog inventory. It needs a running local stack, an existing
WanderSync account, and one available flight, hotel, and car offer.

Configure these PowerShell environment variables with values from the local
development environment. Do not commit credentials or a `.env` file:

```powershell
$env:WANDERSYNC_GATEWAY_URL = "http://127.0.0.1:3000/graphql"  # el frontend (Nginx) reenvía /graphql al gateway
$env:WANDERSYNC_E2E_EMAIL = "your-existing-account@example.com"
$env:WANDERSYNC_E2E_PASSWORD = "your-local-password"
$env:WANDERSYNC_E2E_FLIGHT_OFFER_ID = "flight-offer-uuid"
$env:WANDERSYNC_E2E_HOTEL_OFFER_ID = "hotel-offer-uuid"
$env:WANDERSYNC_E2E_CAR_OFFER_ID = "car-offer-uuid"
```

Set `ENABLE_FAULT_INJECTION=true` for `orders-service`, `flights-service`,
`hotels-service`, and `cars-service` in the local `.env`, then restart the
stack. The test runs a successful booking and simulated failures at the hotel,
car, and payment steps. It verifies the terminal order/SAGA statuses and that
failed bookings restore the catalog inventory. The successful booking
permanently consumes the selected offers' inventory.

Install the test-only dependencies and run it from the repository root:

```powershell
python -m pip install -r tests\e2e\requirements.txt
python -m pytest -v tests\e2e\test_saga.py
```

When the required configuration variables are absent, pytest reports the
test as skipped. Use offers with enough available inventory for the passenger
and room counts configured by `WANDERSYNC_E2E_PASSENGERS` and
`WANDERSYNC_E2E_ROOMS` (both default to `1`).
