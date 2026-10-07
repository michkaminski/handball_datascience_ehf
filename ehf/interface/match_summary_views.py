from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError, MatchNotFound
from ehf.interface.match_summary_charts import (
    COLORS,
    TINTS,
    court_spots,
    flow_chart,
    goal_dots,
    lead_chart,
    scale_stops,
    segment_bars,
)
from ehf.interface.match_summary_texts import (
    LANGUAGES,
    TEXTS,
    decimal_text,
    headline_text,
    kickoff_text,
    language,
    spectators_text,
)
from ehf.services.match_summary import MatchSummaryService, NoPlayByPlay


class MatchSummaryPrintView(MethodView):
    """One-page match summary; ``?lang=en`` for English (Polish otherwise), ``?variant=short`` for the
    plain version: no crests, averages, key moments or shot maps."""

    def __init__(self, service: MatchSummaryService) -> None:
        self._service = service

    def get(self, match_id: int) -> str:
        lang = language(request.args.get("lang"))
        short = request.args.get("variant") == "short"
        try:
            summary = self._service.build(match_id, with_baseline=not short)
        except MatchNotFound:
            abort(404)
        except NoPlayByPlay as exc:
            abort(404, description=str(exc))
        except DataReadError as exc:
            abort(503, description=str(exc))
        header = summary.header
        return render_template(
            "print/match_summary.html",
            s=summary,
            lang=lang,
            short=short,
            languages=LANGUAGES,
            t=TEXTS[lang],
            headline=headline_text(summary.headline, header.names, lang),
            kickoff=kickoff_text(header.kickoff_at, lang),
            spectators=spectators_text(header.spectators, lang),
            decimal=lambda value: decimal_text(value, lang),
            flow=flow_chart(summary),
            lead=lead_chart(summary) if short else None,
            spots={side: court_spots(summary.maps[side]) for side in ("home", "away")},
            stops={side: scale_stops(side) for side in ("home", "away")},
            segments=segment_bars(summary.flow),
            colors=COLORS,
            tints=TINTS,
            goal_dots=goal_dots,
        )
