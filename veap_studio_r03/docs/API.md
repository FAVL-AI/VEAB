# VEAP Studio R0.3 API

The API binds to the local machine and supports an optional `x-veap-token` header when `VEAP_STUDIO_TOKEN` is set.

- `GET /api/health` — software boundary declaration.
- `GET /api/integrations` — local runtime availability, not native execution validity.
- `GET /api/assets`, `POST /api/assets`, `GET /api/inbox`, `POST /api/inbox/import` — bounded original evidence and staging.
- `GET /api/traces/{asset_id}`, `POST /api/compare`, `POST /api/counterfactual` — trajectory parsing and analytic comparisons.
- `POST /api/jobs` (`kind`: `mujoco_fall`, `isaac_fall`, `mcap_decode`, `lerobot_dataset`, `scene_export`) — bounded local jobs.
- `GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/artifact/{name}` — persisted local job status and scoped artifacts.
- `POST /api/physics/compare` — compare completed native Isaac and MuJoCo 3D state traces using their job IDs.
- `GET /api/contracts`, `POST /api/contracts`, `POST /api/contracts/{id}/evaluate/{asset_id}` — versioned recorded 2D contracts and separate-process monitor verdicts.

Example:

```bash
curl -X POST http://127.0.0.1:8765/api/jobs \
  -H 'Content-Type: application/json' -H "x-veap-token: $VEAP_STUDIO_TOKEN" \
  -d '{"kind":"scene_export"}'
```

Run endpoints do not take arbitrary executable filenames, shell commands, robot addresses, motion commands or unbounded timeouts. The native workers are fixed source-controlled experiments.
