"""Alert export utilities for local JSON output."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List


LOGGER = logging.getLogger(__name__)


class JsonAlertExporter:
    """Exports detection alerts to a local JSON file."""

    def __init__(self, output_path: str) -> None:
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def export_alert(self, alert: Dict[str, object]) -> bool:
        """Append a new alert into the JSON artifact on disk."""
        try:
            existing_alerts = self._load_existing_alerts()
            existing_alerts.append(alert)
            with self.output_path.open("w", encoding="utf-8") as file_handle:
                json.dump(existing_alerts, file_handle, indent=2)
            LOGGER.info("Exported alert to JSON: %s", self.output_path)
            return True
        except OSError as error:
            LOGGER.error("Failed to export alert to JSON: %s", error)
            return False

    def _load_existing_alerts(self) -> List[Dict[str, object]]:
        if not self.output_path.exists():
            return []

        try:
            with self.output_path.open("r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
        except json.JSONDecodeError:
            LOGGER.warning(
                "Alert export file %s was not valid JSON. Starting a fresh alert list.",
                self.output_path,
            )
            return []

        return data if isinstance(data, list) else []
