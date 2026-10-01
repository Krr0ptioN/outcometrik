# GitHub automation

`workflows/ci.yml` validates pull requests with isolated lint, unit-test, build, and end-to-end jobs. `workflows/cd.yml` deploys only after successful CI on `main`.

Configure repository settings to require CI, allow squash merges only, and set squash as the default merge option. These settings cannot be enforced by repository files alone.
