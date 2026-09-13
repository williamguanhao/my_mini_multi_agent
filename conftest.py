"""Ensures the repo root is on sys.path so tests can import
`mini_agent`, `graph`, and `mcp_servers.*` regardless of how
pytest is invoked (plain `pytest` vs `python -m pytest`).
"""
