"""Hold annotation route: replace the whole annotated hold set for a climb.

Contract (CLAUDE.md):
  PUT /climbs/{id}/holds { holds: [{ sequence_index, frame_x, frame_y }] }
      -> 200 { data: { holds } }

- Rejects an empty hold list with 400.
- Replaces the whole set atomically (delete existing, insert new) so the
  sequence stays consistent.
- Marks the climb 'annotated'.
"""

from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from core.db import get_conn
from core.envelope import ok
from core.security import CurrentUser, get_current_user
from models.schemas import HoldResponse, HoldsRequest
from routers.climbs import _owned_climb_or_404

router = APIRouter(prefix="/climbs", tags=["holds"])


@router.put("/{climb_id}/holds")
def replace_holds(
    climb_id: UUID,
    body: HoldsRequest,
    user: CurrentUser = Depends(get_current_user),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    _owned_climb_or_404(conn, climb_id, user.id)
    if not body.holds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="At least one hold is required"
        )

    # Distinct sequence indices keep the (climb_id, sequence_index) unique
    # constraint meaningful and the tap order well-defined.
    indices = [h.sequence_index for h in body.holds]
    if len(set(indices)) != len(indices):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate hold sequence_index"
        )

    ordered = sorted(body.holds, key=lambda h: h.sequence_index)
    with conn.cursor() as cur:
        # Atomic replace within the request transaction (commits on clean exit).
        cur.execute("DELETE FROM holds WHERE climb_id = %s", (climb_id,))
        saved: list[dict[str, Any]] = []
        for h in ordered:
            cur.execute(
                """
                INSERT INTO holds (climb_id, sequence_index, frame_x, frame_y)
                VALUES (%s, %s, %s, %s)
                RETURNING id, sequence_index, frame_x, frame_y
                """,
                (climb_id, h.sequence_index, h.frame_x, h.frame_y),
            )
            row = cur.fetchone()
            assert row is not None
            saved.append(HoldResponse(**row).model_dump(mode="json"))
        cur.execute("UPDATE climbs SET status = 'annotated' WHERE id = %s", (climb_id,))

    return ok({"holds": saved})
