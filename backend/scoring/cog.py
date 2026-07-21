"""Server-side port of Stage 2 - segmental, mass-weighted center of mass.

This mirrors frontend/src/pipeline/cog.ts one-to-one (same Dempster table, same
landmark indices). Both exist because the API contract (CLAUDE.md) sends raw
landmarks and the server recomputes scoring authoritatively. The two ports are
kept consistent by validating this one against the committed clip-01 fixture
(see backend/scoring/tests). Method and rationale: PIPELINE.md - Stage 2.
"""

from __future__ import annotations

from dataclasses import dataclass

# MediaPipe Pose landmark indices (must match cog.ts).
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28

COG_LANDMARK_INDICES = [
    LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_WRIST, RIGHT_WRIST, LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE,
]

_SHOULDER_MID = (LEFT_SHOULDER, RIGHT_SHOULDER)
_HIP_MID = (LEFT_HIP, RIGHT_HIP)

# A landmark reference is either a single index or a two-index midpoint.
Ref = int | tuple[int, int]


@dataclass(frozen=True)
class Segment:
    name: str
    mass_fraction: float
    com_fraction: float  # fraction from proximal to distal endpoint
    proximal: Ref
    distal: Ref


# Dempster mass fractions (PIPELINE.md table). Paired-limb fractions are PER SIDE.
SEGMENTS: list[Segment] = [
    Segment("head_neck", 0.081, 0.0, _SHOULDER_MID, _SHOULDER_MID),
    Segment("trunk", 0.497, 0.5, _SHOULDER_MID, _HIP_MID),
    Segment("upper_arm_l", 0.028, 0.436, LEFT_SHOULDER, LEFT_ELBOW),
    Segment("upper_arm_r", 0.028, 0.436, RIGHT_SHOULDER, RIGHT_ELBOW),
    Segment("forearm_l", 0.016, 0.43, LEFT_ELBOW, LEFT_WRIST),
    Segment("forearm_r", 0.016, 0.43, RIGHT_ELBOW, RIGHT_WRIST),
    Segment("hand_l", 0.006, 0.0, LEFT_WRIST, LEFT_WRIST),
    Segment("hand_r", 0.006, 0.0, RIGHT_WRIST, RIGHT_WRIST),
    Segment("thigh_l", 0.1, 0.433, LEFT_HIP, LEFT_KNEE),
    Segment("thigh_r", 0.1, 0.433, RIGHT_HIP, RIGHT_KNEE),
    Segment("shank_l", 0.0465, 0.433, LEFT_KNEE, LEFT_ANKLE),
    Segment("shank_r", 0.0465, 0.433, RIGHT_KNEE, RIGHT_ANKLE),
    Segment("foot_l", 0.0145, 0.0, LEFT_ANKLE, LEFT_ANKLE),
    Segment("foot_r", 0.0145, 0.0, RIGHT_ANKLE, RIGHT_ANKLE),
]


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    z: float
    visibility: float


@dataclass(frozen=True)
class CoGPoint:
    x: float
    y: float
    confidence: float


Frame = list[Landmark]


def total_mass_fraction() -> float:
    """Cheapest correctness check in the pipeline: must be ~1.0."""
    return sum(s.mass_fraction for s in SEGMENTS)


if abs(total_mass_fraction() - 1.0) > 1e-6:
    raise RuntimeError(
        f"Segment mass fractions sum to {total_mass_fraction()}, expected 1.0 "
        "- a segment is missing or double-counted (PIPELINE.md Stage 2)"
    )


def _resolve_point(frame: Frame, ref: Ref) -> tuple[float, float]:
    if isinstance(ref, int):
        lm = frame[ref]
        return lm.x, lm.y
    a, b = frame[ref[0]], frame[ref[1]]
    return (a.x + b.x) / 2, (a.y + b.y) / 2


def compute_frame_cog(frame: Frame) -> CoGPoint:
    x = 0.0
    y = 0.0
    mass = 0.0
    for seg in SEGMENTS:
        px, py = _resolve_point(frame, seg.proximal)
        dx, dy = _resolve_point(frame, seg.distal)
        com_x = px + (dx - px) * seg.com_fraction
        com_y = py + (dy - py) * seg.com_fraction
        x += com_x * seg.mass_fraction
        y += com_y * seg.mass_fraction
        mass += seg.mass_fraction

    vis = [frame[i].visibility for i in COG_LANDMARK_INDICES]
    confidence = sum(vis) / len(vis)
    return CoGPoint(x=x / mass, y=y / mass, confidence=confidence)


def compute_cog_trajectory(frames: list[Frame]) -> list[CoGPoint]:
    return [compute_frame_cog(f) for f in frames]
