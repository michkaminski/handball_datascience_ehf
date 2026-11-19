from __future__ import annotations

from collections.abc import Sequence

from ehf.domain.nationality import nationality_code

NATIONALITY_SQL = """
SELECT n.person_id, n.nationality, co.code
FROM ehf.person_nationality n
LEFT JOIN ehf.country co ON lower(co.name) = lower(n.nationality)
WHERE n.person_id = ANY(%(people)s)
ORDER BY n.person_id, n.nationality
"""


def read_nationalities(cursor, people: Sequence[int]) -> dict[int, tuple[str, ...]]:
    if not people:
        return {}
    cursor.execute(NATIONALITY_SQL, {"people": list(people)})
    grouped: dict[int, list[str]] = {}
    for row in cursor.fetchall():
        code = nationality_code(row["nationality"], row["code"])
        codes = grouped.setdefault(row["person_id"], [])
        if code not in codes:
            codes.append(code)
    return {person: tuple(codes) for person, codes in grouped.items()}
