
# Smart Parking API — Implementation-Synced Spec

This spec mirrors the current implementation (v5.3) with **implicit tenant scoping**:
- Paths do **not** include `/tenants/{tenant_id}`; tenant is derived from auth.
- Endpoints present here are those that exist in code today per the compliance report.

## Validate
```bash
npm i -g @stoplight/spectral-cli
spectral lint docs/api/smart-parking-openapi.yaml -r docs/api/spectral.yaml
```

## View
Open `docs/api/redoc.html` next to the YAML.
