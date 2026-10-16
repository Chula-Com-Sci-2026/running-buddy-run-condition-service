# Run Conditions

Live Open-Meteo/CAMS forecast and air-quality adapters, suitability, 15-minute Redis cache and bounded stale fallback.

Local Deliverable 4 implementation. Separate Git repository; API/event contracts and environment configuration allow a compatible teammate service to replace this one.

## Run

Python 3.13 and pinned dependencies. Build with `docker build -t cra-conditions .`. The integrated startup and isolated test database provisioning are documented in `../local-integration/README.md`:

```sh
cd ../local-integration
python3 scripts/init-env.py
docker compose up -d --build
./scripts/test-services.sh
```

The Compose service is `conditions`. It listens on port 8000 inside the private local network. Database: **Redis**. Every protected route validates its bearer token and performs ownership checks. JWT secret, database credentials and service addresses come from the environment; `.env` is ignored. The gateway publishes only its loopback port to the host.

## API and tests

FastAPI exposes `/openapi.json` and `/docs`. The exported contract is `../local-integration/contracts/conditions.openapi.json`. `/up` checks database connectivity when PostgreSQL is configured. Run Conditions additionally exposes `/ready` for Redis readiness.

Tests are in `test_*.py`; run `pytest -q` with this service's test database and required environment variables. PostgreSQL tests require a separately created service-owned `*_test` database and run real SQL migrations automatically. Run Conditions tests require a dedicated Redis database (integration uses database 15). Never point tests at demo/production data. Gateway test stubs are generated in its Docker build from its checked-in `.proto` copy. Full running-stack tests live in `local-integration/scripts/check_flows.py`.

Only the scoped delivery operations are implemented. Deferred product features are listed in `../docs/plans/deliverable-4-implementation-plan.md`; they must not be claimed as implemented. OTP uses an explicitly labeled console delivery adapter, not live SMS. Provider fixtures appear only in focused tests and the labeled prepared past run; integrated forecast calls use the live provider.
