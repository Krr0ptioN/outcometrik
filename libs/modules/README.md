# Django modules

Reusable Django apps and shared Python libraries are kept here. Add each module as a local path dependency of `apps/api` when it is created.

`access/` provides the `outcometrik-access` local Python package. The API declares
it as an editable uv path dependency, registers `access` in `INSTALLED_APPS`, and
runs its tests and lint through the API Nx targets. The `api-access` Nx library
is an implicit dependency of `api`, so library changes invalidate API caches. See
[the API authorization contract](../../apps/api/README.md#scoped-authorization-auth-01).
Backend container builds use the repository root as context so local libraries
are included. Compose mounts both the API and the access package for development.
