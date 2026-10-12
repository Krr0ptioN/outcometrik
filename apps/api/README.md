# API

Django REST Framework API managed with uv. The runtime uses PostgreSQL and Redis through the repository Compose stack.

```sh
pnpm nx run api:sync
pnpm nx serve api
```

For a complete local database-backed stack:

```sh
./tools/compose-up.sh
```

The only health endpoint is `/api/health/status`. It returns only `{ "status": "ok" }` or `{ "status": "unavailable" }`; dependency details are intentionally not exposed. For isolated local tests without PostgreSQL, set `DJANGO_DB_ENGINE=django.db.backends.sqlite3`.
