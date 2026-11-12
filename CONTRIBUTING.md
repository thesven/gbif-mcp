# Contributing to gbif-mcp

Contributions are welcome! Please adhere to the following workflow:

1. Use `uv` for dependency management: `uv sync`.
2. Format your code with `uv run ruff format src tests scripts`.
3. Verify linting with `uv run ruff check src tests scripts`.
4. Ensure all unit tests pass with branch coverage >90%: `uv run pytest --cov=gbif_mcp --cov-branch`.
5. Build and run smoke tests: `uv build && uv run python scripts/check_dist.py && uv run python scripts/smoke.py`.
