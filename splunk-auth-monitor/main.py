"""Entry point for the Splunk authentication monitoring demo."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from collector.event_collector import WindowsSecurityEventCollector
from detection.auth_detector import AuthenticationDetector
from integration.json_exporter import JsonAlertExporter
from integration.splunk_sender import SplunkHECSender
from utils.logger import configure_logging


LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "config.yaml"


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load YAML configuration from disk."""
    with config_path.open("r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle) or {}


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Windows authentication monitor with Splunk integration")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the YAML configuration file",
    )
    parser.add_argument(
        "--oneshot",
        action="store_true",
        help="Collect and analyze available events once, then exit",
    )
    parser.add_argument(
        "--no-splunk",
        action="store_true",
        help="Force local analysis mode even if Splunk is enabled in config",
    )
    return parser


def print_alert(alert: Dict[str, object]) -> None:
    """Print a human-readable alert to the console."""
    print(
        "[ALERT] "
        f"{alert['severity'].upper()} | {alert['alert_type']} | "
        f"user={alert.get('username', 'unknown')} | "
        f"host={alert.get('host', 'unknown')} | "
        f"details={alert['description']}"
    )


def build_json_exporter(config: Dict[str, Any]) -> JsonAlertExporter | None:
    alerts_config = config.get("alerts", {})
    export_config = alerts_config.get("export_json", {})
    if not export_config.get("enabled", False):
        return None

    output_path = export_config.get("path")
    if not output_path:
        LOGGER.warning("JSON alert export is enabled but no output path is configured.")
        return None

    return JsonAlertExporter(str((BASE_DIR / output_path).resolve()))


def build_splunk_sender(config: Dict[str, Any], force_local_mode: bool) -> SplunkHECSender | None:
    splunk_config = config.get("splunk", {})
    if force_local_mode or not splunk_config.get("enabled", False):
        LOGGER.info("Running in local analysis mode. Splunk HEC is disabled.")
        return None

    token = splunk_config.get("token")
    hec_url = splunk_config.get("hec_url")
    if not token or token == "YOUR_SPLUNK_TOKEN" or not hec_url:
        LOGGER.warning("Splunk is enabled but the HEC configuration is incomplete. Using local mode.")
        return None

    return SplunkHECSender(
        hec_url=hec_url,
        token=token,
        index=splunk_config.get("index", "security"),
        source=splunk_config.get("source", "splunk-auth-monitor"),
        sourcetype=splunk_config.get("sourcetype", "json"),
        verify_tls=bool(splunk_config.get("verify_tls", False)),
        timeout_seconds=int(splunk_config.get("timeout_seconds", 10)),
    )


def main() -> int:
    arguments = build_argument_parser().parse_args()
    config_path = Path(arguments.config).resolve()
    if not config_path.exists():
        print(f"Configuration file not found: {config_path}", file=sys.stderr)
        return 1

    config = load_config(config_path)
    configure_logging(config.get("app", {}).get("log_level", "INFO"))

    app_config = config.get("app", {})
    detection_config = config.get("detection", {})

    try:
        collector = WindowsSecurityEventCollector(
            lookback_minutes=int(app_config.get("historical_lookback_minutes", 15)),
            start_from_latest=bool(app_config.get("start_from_latest", False)),
        )
    except RuntimeError as error:
        LOGGER.error(error)
        return 1

    detector = AuthenticationDetector(
        brute_force_threshold=int(detection_config.get("brute_force_threshold", 10)),
        brute_force_window_minutes=int(detection_config.get("brute_force_window_minutes", 5)),
        business_hours_start=int(detection_config.get("business_hours_start", 8)),
        business_hours_end=int(detection_config.get("business_hours_end", 18)),
        privilege_window_minutes=int(detection_config.get("privilege_window_minutes", 10)),
    )
    json_exporter = build_json_exporter(config)
    splunk_sender = build_splunk_sender(config, arguments.no_splunk)

    poll_interval = int(app_config.get("poll_interval_seconds", 15))
    LOGGER.info("Starting Splunk Auth Monitor")

    try:
        while True:
            try:
                events = collector.collect()
            except RuntimeError as error:
                LOGGER.error("Event collection failed: %s", error)
                return 1

            for event in events:
                LOGGER.info(
                    "Collected event_id=%s user=%s host=%s",
                    event.get("event_id"),
                    event.get("username"),
                    event.get("host"),
                )

                alerts = detector.analyze_event(event)
                for alert in alerts:
                    LOGGER.warning("Detection generated: %s", alert["alert_type"])
                    print_alert(alert)
                    if json_exporter:
                        json_exporter.export_alert(alert)
                    if splunk_sender:
                        splunk_sender.send_event(alert, event_type="security_alert")

                if splunk_sender:
                    splunk_sender.send_event(event, event_type="windows_auth_event")

            if arguments.oneshot:
                break

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        LOGGER.info("Stopping monitor due to keyboard interrupt")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
