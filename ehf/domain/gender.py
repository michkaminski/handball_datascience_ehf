from __future__ import annotations

from ehf.domain.matches import Choice

GENDERS = frozenset({"men", "women"})
GENDER_LABELS = {"men": "Mężczyźni", "women": "Kobiety"}
GENDER_CHOICES = (
    Choice("men", GENDER_LABELS["men"]),
    Choice("women", GENDER_LABELS["women"]),
)


def gender_label(code: str | None) -> str:
    if not code:
        return "—"
    parts = [GENDER_LABELS.get(part, part) for part in code.split(",") if part]
    return ", ".join(parts) if parts else "—"
