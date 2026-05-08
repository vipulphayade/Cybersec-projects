"""Windows Security Event Log collector for authentication monitoring."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

try:
    import win32evtlog
    import pywintypes
except ImportError:  # pragma: no cover
    win32evtlog = None
    pywintypes = None


LOGGER = logging.getLogger(__name__)
WINDOWS_EVENT_NS = {"evt": "http://schemas.microsoft.com/win/2004/08/events/event"}
TARGET_EVENT_IDS = {4624, 4625, 4672, 4720, 4740}


class WindowsSecurityEventCollector:
    """Collects and normalizes Windows Security log events."""

    def __init__(
        self,
        event_ids: Optional[List[int]] = None,
        lookback_minutes: int = 15,
        start_from_latest: bool = False,
        batch_size: int = 64,
    ) -> None:
        if win32evtlog is None:
            raise RuntimeError(
                "pywin32 is not installed or this is not a Windows host. "
                "Install pywin32 on Windows to read Security Event Logs."
            )

        self.event_ids = event_ids or sorted(TARGET_EVENT_IDS)
        self.lookback_minutes = lookback_minutes
        self.start_from_latest = start_from_latest
        self.batch_size = batch_size
        self.last_record_id: Optional[int] = None
        self.channel = "Security"

    def collect(self) -> List[Dict[str, object]]:
        """Return newly observed authentication events as structured dictionaries."""
        if self.last_record_id is None:
            if self.start_from_latest:
                self.last_record_id = self._get_latest_record_id()
                LOGGER.info("Collector initialized from record id %s", self.last_record_id)
                return []

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.lookback_minutes)
            recent_events = self._fetch_events(cutoff_time=cutoff)
            if recent_events:
                self.last_record_id = max(
                    int(event["record_id"]) for event in recent_events if event.get("record_id")
                )
            LOGGER.info("Collected %s historical events", len(recent_events))
            return recent_events

        new_events = self._fetch_events(stop_record_id=self.last_record_id)
        if new_events:
            self.last_record_id = max(
                int(event["record_id"]) for event in new_events if event.get("record_id")
            )
        LOGGER.info("Collected %s new security events", len(new_events))
        return new_events

    def _fetch_events(
        self,
        stop_record_id: Optional[int] = None,
        cutoff_time: Optional[datetime] = None,
    ) -> List[Dict[str, object]]:
        query_handle = self._evt_query(self._build_xpath_query(), reverse=True)
        collected: List[Dict[str, object]] = []
        should_stop = False

        try:
            while not should_stop:
                event_handles = self._evt_next(query_handle)
                if not event_handles:
                    break

                for event_handle in event_handles:
                    event = self._render_event(event_handle)
                    if not event:
                        continue

                    record_id = int(event.get("record_id", 0))
                    event_time = self._parse_timestamp(str(event["timestamp"]))

                    if stop_record_id is not None and record_id <= stop_record_id:
                        should_stop = True
                        break

                    if cutoff_time is not None and event_time < cutoff_time:
                        should_stop = True
                        break

                    collected.append(event)
        finally:
            self._safe_close(query_handle)

        collected.sort(key=lambda item: int(item.get("record_id", 0)))
        return collected

    def _get_latest_record_id(self) -> int:
        query_handle = self._evt_query(self._build_xpath_query(), reverse=True)
        try:
            event_handles = self._evt_next(query_handle)
            if not event_handles:
                return 0
            latest_event = self._render_event(event_handles[0])
            for leftover_handle in event_handles[1:]:
                self._safe_close(leftover_handle)
        finally:
            self._safe_close(query_handle)

        if not latest_event:
            return 0
        return int(latest_event["record_id"])

    def _build_xpath_query(self) -> str:
        predicates = " or ".join(f"EventID={event_id}" for event_id in self.event_ids)
        return f"*[System[({predicates})]]"

    def _evt_query(self, query: str, reverse: bool = True):
        flags = getattr(win32evtlog, "EvtQueryReverseDirection", 0) if reverse else 0
        attempts = [
            (self.channel, flags, query),
            (self.channel, query, flags),
            (self.channel, getattr(win32evtlog, "EvtQueryChannelPath", 0) | flags, query),
            (self.channel, query, getattr(win32evtlog, "EvtQueryChannelPath", 0) | flags),
        ]

        last_error: Optional[Exception] = None
        for args in attempts:
            try:
                return win32evtlog.EvtQuery(*args)
            except TypeError as error:
                last_error = error
            except pywintypes.error as error:
                if getattr(error, "winerror", None) == 5:
                    raise RuntimeError(
                        "Access to the Windows Security Event Log was denied. "
                        "Run the monitor from an elevated PowerShell session or grant the account "
                        "permission to read the Security log."
                    ) from error
                raise
            except Exception:
                raise

        if last_error:
            raise last_error
        raise RuntimeError("Unable to query Windows Security Event Log.")

    def _evt_next(self, query_handle):
        try:
            return win32evtlog.EvtNext(query_handle, self.batch_size)
        except TypeError:
            return win32evtlog.EvtNext(query_handle, self.batch_size, 0, 0)

    def _render_event(self, event_handle) -> Optional[Dict[str, object]]:
        try:
            xml_text = win32evtlog.EvtRender(
                event_handle,
                getattr(win32evtlog, "EvtRenderEventXml", 1),
            )
            xml_root = ET.fromstring(xml_text)
        except Exception as error:
            LOGGER.exception("Failed to render event XML: %s", error)
            return None
        finally:
            self._safe_close(event_handle)

        system_node = xml_root.find("evt:System", WINDOWS_EVENT_NS)
        if system_node is None:
            return None

        event_id = self._read_int(system_node.find("evt:EventID", WINDOWS_EVENT_NS))
        if event_id not in TARGET_EVENT_IDS:
            return None

        timestamp = self._read_attr(
            system_node.find("evt:TimeCreated", WINDOWS_EVENT_NS),
            "SystemTime",
        )
        computer_name = self._read_text(system_node.find("evt:Computer", WINDOWS_EVENT_NS))
        record_id = self._read_int(system_node.find("evt:EventRecordID", WINDOWS_EVENT_NS))

        event_data = self._extract_event_data(xml_root)
        message = self._format_message(event_id, event_data)

        return {
            "event_id": event_id,
            "timestamp": timestamp,
            "username": self._extract_username(event_id, event_data),
            "host": computer_name or event_data.get("WorkstationName") or event_data.get("CallerComputerName"),
            "message": message,
            "record_id": record_id,
            "channel": self.channel,
            "source_ip": event_data.get("IpAddress") or event_data.get("SourceNetworkAddress"),
            "logon_id": event_data.get("TargetLogonId") or event_data.get("SubjectLogonId"),
            "logon_type": event_data.get("LogonType"),
            "event_data": event_data,
        }

    def _extract_event_data(self, xml_root: ET.Element) -> Dict[str, str]:
        fields: Dict[str, str] = {}

        event_data = xml_root.find("evt:EventData", WINDOWS_EVENT_NS)
        if event_data is not None:
            for index, data_node in enumerate(event_data.findall("evt:Data", WINDOWS_EVENT_NS)):
                name = data_node.attrib.get("Name", f"Field{index}")
                fields[name] = (data_node.text or "").strip()

        user_data = xml_root.find("evt:UserData", WINDOWS_EVENT_NS)
        if user_data is not None:
            for node in user_data.iter():
                key = self._strip_namespace(node.tag)
                value = (node.text or "").strip()
                if key and value and key != "UserData":
                    fields[key] = value

        return fields

    def _extract_username(self, event_id: int, event_data: Dict[str, str]) -> str:
        username_fields = {
            4624: ["TargetUserName", "SubjectUserName"],
            4625: ["TargetUserName", "SubjectUserName"],
            4672: ["SubjectUserName", "TargetUserName"],
            4720: ["TargetUserName", "SamAccountName", "SubjectUserName"],
            4740: ["TargetUserName", "SubjectUserName"],
        }
        for field_name in username_fields.get(event_id, ["TargetUserName", "SubjectUserName"]):
            value = event_data.get(field_name)
            if value and value != "-":
                return value
        return "unknown"

    @staticmethod
    def _format_message(event_id: int, event_data: Dict[str, str]) -> str:
        username = event_data.get("TargetUserName") or event_data.get("SubjectUserName") or "unknown"
        source_ip = event_data.get("IpAddress") or event_data.get("SourceNetworkAddress") or "unknown"

        if event_id == 4624:
            return f"Successful logon for user '{username}' from '{source_ip}'."
        if event_id == 4625:
            return f"Failed logon for user '{username}' from '{source_ip}'."
        if event_id == 4672:
            return f"Special privileges assigned to user '{username}'."
        if event_id == 4720:
            return f"User account '{username}' was created."
        if event_id == 4740:
            return f"User account '{username}' was locked out."
        return "Security event"

    @staticmethod
    def _parse_timestamp(timestamp: str) -> datetime:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    @staticmethod
    def _read_text(node: Optional[ET.Element]) -> str:
        if node is None or node.text is None:
            return ""
        return node.text.strip()

    @staticmethod
    def _read_attr(node: Optional[ET.Element], attribute_name: str) -> str:
        if node is None:
            return ""
        return str(node.attrib.get(attribute_name, "")).strip()

    @staticmethod
    def _read_int(node: Optional[ET.Element]) -> int:
        if node is None or node.text is None:
            return 0
        try:
            return int(node.text)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _strip_namespace(tag_name: str) -> str:
        return tag_name.split("}", 1)[-1] if "}" in tag_name else tag_name

    @staticmethod
    def _safe_close(handle) -> None:
        if handle is None or win32evtlog is None:
            return

        close_method = getattr(win32evtlog, "EvtClose", None)
        if close_method is None:
            return

        try:
            close_method(handle)
        except Exception:
            LOGGER.debug("Unable to close event handle cleanly", exc_info=True)
