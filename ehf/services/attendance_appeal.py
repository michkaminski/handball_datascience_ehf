from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ehf.domain.attendance_appeal import APPEAL_MODELS, METRIC_CONCEPTS, AppealModel, appeal_model
from ehf.services.attendance_appeal_i18n import (
    translate_club,
    translate_forecast,
    translate_model,
    translate_panel,
)
from ehf.services.mathematics import MathLibraryService
from maf.artifacts import ModelArtifact
from maf.forecast import AttendanceSimulator, ForecastScenario, HostOpponentAnalysis, compare_clubs

JsonDict = dict[str, object]
DEFAULT_STORE = Path(__file__).resolve().parents[2] / "var" / "maf"
PANEL_CLUB_FIELDS = ("id", "name", "names_history", "home")


def model_store_path() -> Path:
    return Path(os.environ.get("MAF_STORE", str(DEFAULT_STORE)))


class AppealModelStore(Protocol):
    def latest(self, key: str) -> ModelArtifact | None: ...


class AppealModelMissing(LookupError):
    pass


@dataclass(frozen=True)
class AppealModelOption:
    key: str
    label: str
    available: bool
    version: str | None
    status: str | None


class AttendanceAppealService:
    def __init__(self, store: AppealModelStore, library: MathLibraryService) -> None:
        self._store = store
        self._library = library

    def models(self) -> tuple[AppealModelOption, ...]:
        options = []
        for model in APPEAL_MODELS:
            artifact = self._store.latest(model.spec.key)
            info = _model(artifact) if artifact else {}
            options.append(
                AppealModelOption(
                    key=model.spec.key,
                    label=model.spec.label,
                    available=artifact is not None,
                    version=str(info["version"]) if artifact else None,
                    status=str(info["status"]) if artifact else None,
                )
            )
        return tuple(options)

    def select(self, key: str | None) -> AppealModel:
        return appeal_model(key)

    def artifact(self, key: str) -> ModelArtifact:
        artifact = self._store.latest(key)
        if artifact is None:
            raise AppealModelMissing(key)
        return artifact

    def links(self) -> JsonDict:
        concept_ids = tuple(dict.fromkeys(concept for concept, _ in METRIC_CONCEPTS.values()))
        registry = self._library.registry
        return {
            "concepts": self._library.links(concept_ids),
            "metrics": {
                key: {"concept": concept, "url": registry.url(concept, anchor)}
                for key, (concept, anchor) in METRIC_CONCEPTS.items()
            },
            "model": registry.url("atrakcyjnosc-frekwencyjna"),
        }

    def panel(self, key: str) -> JsonDict:
        summary = self.artifact(key).summary
        return translate_panel({
            "model": summary["model"],
            "quality": summary["quality"],
            "diagnostics": summary["diagnostics"],
            "coefficients": summary["coefficients"],
            "kpi": summary["kpi"],
            "clubs": [self._panel_club(club) for club in _items(summary["clubs"])],
            "hosts": [
                {"id": host["club_id"], "capacity": host["capacity"]}
                for host in _items(summary["hosts"])
            ],
            "competitions": summary["competitions"],
            "venues": _items(summary["venues"])[:400],
            "surprises": summary["surprises"],
            "records": summary["records"],
            "heatmap": summary["heatmap"],
            "ppc": summary["ppc"],
            "backtest": summary["backtest"],
            "links": self.links(),
        })

    def _panel_club(self, club: JsonDict) -> JsonDict:
        result = {field: club.get(field) for field in PANEL_CLUB_FIELDS}
        away = club.get("away")
        if isinstance(away, dict):
            result["away"] = {
                field: value for field, value in away.items() if field not in {"histogram", "central"}
            }
        return result

    def club(self, key: str, club_id: int) -> JsonDict:
        artifact = self.artifact(key)
        club = next((item for item in _items(artifact.summary["clubs"]) if item["id"] == club_id), None)
        if club is None:
            raise KeyError(club_id)
        model = _model(artifact)
        fields = (
            "key", "label", "measure", "version", "trained_at", "status",
            "matches_used", "period", "reference", "sampler", "groups",
        )
        club = dict(club)
        translate_club(club)
        selected = {field: model[field] for field in fields}
        translate_model(selected)
        return {"club": club, "model": selected, "links": self.links()}

    def host(self, key: str, club_id: int) -> JsonDict:
        return HostOpponentAnalysis(self.artifact(key)).analyze(club_id)

    def compare(self, key: str, first: int, second: int) -> JsonDict:
        return compare_clubs(self.artifact(key), first, second)

    def forecast(self, key: str, scenario: ForecastScenario) -> JsonDict:
        return translate_forecast(AttendanceSimulator(self.artifact(key)).simulate(scenario))

    def export_csv(self, key: str) -> str:
        artifact = self.artifact(key)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "club_id", "club", "matches_as_visitor", "mean_spectators", "median_spectators",
                "iaf_median", "iaf_q2.5", "iaf_q97.5", "p_iaf_gt_100", "extra_spectators_median",
                "reliable", "notes", "model_version",
            ]
        )
        for club in _items(artifact.summary["clubs"]):
            away = club.get("away")
            if not isinstance(away, dict):
                continue
            iaf = away["iaf"]
            writer.writerow(
                [
                    club["id"], club["name"], away["matches"], round(away["mean"], 2),
                    round(away["median"], 2), round(iaf["median"], 3), round(iaf["q025"], 3),
                    round(iaf["q975"], 3), round(away["p_gt_100"], 4), round(away["extra"]["median"], 1),
                    "yes" if away["reliable"] else "no", "; ".join(away["notes"]), artifact.version,
                ]
            )
        return buffer.getvalue()


def _model(artifact: ModelArtifact) -> JsonDict:
    model = artifact.summary["model"]
    assert isinstance(model, dict)
    return model


def _items(value: object) -> list[JsonDict]:
    assert isinstance(value, list)
    return value
