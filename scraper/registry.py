"""Model ID registry — assigns and preserves stable integer IDs for models."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class IDRegistry:
    """Manages stable model ID assignment across scraper runs.

    Column IDs are defined in scraper/columns.py and not tracked here.
    """

    def __init__(
        self,
        models: dict[str, int] | None = None,
        retired_models: list[int] | None = None,
        next_model_id: int = 1,
    ) -> None:
        self.models: dict[str, int] = dict(models) if models else {}
        self.retired_models: list[int] = list(retired_models) if retired_models else []
        self.next_model_id: int = next_model_id
        self._retired_set: set[int] = set(self.retired_models)

    # ── Load / Save ────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> IDRegistry:
        """Load registry from JSON file. Creates fresh registry if file not found."""
        if not path.exists():
            log.warning("[registry:load] File not found, starting fresh | path=%s", path)
            return cls()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Failed to load registry from {path}: {e}") from e

        version = data.get("version", 1)
        models = data.get("models", {})
        retired = data.get("retired_models", [])

        # Handle v1 format (has columns section — ignore it)
        if version == 1:
            next_id = data.get("next_model_id", 1)
        else:
            next_id = data.get("next_model_id", 1)

        reg = cls(models=models, retired_models=retired, next_model_id=next_id)
        log.info(
            "[registry:load] Loaded | path=%s model_count=%d next_model_id=%d retired=%d",
            path, len(reg.models), reg.next_model_id, len(reg.retired_models),
        )
        return reg

    def save(self, path: Path) -> None:
        """Atomic write registry to JSON file."""
        data = {
            "version": 2,
            "models": self.models,
            "retired_models": sorted(self.retired_models),
            "next_model_id": self.next_model_id,
        }
        content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        # Write to temp file then atomic rename
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix=path.stem,
        )
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            os.replace(tmp, str(path))
        except BaseException:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

        log.info(
            "[registry:save] Written | path=%s model_count=%d next_model_id=%d",
            path, len(self.models), self.next_model_id,
        )

    # ── ID assignment ──────────────────────────────────────────────────

    def assign_model_id(self, natural_key: str) -> int:
        """Return the stable ID for a model, assigning a new one if needed.

        Natural key format: "manufacturer|model" (lowercased, stripped).
        """
        existing = self.models.get(natural_key)
        if existing is not None:
            return existing

        new_id = self.next_model_id
        if new_id == 0:
            new_id = 1  # ID 0 is reserved
        if new_id > 65535:
            raise OverflowError(
                f"Model ID overflow: next_model_id={new_id} exceeds uint16 max (65535)"
            )

        self.models[natural_key] = new_id
        self.next_model_id = new_id + 1
        log.debug("[registry:assign] New model | key=%s id=%d", natural_key, new_id)
        return new_id

    def get_model_id(self, natural_key: str) -> int | None:
        """Look up a model ID without assigning. Returns None if not found."""
        return self.models.get(natural_key)

    def retire_model(self, natural_key: str) -> int | None:
        """Mark a model as retired. Returns the retired ID, or None if not found."""
        model_id = self.models.get(natural_key)
        if model_id is None:
            return None
        if model_id not in self._retired_set:
            self.retired_models.append(model_id)
            self._retired_set.add(model_id)
            log.info("[registry:retire] Model retired | key=%s id=%d", natural_key, model_id)
        return model_id
