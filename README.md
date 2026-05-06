# CodeChef Stats API

FastAPI REST API for scraping public CodeChef profile data.

The root route serves a lightweight HTML documentation page similar to the CodeForces API project,
`/dashboard` provides a handle-driven response viewer for all API endpoints, and Swagger/OpenAPI
remains available at `/docs`.

## Structure

- `core/` shared configuration
- `core/cache.py` in-memory TTL response cache
- `core/rate_limit.py` in-memory request limiter
- `models/` response models
- `routes/profile.py` profile info route
- `routes/heatmap.py` heatmap data route
- `routes/rating.py` rating history route
- `services/profile.py` profile scraping and normalization
- `services/heatmap.py` heatmap data service
- `services/rating.py` rating history service
- `main.py` FastAPI entrypoint

## Run

```bash
uv sync
uv run uvicorn main:app --reload
```

Run tests:

```bash
uv run pytest
```

## Endpoint

```http
GET /profile/{handle}
```

```http
GET /
```

```http
GET /heatmap/{handle}
```

Heatmap query options:

```http
GET /heatmap/{handle}?view=last_365
GET /heatmap/{handle}?view=year&year=2025
GET /heatmap/{handle}?view=all
```

```http
GET /rating/{handle}
```

```http
GET /dashboard
```

## Behavior

- upstream CodeChef fetches are cached in memory
- API routes are rate-limited per client IP
