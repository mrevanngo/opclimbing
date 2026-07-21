"""The response envelope every route returns (CLAUDE.md - Response Format):

    success -> { "data": <payload> }
    error   -> { "error": "<human-readable message>" }

`ok` builds success bodies; the exception handlers in main.py build error bodies
so the shape is consistent even for framework-raised errors.
"""

from typing import Any


def ok(payload: Any) -> dict[str, Any]:
    return {"data": payload}
