"""Splunk HTTP Event Collector integration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict

import requests


LOGGER = logging.getLogger(__name__)


class SplunkHECSender:
    """Sends events and alerts to Splunk using the HTTP Event Collector."""

    def __init__(
        self,
        hec_url: str,
        token: str,
        index: str = "security",
        source: str = "splunk-auth-monitor",
        sourcetype: str = "json",
        verify_tls: bool = False,
        timeout_seconds: int = 10,
    ) -> None:
        self.hec_url = hec_url
        self.index = index
        self.source = source
        self.sourcetype = sourcetype
        self.verify_tls = verify_tls
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Splunk {token}",
                "Content-Type": "application/json",
            }
        )

    def send_event(self, event: Dict[str, object], event_type: str = "windows_auth_event") -> bool:
        """Send a structured event to Splunk HEC."""
        payload = {
            "time": self._event_time_to_epoch(event.get("timestamp")),
            "host": event.get("host", "unknown"),
            "source": self.source,
            "sourcetype": self.sourcetype,
            "index": self.index,
            "event": {
                "event_type": event_type,
                **event,
            },
        }

        try:
            response = self.session.post(
                self.hec_url,
                json=payload,
                verify=self.verify_tls,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            LOGGER.info("Sent %s to Splunk HEC", event_type)
            return True
        except requests.RequestException as error:
            LOGGER.error("Failed to send %s to Splunk: %s", event_type, error)
            return False

    @staticmethod
    def _event_time_to_epoch(timestamp: object) -> float:
        if timestamp is None:
            return datetime.now(timezone.utc).timestamp()
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        return parsed.timestamp()
