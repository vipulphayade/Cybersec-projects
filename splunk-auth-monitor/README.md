# Splunk Auth Monitor

`splunk-auth-monitor` is a Python-based cybersecurity monitoring project that collects Windows Security Event Logs, analyzes authentication activity for suspicious behavior, and optionally forwards telemetry to Splunk through the HTTP Event Collector (HEC).

The project is designed as a portfolio-ready security engineering tool. It demonstrates log collection, detection engineering, alert generation, defensive telemetry forwarding, and a local-analysis fallback mode when Splunk is not configured.

## Project Overview

The monitor focuses on these Windows authentication events:

- `4624` - Successful logon
- `4625` - Failed logon
- `4672` - Special privileges assigned to new logon
- `4740` - Account locked out
- `4720` - User account created

The tool collects these events from the Windows Security log, converts them into structured Python dictionaries, runs detection logic, prints alerts to the console, exports alerts to JSON for local evidence retention, and optionally sends both raw events and alerts to Splunk.

## Folder Structure

```text
splunk-auth-monitor/
├── collector/
│   └── event_collector.py
├── detection/
│   └── auth_detector.py
├── integration/
│   ├── json_exporter.py
│   └── splunk_sender.py
├── config/
│   └── config.yaml
├── utils/
│   └── logger.py
├── main.py
├── requirements.txt
└── README.md
```

## Architecture

The application is organized into small, security-focused modules:

1. `collector/event_collector.py`
   Reads Windows Security Event Logs with `win32evtlog`, extracts key fields, and returns structured events.
2. `detection/auth_detector.py`
   Applies correlation logic to identify brute force activity, suspicious login times, privilege escalation patterns, and account lockouts.
3. `integration/splunk_sender.py`
   Sends JSON payloads to Splunk HEC and handles network failures gracefully.
4. `integration/json_exporter.py`
   Persists alerts to a local JSON file so detections can be reviewed or shared even without a SIEM connection.
5. `utils/logger.py`
   Configures consistent application logging for operational visibility.
6. `main.py`
   Orchestrates configuration loading, event collection, detection execution, console alerts, and optional Splunk forwarding.

### Architecture Diagram Explanation

```text
Windows Security Log
        |
        v
WindowsSecurityEventCollector
        |
        v
AuthenticationDetector
        |
        +--> Console Alerts
        |
        +--> JSON Alert Export
        |
        +--> SplunkHECSender (optional)
                |
                v
             Splunk SIEM
```

## Detection Logic

### Brute Force Attack

The detector tracks failed login events (`4625`) over a rolling 5-minute window. If more than 10 failures are observed for the same user and source IP combination, the monitor raises a high-severity brute force alert.

### Privilege Escalation

The detector correlates a special-privilege event (`4672`) with a recent successful login (`4624`). If privileged access is assigned shortly after a logon, the monitor raises an alert for possible privilege escalation.

### Account Lockout Attack

Any account lockout event (`4740`) generates an immediate high-severity alert because lockouts often follow password spraying, brute force activity, or malicious login attempts.

### Suspicious Login Times

Interactive successful logins (`4624`) outside business hours, defined by default as `08:00` to `18:00`, generate a medium-severity alert.

## Installation

### Requirements

- Windows host with access to the Security Event Log
- Python 3
- Administrator or sufficient privileges to read Windows Security logs
- Optional Splunk instance with HTTP Event Collector enabled

### Install Dependencies

```powershell
pip install -r requirements.txt
```

If you prefer a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

The application reads settings from `config/config.yaml`.

```yaml
app:
  log_level: INFO
  poll_interval_seconds: 15
  historical_lookback_minutes: 15
  start_from_latest: false

detection:
  brute_force_threshold: 10
  brute_force_window_minutes: 5
  business_hours_start: 8
  business_hours_end: 18
  privilege_window_minutes: 10

alerts:
  export_json:
    enabled: true
    path: output/alerts.json

splunk:
  enabled: false
  hec_url: https://localhost:8088/services/collector
  token: YOUR_SPLUNK_TOKEN
  index: security
  source: splunk-auth-monitor
  sourcetype: json
  verify_tls: false
  timeout_seconds: 10
```

## How to Run the Application

Run continuously:

```powershell
python main.py
```

Run once and exit:

```powershell
python main.py --oneshot
```

Force local analysis mode:

```powershell
python main.py --no-splunk
```

When alert export is enabled, detections are also written to `output/alerts.json`.

## How to Enable Splunk Integration

1. Enable HTTP Event Collector in Splunk.
2. Create an HEC token.
3. Update `config/config.yaml`:

```yaml
splunk:
  enabled: true
  hec_url: https://localhost:8088/services/collector
  token: YOUR_REAL_HEC_TOKEN
  index: security
```

4. Start the monitor:

```powershell
python main.py
```

If Splunk is unreachable, the application logs the error and continues local analysis.

## JSON Alert Export

The monitor can persist alerts locally in JSON format. This is useful for:

- collecting evidence during local testing
- sharing detections in a portfolio project
- reviewing alerts when Splunk is disabled

Example exported alert:

```json
[
  {
    "alert_type": "brute_force_attempt",
    "severity": "high",
    "timestamp": "2026-04-14T03:10:25.000000+00:00",
    "username": "testuser",
    "host": "WORKSTATION01",
    "source_ip": "192.168.1.50",
    "description": "More than 10 failed logon events were observed for user 'testuser' from '192.168.1.50' within 5 minutes.",
    "supporting_event_id": 4625,
    "metadata": {
      "failed_attempt_count": 11,
      "window_minutes": 5
    }
  }
]
```

## How to Simulate Authentication Attacks

Use a lab or isolated Windows test environment only.

### Failed Logons / Brute Force Conditions

- Attempt multiple logins with an incorrect password against a test account.
- You can also use `runas /user:HOSTNAME\testuser cmd` and intentionally enter the wrong password repeatedly.

### Privilege Escalation Patterns

- Log in with a local administrator account or a test account that has been added to the Administrators group.
- This commonly produces Event `4672` following a successful logon.

### Account Lockout

- Configure an account lockout threshold in local security policy or domain policy.
- Intentionally fail authentication until the account locks out, producing Event `4740`.

### User Creation

```powershell
net user socdemo P@ssw0rd! /add
```

## Example Splunk Detection Queries

### Brute Force Attacks

```spl
index=security EventCode=4625
| stats count by user host
| where count > 10
```

### Privilege Escalation

```spl
index=security EventCode=4672
```

### Account Lockouts

```spl
index=security EventCode=4740
```

### After-Hours Logins

```spl
index=security EventCode=4624
| eval hour=strftime(_time,"%H")
| where hour < 8 OR hour >= 18
| table _time user host src_ip
```

## Cybersecurity Use Case

This project supports SOC monitoring by giving defenders rapid visibility into Windows authentication behavior. It can help analysts:

- detect password spraying or brute force attempts
- identify suspicious privileged logons
- surface account lockout activity for incident triage
- enrich Splunk with host-level authentication telemetry
- demonstrate practical detection engineering skills in a portfolio

## Notes for Portfolio Presentation

- The project shows modular security engineering design.
- It demonstrates how endpoint telemetry can be normalized before SIEM ingestion.
- It includes both detection content and Splunk integration.
- It can be extended with dashboards, Sigma mappings, or enrichment workflows.
