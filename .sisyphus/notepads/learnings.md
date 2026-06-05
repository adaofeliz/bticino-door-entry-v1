
## task-6-api: LegrandApiClientV1

- `_MAX_RETRIES = 2` means 3 total attempts (range(3) = 0,1,2). Test queues exactly 3 mock 500 responses.
- `aioresponses` with regex pattern works for dynamic URL matching (plant_id, gateway_id in path).
- `asyncio.sleep` in retry path is fine in tests — aioresponses doesn't block it.
- `get_plants` / `get_modules` handle both list responses and wrapped `{"plants": [...]}` shapes.
- `close()` only closes the internally-created session (`_owns_session=True`), not injected ones.
