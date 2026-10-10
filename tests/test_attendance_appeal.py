from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from flask import Flask

from ehf.domain.attendance_appeal import METRIC_CONCEPTS
from ehf.interface.factory import create_app
from ehf.services.attendance_appeal_i18n import translate_text
from maf.artifacts import ArtifactStore
from maf.diagnostics import ess_bulk, rank_normalized_rhat
from maf.features import FeatureBuilder, FeatureScaler, PhaseClassifier
from maf.design import ModelDataBuilder
from maf.forecast import AttendanceSimulator, ForecastScenario
from maf.model import HierarchicalAttendanceModel
from maf.nuts import SamplerSettings
from maf.quality import DataQualityChecker
from maf.records import Measure, ModelSpec
from maf.training import MafTrainer
from mathlib.registry import CONTENT_DIR, ArticleValidator, default_registry
from tests.maf_synthetic import synthetic_matches

INTERFACE = Path(__file__).resolve().parents[1] / "ehf" / "interface"


def test_analytic_gradient_matches_finite_differences() -> None:
    records = synthetic_matches(with_capacity=False)
    prepared, _ = DataQualityChecker().prepare(records)
    features, _ = FeatureBuilder().build(prepared)
    data = ModelDataBuilder().build(prepared, features, Measure.COUNT, FeatureScaler.fit(list(features.values())))
    model = HierarchicalAttendanceModel(data)
    theta = model.initial_point(np.random.default_rng(1))
    _, gradient = model.logp_and_grad(theta)
    for index in range(model.dimension):
        step = np.zeros_like(theta)
        step[index] = 1e-5
        numeric = (model.logp_and_grad(theta + step)[0] - model.logp_and_grad(theta - step)[0]) / 2e-5
        assert numeric == pytest.approx(gradient[index], rel=1e-4, abs=1e-3)


def test_convergence_diagnostics() -> None:
    rng = np.random.default_rng(3)
    good = rng.normal(size=(4, 1000))
    assert rank_normalized_rhat(good) < 1.01
    assert ess_bulk(good) == pytest.approx(4000, rel=0.15)
    assert rank_normalized_rhat(good + np.array([[0], [0], [0], [3.0]])) > 1.1


def test_null_attendance_is_never_zero() -> None:
    records = synthetic_matches(seasons=1, with_capacity=False)
    unknown = replace(records[0], spectators=None)
    prepared, report = DataQualityChecker().prepare([unknown, *records[1:]])
    assert report.attendance_unknown == 1
    assert not next(item for item in prepared if item.record.match_id == unknown.match_id).usable_count


@pytest.mark.parametrize(
    ("phase", "expected"),
    [("Group Phase", "regular"), ("Quarter-finals", "playoff"), ("Semi-finals", "playoff"), ("Finals", "final"), ("Qualification Round 2", "playoff")],
)
def test_phase_classes(phase: str, expected: str) -> None:
    assert PhaseClassifier().classify(phase) == expected


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> ArtifactStore:
    store = ArtifactStore(Path(tmp_path_factory.mktemp("maf")))
    trainer = MafTrainer(store, SamplerSettings(chains=2, warmup=150, draws=150, thin_store=2), parallel=False)
    spec = ModelSpec("men-count", "Men — spectators", Measure.COUNT, "test", holdout_seasons=1)
    trainer.train(synthetic_matches(with_capacity=False), spec, {100: "Club Zero"}, backtest=True)
    return store


def test_count_model_iaf_equals_exponent_of_effect(store: ArtifactStore) -> None:
    artifact = store.latest("men-count")
    assert artifact is not None
    effects = np.asarray(artifact.draws["effect_opponent"], dtype=np.float64)
    iaf = np.asarray(artifact.draws["iaf"], dtype=np.float64)
    assert np.allclose(iaf, 100.0 * np.exp(effects), rtol=1e-4)
    clubs = {club["id"]: club for club in artifact.summary["clubs"]}
    assert clubs[100]["away"]["iaf"]["median"] > 100 > clubs[105]["away"]["iaf"]["median"]


def test_forecast_intervals_are_nested(store: ArtifactStore) -> None:
    artifact = store.latest("men-count")
    assert artifact is not None
    result = AttendanceSimulator(artifact).simulate(ForecastScenario(100, 101, None, None, None, 2, 20.75, "playoff", 400))
    p50, p95 = result["intervals"]["50"], result["intervals"]["95"]
    assert p95[0] <= p50[0] <= p50[1] <= p95[1]
    assert 0.0 <= result["p_threshold"] <= 1.0


@pytest.fixture()
def app(store: ArtifactStore, monkeypatch: pytest.MonkeyPatch) -> Flask:
    monkeypatch.setenv("MAF_STORE", str(store.root))
    return create_app()


def test_api_panel_is_translated_and_linked(app: Flask) -> None:
    data = app.test_client().get("/raporty/frekwencja/maf/data?model=men-count").get_json()
    assert data["model"]["key"] == "men-count"
    assert not any(re.search("[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", item["label"]) for item in data["coefficients"])
    assert data["links"]["metrics"]["iaf"]["url"].startswith("/matematyka/modele-sportowe/")


def test_api_errors(app: Flask) -> None:
    client = app.test_client()
    assert client.get("/raporty/frekwencja/maf/data?model=women-count").status_code == 404
    assert client.get("/raporty/frekwencja/maf/forecast?model=men-count&host=100&opponent=101&weekday=8").status_code == 400
    assert client.get("/raporty/frekwencja/maf/club/1?model=men-count").status_code == 404
    export = client.get("/raporty/frekwencja/maf/export.csv?model=men-count")
    assert export.mimetype == "text/csv" and "iaf_median" in export.get_data(as_text=True)


def test_math_pages(app: Flask) -> None:
    client = app.test_client()
    registry = default_registry()
    for concept in registry.articles():
        assert client.get(registry.url(concept.id)).status_code == 200, concept.id
    assert client.get("/matematyka/").status_code == 200
    assert client.get("/matematyka/missing/").status_code == 404


def test_math_library_is_valid_and_in_sync() -> None:
    registry = default_registry()
    problems = ArticleValidator(registry).validate()
    assert not problems, [f"{item.article}: {item.message}" for item in problems]
    assert registry.checksum() == (CONTENT_DIR / "CHECKSUM").read_text(encoding="utf-8").strip()


def test_dashboard_metric_keys_exist() -> None:
    registry = default_registry()
    validator = ArticleValidator(registry)
    for key, (concept_id, anchor) in METRIC_CONCEPTS.items():
        concept = registry.concepts[concept_id]
        fragment = registry.resolve_anchor(concept, anchor)
        assert fragment is None or fragment in validator.ids_of(registry.concepts[concept.article]), key
    used: set[str] = set()
    for path in (INTERFACE / "templates" / "partials" / "attendance_appeal_panel.html", INTERFACE / "static" / "js" / "attendance_appeal.js"):
        text = path.read_text(encoding="utf-8")
        used |= set(re.findall(r'data-maf-info="([a-z_]+)"', text))
    assert used and used <= set(METRIC_CONCEPTS)


def test_engine_notes_are_translated() -> None:
    assert translate_text("tylko 3 mecze/meczów jako rywal") == "only 3 matches as visitor"
    assert translate_text("unchanged") == "unchanged"
