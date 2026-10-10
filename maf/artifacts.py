from __future__ import annotations

import json
import math
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

SUMMARY_FILE = "summary.json"
MATCHES_FILE = "matches.json"
DRAWS_FILE = "draws.npz"
LATEST_FILE = "latest.json"


def _clean(value: object) -> object:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, np.floating):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(item) for item in value]
    return value


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(_clean(payload), ensure_ascii=False), encoding="utf-8")


@dataclass
class ModelArtifact:
    path: Path
    summary: dict[str, object]
    _draws: dict[str, NDArray[np.float32]] | None = field(default=None, repr=False)

    @property
    def version(self) -> str:
        model = self.summary.get("model")
        assert isinstance(model, dict)
        return str(model["version"])

    @cached_property
    def matches(self) -> list[dict[str, object]]:
        loaded = json.loads((self.path / MATCHES_FILE).read_text(encoding="utf-8"))
        assert isinstance(loaded, list)
        return loaded

    @property
    def draws(self) -> dict[str, NDArray[np.float32]]:
        if self._draws is None:
            with np.load(self.path / DRAWS_FILE) as archive:
                self._draws = {name: archive[name] for name in archive.files}
        return self._draws


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(
        self,
        key: str,
        version: str,
        summary: Mapping[str, object],
        matches: list[dict[str, object]],
        draws: Mapping[str, NDArray[np.floating]],
    ) -> Path:
        directory = self.root / key / version.replace("+", "_")
        temporary = directory.with_name(directory.name + ".tmp")
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True)
        write_json(temporary / SUMMARY_FILE, dict(summary))
        write_json(temporary / MATCHES_FILE, matches)
        arrays: dict[str, Any] = {
            name: np.asarray(values, dtype=np.float32) for name, values in draws.items()
        }
        np.savez_compressed(temporary / DRAWS_FILE, **arrays)
        if directory.exists():
            shutil.rmtree(directory)
        temporary.rename(directory)
        write_json(self.root / key / LATEST_FILE, {"version": version, "directory": directory.name})
        return directory

    def latest(self, key: str) -> ModelArtifact | None:
        pointer = self.root / key / LATEST_FILE
        if not pointer.exists():
            return None
        data = json.loads(pointer.read_text(encoding="utf-8"))
        return self.load(self.root / key / str(data["directory"]))

    def load(self, directory: Path) -> ModelArtifact | None:
        summary_path = directory / SUMMARY_FILE
        if not summary_path.exists():
            return None
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return ModelArtifact(path=directory, summary=summary)

    def versions(self, key: str) -> list[str]:
        folder = self.root / key
        if not folder.exists():
            return []
        return sorted(
            (
                item.name
                for item in folder.iterdir()
                if item.is_dir() and not item.name.endswith(".tmp")
            ),
            reverse=True,
        )
