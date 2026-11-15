# Plan: bulk upload size limits (recipes-cms #10)

Spec: [bulk-upload-size-limits.spec.md](bulk-upload-size-limits.spec.md)

## Context
- `MAX_UPLOAD_SIZE` is enforced only for multipart files (`serializers.py:147`, 400, untested).
- Raw JSON bodies hit Django's `DATA_UPLOAD_MAX_MEMORY_SIZE` (2.5 MiB default, HTML 400): DRF reads `request.body`.
- nginx (50m), gunicorn and Scaleway need no change.

## Design
- `settings/base.py`: `DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024`; `MAX_UPLOAD_SIZE = settings.DATA_UPLOAD_MAX_MEMORY_SIZE`.
- Add `PayloadTooLarge(APIException)` in `serializers.py`: `status_code = 413`, `default_code = "payload_too_large"`.
- Verified: DRF `exception_handler` returns a dict/list `detail` unchanged as the body, with `exc.status_code`.
- `APIException(detail=dict)` wraps values in `ErrorDetail`; they serialise as plain strings.
- File path body: `{"file": ["File too large; the maximum is 5242880 bytes."]}`.
- Raw path: same shape with key `"body"` instead of `"file"`.
- Add `check_body_size(content_length: str | None)` in `serializers.py`; the view passes `request.META.get("CONTENT_LENGTH")`.
- Run it only when `request.content_type` is JSON, before `request.data` is touched (DRF parses lazily).
- Multipart is not checked on `Content-Length`: envelope overhead would reject a file just under the limit.
- Missing, empty or non-numeric `Content-Length` passes; chunked bodies arrive empty and fail validation.

## Acceptance criteria
1. Multipart file over `MAX_UPLOAD_SIZE` returns 413 with `{"file": [...]}` naming the bytes.
2. Raw JSON body over `MAX_UPLOAD_SIZE` returns 413 with `{"body": [...]}`, without parsing.
3. Bodies of exactly `MAX_UPLOAD_SIZE` bytes are accepted on both paths.
4. README states the limit, the 413 and each layer's allowance.

## Implementation steps
1. `settings/base.py` and `serializers.py`: raise `DATA_UPLOAD_MAX_MEMORY_SIZE`, derive `MAX_UPLOAD_SIZE`; add `PayloadTooLarge` and `check_body_size`; raise `PayloadTooLarge` in `load_json_upload`.
2. `views.py` (`bulk_upload`): call `check_body_size` for JSON content before reading `request.data`.
3. `src/recipes/tests/test_bulk_upload.py`: add size tests beside `test_invalid_json_file` (line 270).
4. `README.md` "Bulk recipe upload" (line 111): 5 MiB, 413, Django limit raised to match, nginx 50 MB, gunicorn none, Scaleway undocumented.
5. Run `uv run invoke format`, `lint`, `test`.

## Test plan
- File: exactly the limit gives 201/200; limit + 1 gives 413 and `file` error.
- Raw: pad with a long `preparation` to hit exact sizes; same two cases, 413 uses `body`.
- Raw over limit sends no valid recipe data and creates no pages.

## Open questions
- Scaleway request body limit is undocumented; verify on staging, or state "undocumented" in the README?
