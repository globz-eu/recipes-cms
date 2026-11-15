# Spec: bulk upload size limits (recipes-cms #10)

Oversize bulk uploads must fail with the API's own JSON error, not a proxy error page.

### Intent
- One limit, `MAX_UPLOAD_SIZE` (5 MiB), for both input forms of `POST /api/recipes/bulk-upload/`.
- Proxies in front of Django allow at least that much, so Django's error is what clients see.

### Findings (today)
- Multipart `file`: `load_json_upload` refuses > 5 MiB with 400; no test covers it.
- Raw JSON body: no limit; DRF streams it, so `DATA_UPLOAD_MAX_MEMORY_SIZE` does not apply.
- Dev nginx (recipes-infrastructure `dev/config/nginx/nginx.conf.template`): `client_max_body_size 50m` on `location /`.
- Docker, gunicorn: no body limit.
- Staging (Scaleway Serverless Container, no nginx): no documented request body limit.

### Goals
- Raw JSON body over `MAX_UPLOAD_SIZE` refused before parsing, from `Content-Length`.
- Both paths answer 413 with a JSON error naming the limit in bytes.
- Tests for both paths: just under and just over the limit.
- README "Bulk recipe upload": state the limit, the 413 and each layer's allowance.

### Non-goals
- No change to nginx, gunicorn or Scaleway config; 50 MB nginx stays as outer safety net.
- No site-wide `DATA_UPLOAD_MAX_MEMORY_SIZE` change.

### Approaches
- **Chosen:** `Content-Length` check in the bulk-upload view; endpoint-local, reads nothing; chunked bodies arrive empty in DRF and fail validation.
- Size-capped JSON parser: robust without headers, but new class and `{"detail"}` error shape.
- `DATA_UPLOAD_MAX_MEMORY_SIZE` + `request.body`: site-wide, Django's HTML 400 instead of API JSON.

### Decided
- 413 for both paths (file path changes from 400); no caller depends on 400 yet.

### Left to the builder
- Error body shape for the raw-body case (stay close to the file error's `{"file": [...]}`).
- Where the check lives (view or a small helper in `serializers.py`).
