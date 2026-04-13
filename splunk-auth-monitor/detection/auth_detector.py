"""Authentication detection logic for suspicious Windows activity."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque, DefaultDict, Dict, List, Tuple


LOGGER = logging.getLogger(__name__)


class AuthenticationDetector:
    """Stateful detector for common authentication threats."""

    def __init__(
        self,
        brute_force_threshold: int = 10,
        brute_force_window_minutes: int = 5,
        business_hours_start: int = 8,
        business_hours_end: int = 18,
        privilege_window_minutes: int = 10,
    ) -> None:
        self.brute_force_threshold = brute_force_threshold
        self.brute_force_window = timedelta(minutes=brute_force_window_minutes)
        self.business_hours_start = business_hours_start
        self.business_hours_end = business_hours_end
        self.privilege_window = timedelta(minutes=privilege_window_minutes)

        self.failed_logins: DefaultDict[Tuple[str, str], Deque[datetime]] = defaultdict(deque)
        self.last_bruteforce_alert: Dict[Tuple[str, str], datetime] = {}
        self.recent_logons_by_id: Dict[str, Dict[str, object]] = {}
        self.recent_logons_by_user: DefaultDict[str, Deque[Dict[str, object]]] = defaultdict(deque)

    def analyze_event(self, event: Dict[str, object]) -> List[Dict[str, object]]:
        """Analyze a single event and return zero or more alerts."""
        alerts: List[Dict[str, object]] = []
        event_id = int(event.get("event_id", 0))
        event_time = self._parse_event_time(event["timestamp"])

        self._expire_old_state(event_time)

        if event_id == 4625:
            brute_force_alert = self._detect_brute_force(event, event_time)
            if brute_force_alert:
                alerts.append(brute_force_alert)

        if event_id == 4624:
            self._remember_successful_login(event, event_time)
            suspicious_login_alert = self._detect_after_hours_login(event, event_time)
            if suspicious_login_alert:
                alerts.append(suspicious_login_alert)

        if event_id == 4672:
            privilege_alert = self._detect_privilege_escalation(event, event_time)
            if privilege_alert:
                alerts.append(privilege_alert)

        if event_id == 4740:
            alerts.append(self._build_lockout_alert(event))

        return alerts

    def _detect_brute_force(
        self,
        event: Dict[str, object],
        event_time: datetime,
    ) -> Dict[str, object] | None:
        username = str(event.get("username") or "unknown")
        source_ip = self._normalize_ip(str(event.get("source_ip") or "unknown"))
        tracking_key = (username, source_ip)

        recent_failures = self.failed_logins[tracking_key]
        recent_failures.append(event_time)

        while recent_failures and event_time - recent_failures[0] > self.brute_force_window:
            recent_failures.popleft()

        if len(recent_failures) <= self.brute_force_threshold:
            return None

        previous_alert_time = self.last_bruteforce_alert.get(tracking_key)
        if previous_alert_time and event_time - previous_alert_time <= self.brute_force_window:
            return None

        self.last_bruteforce_alert[tracking_key] = event_time
        LOGGER.warning(
            "Brute force pattern detected for user=%s from source=%s count=%s",
            username,
            source_ip,
            len(recent_failures),
        )
        return {
            "alert_type": "brute_force_attempt",
            "severity": "high",
            "timestamp": event["timestamp"],
            "username": username,
            "host": event.get("host", "unknown"),
            "source_ip": source_ip,
            "description": (
                f"More than {self.brute_force_threshold} failed logon events were observed "
                f"for user '{username}' from '{source_ip}' within 5 minutes."
            ),
            "supporting_event_id": 4625,
            "metadata": {
                "failed_attempt_count": len(recent_failures),
                "window_minutes": int(self.brute_force_window.total_seconds() // 60),
            },
        }

    def _remember_successful_login(self, event: Dict[str, object], event_time: datetime) -> None:
        logon_id = str(event.get("logon_id") or "").strip()
        username = str(event.get("username") or "unknown")

        login_record = {
            "timestamp": event["timestamp"],
            "event_time": event_time,
            "username": username,
            "host": event.get("host", "unknown"),
            "source_ip": self._normalize_ip(str(event.get("source_ip") or "unknown")),
            "logon_id": logon_id,
            "logon_type": event.get("logon_type", ""),
        }

        if logon_id:
            self.recent_logons_by_id[logon_id] = login_record
        self.recent_logons_by_user[username].append(login_record)

    def _detect_after_hours_login(
        self,
        event: Dict[str, object],
        event_time: datetime,
    ) -> Dict[str, object] | None:
        logon_type = str(event.get("logon_type") or "")
        # Interactive and remote interactive logons are more meaningful than service noise.
        if logon_type and logon_type not in {"2", "10", "11"}:
            return None

        if not self._is_outside_business_hours(event_time.hour):
            return None

        LOGGER.warning(
            "Suspicious after-hours login detected for user=%s at hour=%s",
            event.get("username", "unknown"),
            event_time.hour,
        )
        return {
            "alert_type": "suspicious_login_time",
            "severity": "medium",
            "timestamp": event["timestamp"],
            "username": event.get("username", "unknown"),
            "host": event.get("host", "unknown"),
            "source_ip": self._normalize_ip(str(event.get("source_ip") or "unknown")),
            "description": (
                f"Successful logon for '{event.get('username', 'unknown')}' occurred outside "
                f"business hours ({self.business_hours_start}:00-{self.business_hours_end}:00)."
            ),
            "supporting_event_id": 4624,
            "metadata": {"logon_type": logon_type or "unknown"},
        }

    def _detect_privilege_escalation(
        self,
        event: Dict[str, object],
        event_time: datetime,
    ) -> Dict[str, object] | None:
        username = str(event.get("username") or "unknown")
        logon_id = str(event.get("logon_id") or "").strip()
        related_login = None

        if logon_id:
            related_login = self.recent_logons_by_id.get(logon_id)

        if related_login is None:
            user_logins = self.recent_logons_by_user.get(username, deque())
            for login in reversed(user_logins):
                if event_time - login["event_time"] <= self.privilege_window:
                    related_login = login
                    break

        if related_login is None:
            return None

        LOGGER.warning(
            "Privilege assignment following login detected for user=%s logon_id=%s",
            username,
            logon_id or "unknown",
        )
        return {
            "alert_type": "possible_privilege_escalation",
            "severity": "high",
            "timestamp": event["timestamp"],
            "username": username,
            "host": event.get("host", "unknown"),
            "source_ip": related_login.get("source_ip", "unknown"),
            "description": (
                f"Special privileges were assigned to '{username}' shortly after a logon event. "
                "Review the account, logon source, and assigned privileges."
            ),
            "supporting_event_id": 4672,
            "metadata": {
                "linked_logon_timestamp": related_login["timestamp"],
                "linked_logon_id": related_login.get("logon_id", "unknown"),
            },
        }

    def _build_lockout_alert(self, event: Dict[str, object]) -> Dict[str, object]:
        LOGGER.warning("Account lockout detected for user=%s", event.get("username", "unknown"))
        return {
            "alert_type": "account_lockout",
            "severity": "high",
            "timestamp": event["timestamp"],
            "username": event.get("username", "unknown"),
            "host": event.get("host", "unknown"),
            "source_ip": self._normalize_ip(str(event.get("source_ip") or "unknown")),
            "description": (
                f"Account '{event.get('username', 'unknown')}' was locked out. "
                "This can indicate a password spraying or brute force condition."
            ),
            "supporting_event_id": 4740,
            "metadata": {},
        }

    def _expire_old_state(self, current_time: datetime) -> None:
        for tracking_key, attempts in list(self.failed_logins.items()):
            while attempts and current_time - attempts[0] > self.brute_force_window:
                attempts.popleft()
            if not attempts:
                del self.failed_logins[tracking_key]

        for logon_id, login_record in list(self.recent_logons_by_id.items()):
            if current_time - login_record["event_time"] > self.privilege_window:
                del self.recent_logons_by_id[logon_id]

        for username, login_records in list(self.recent_logons_by_user.items()):
            while login_records and current_time - login_records[0]["event_time"] > self.privilege_window:
                login_records.popleft()
            if not login_records:
                del self.recent_logons_by_user[username]

    def _is_outside_business_hours(self, hour: int) -> bool:
        if self.business_hours_start < self.business_hours_end:
            return not (self.business_hours_start <= hour < self.business_hours_end)
        return not (hour >= self.business_hours_start or hour < self.business_hours_end)

    @staticmethod
    def _parse_event_time(timestamp: object) -> datetime:
        return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))

    @staticmethod
    def _normalize_ip(value: str) -> str:
        if not value or value == "-" or value == "::1":
            return "unknown"
        return value
