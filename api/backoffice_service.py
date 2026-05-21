"""Load mock BackOffice configuration from JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKOFFICE_CONFIG_PATH = PROJECT_ROOT / "backoffice" / "mock_config.json"


class BackOfficeConfigNotFoundError(FileNotFoundError):
    """Raised when mock_config.json is missing."""


class BackOfficeConfigError(ValueError):
    """Raised when mock_config.json cannot be parsed."""


def load_backoffice_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or BACKOFFICE_CONFIG_PATH
    if not config_path.is_file():
        raise BackOfficeConfigNotFoundError(
            f"Missing BackOffice config file: {config_path}"
        )

    try:
        with config_path.open(encoding="utf-8") as fh:
            config = json.load(fh)
    except json.JSONDecodeError as exc:
        raise BackOfficeConfigError(
            f"Invalid JSON in BackOffice config: {config_path}"
        ) from exc

    if not isinstance(config, dict):
        raise BackOfficeConfigError(
            f"BackOffice config must be a JSON object: {config_path}"
        )
    return config
