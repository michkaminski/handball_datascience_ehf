from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ehf.domain.attendance_appeal import APPEAL_MODELS  # noqa: E402
from ehf.infrastructure.attendance_appeal_reader import PsycopgAttendanceAppealReader  # noqa: E402
from ehf.infrastructure.connection import open_connection  # noqa: E402
from ehf.services.attendance_appeal import model_store_path  # noqa: E402
from ehf.settings import Settings  # noqa: E402
from maf.artifacts import ArtifactStore  # noqa: E402
from maf.nuts import SamplerSettings  # noqa: E402
from maf.training import MafTrainer  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the attendance appeal model (MAF)")
    parser.add_argument("models", nargs="*", help="model keys, e.g. men-count; empty = all")
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=1000)
    parser.add_argument("--draws", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--no-backtest", action="store_true")
    options = parser.parse_args(argv)
    settings = Settings.from_env()
    reader = PsycopgAttendanceAppealReader(lambda: open_connection(settings))
    sampler = SamplerSettings(
        chains=options.chains, warmup=options.warmup, draws=options.draws, seed=options.seed
    )
    trainer = MafTrainer(
        ArtifactStore(model_store_path()), sampler, progress=lambda text: print(text, flush=True)
    )
    selected = [
        model for model in APPEAL_MODELS if not options.models or model.spec.key in options.models
    ]
    if not selected:
        print(f"Unknown models: {options.models}")
        return 2
    names = reader.fetch_club_names()
    for model in selected:
        records = reader.fetch_matches(model.gender)
        result = trainer.train(records, model.spec, names, backtest=not options.no_backtest)
        print(f"{model.spec.key}: version {result.version}, status {result.status}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
