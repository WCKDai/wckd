#!/usr/bin/env python3
"""Add the re-canvass candidates to the worked example.

Every URL below was opened during the re-canvass on 2026-10-23; every score is a read of the linked page,
not a trial. `tried` stays false and `trial_notes` says so. Nothing here is invented.
"""
import json
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "examples" / "air-quality-monitor" / "landscape.json"
AT = "2026-10-23T14:21:16Z"


def ev(locator, summary, confidence=0.8):
    return [{"kind": "url", "locator": locator, "summary": summary, "captured_at": AT,
             "captured_by": "scout", "confidence": confidence, "grade": "found"}]


NEW = [
    {
        "id": "cand-airgradient", "name": "AirGradient indoor monitor (open firmware)",
        "kind": "commercial_cots", "locator": "https://www.airgradient.com/indoor/", "maturity": "stable",
        "license": "firmware open source; hardware commercial",
        "cost": {"keep": {"amount": 240, "currency": "USD", "confidence_class": "rom", "basis": "order-of-magnitude from the product page, one unit"}},
        "checked_at": AT, "tried": False,
        "trial_notes": "read-only inside the canvass time box: product page and datasheets, no unit ordered",
        "works": ["PM2.5 and CO2 in one calibrated unit", "open firmware, ESPHome-compatible", "supports local MQTT without their cloud"],
        "doesnt": ["cloud-first onboarding and their dashboard is the default path", "240 USD vs a 200 USD build ceiling", "no monthly narrative report"],
        "fit": [
            {"capability_id": "C1", "score": 0.75, "meets_bar": True, "notes": "spec'd PM accuracy inside 20%, but the unit price consumes the whole build budget"},
            {"capability_id": "C2", "score": 0.8, "meets_bar": True, "notes": "SCD4x-class CO2, ±(40 ppm + 5%)"},
            {"capability_id": "C3", "score": 0.6, "meets_bar": False, "notes": "alerts are cloud-side by default; local alerting needs the MQTT path"},
            {"capability_id": "C4", "score": 0.7, "meets_bar": True, "notes": "history exists, retention determined by their dashboard"},
            {"capability_id": "C5", "score": 0.75, "meets_bar": True, "notes": "purpose-built enclosure; field reliability not proven for 12 months at this price"},
            {"capability_id": "C6", "score": 0.3, "meets_bar": False, "notes": "dashboards, no plain-language monthly summary"},
        ],
        "evidence": ev("https://www.airgradient.com/indoor/", "product page: PM2.5 + CO2, open firmware, 240 USD class"),
    },
    {
        "id": "cand-airthings", "name": "Airthings Wave Plus (BLE, local integration)",
        "kind": "commercial_cots", "locator": "https://www.home-assistant.io/integrations/airthings_ble/", "maturity": "stable",
        "license": "proprietary hardware; local BLE integration in Home Assistant",
        "checked_at": AT, "tried": False,
        "trial_notes": "read-only: integration docs and product page; no unit ordered",
        "works": ["battery-powered, ~2 year life, no mains run cost", "CO2 plus radon/VOC/temp/humidity", "local BLE integration, no cloud account required"],
        "doesnt": ["radon-first product; CO2 is one channel among many", "per-unit price well above the ceiling", "BLE range limits placement; history lives in their app"],
        "fit": [
            {"capability_id": "C2", "score": 0.65, "meets_bar": False, "notes": "CO2 channel present; accuracy spec not published to the Bar's standard"},
            {"capability_id": "C3", "score": 0.65, "meets_bar": False, "notes": "their app alerts; local alerting via HA needs a host anyway"},
            {"capability_id": "C4", "score": 0.8, "meets_bar": True, "notes": "app history is solid; local retention needs HA recorder"},
            {"capability_id": "C5", "score": 0.8, "meets_bar": True, "notes": "sealed unit, battery life is the strongest 12-month story found"},
        ],
        "evidence": ev("https://www.home-assistant.io/integrations/airthings_ble/", "local BLE integration; CO2 among the measured channels"),
    },
    {
        "id": "cand-grafana", "name": "Grafana over Home Assistant history",
        "kind": "open_source", "locator": "https://grafana.com/grafana/dashboards/15524-air-quality/", "maturity": "mature",
        "license": "AGPLv3 (OSS); reporting is an Enterprise feature",
        "cost": {"run_monthly": {"amount": 0, "currency": "USD", "confidence_class": "budgetary", "basis": "self-hosted beside HA on existing host"}},
        "checked_at": AT, "tried": False,
        "trial_notes": "read-only: dashboard catalogue and plugin docs; not installed in the trial box",
        "works": ["history dashboards over the HA database", "alert rules with contact points", "community dashboards exist for air quality"],
        "doesnt": ["reporting/render-to-email is Enterprise", "another service to run and patch", "thresholds would live in two places (HA and Grafana)"],
        "fit": [
            {"capability_id": "C3", "score": 0.55, "meets_bar": False, "notes": "alerting exists but duplicates HA's; phone path is weaker than the HA app"},
            {"capability_id": "C4", "score": 0.85, "meets_bar": True, "notes": "strongest history view of the candidates, at the cost of a second service"},
            {"capability_id": "C6", "score": 0.35, "meets_bar": False, "notes": "panel images, not a narrative with calibration status; scheduled reporting is paid"},
        ],
        "evidence": ev("https://grafana.com/grafana/dashboards/15524-air-quality/", "air-quality dashboard listing; alerting and reporting tiers documented"),
    },
    {
        "id": "cand-cyd-scd41", "name": "cyd-scd41-co2-monitor (DIY, printed case)",
        "kind": "open_source", "locator": "https://github.com/JamesDavid/cyd-scd41-co2-monitor", "maturity": "experimental",
        "license": "repository licence at the linked page",
        "checked_at": AT, "tried": False,
        "trial_notes": "read-only: repository read; not flashed in the canvass time box",
        "works": ["SCD41 plus a printed enclosure in one project", "cheap display variant", "shows the enclosure shape the BEND needs"],
        "doesnt": ["no calibration routine or watchdog", "no history or phone path", "single maintainer, young repo"],
        "fit": [
            {"capability_id": "C2", "score": 0.75, "meets_bar": True, "notes": "SCD41 accuracy meets the Bar; needs ESPHome or equivalent for the host"},
            {"capability_id": "C5", "score": 0.6, "meets_bar": False, "notes": "enclosure exists; nothing about drift, dust or reconnects"},
        ],
        "evidence": ev("https://github.com/JamesDavid/cyd-scd41-co2-monitor", "repository: SCD41 monitor with printable case"),
    },
    {
        "id": "cand-printables-scd41", "name": "Printable SCD41 enclosure models",
        "kind": "physical_supplier", "locator": "https://www.printables.com/tag/scd41", "maturity": "stable",
        "checked_at": AT, "tried": False,
        "trial_notes": "read-only: model catalogue; no print made",
        "works": ["many vented designs, several with a filter pocket", "free, printable on a commodity printer"],
        "doesnt": ["geometry only: no sensor, no PCB, no calibration", "no airflow validation for any model"],
        "fit": [
            {"capability_id": "C5", "score": 0.5, "meets_bar": False, "notes": "solves the enclosure half of the BEND; the drift and reconnect half remains"},
        ],
        "evidence": ev("https://www.printables.com/tag/scd41", "enclosure model catalogue for the SCD41"),
    },
    {
        "id": "cand-sensor-community", "name": "Sensor.Community airrohr kit",
        "kind": "open_source", "locator": "https://sensor.community/en/sensors/airrohr/", "maturity": "mature",
        "license": "open hardware and firmware",
        "checked_at": AT, "tried": False,
        "trial_notes": "read-only: build instructions; no kit ordered",
        "works": ["proven outdoor enclosure and power design", "huge fleet, so failure modes are documented", "cheap"],
        "doesnt": ["PM-only: no CO2 channel", "SDS011-class sensor is not indoor-grade at low concentrations", "uploads to a public map by default"],
        "fit": [
            {"capability_id": "C1", "score": 0.5, "meets_bar": False, "notes": "PM measured, but indoor low-concentration accuracy and privacy both fail the Bar"},
            {"capability_id": "C5", "score": 0.55, "meets_bar": False, "notes": "enclosure lessons transfer; the sensor stack does not"},
        ],
        "evidence": ev("https://sensor.community/en/sensors/airrohr/", "airrohr build guide: PM-only, public upload"),
    },
    {
        "id": "cand-scd41", "name": "Sensirion SCD41 module (second source)",
        "kind": "physical_supplier", "locator": "https://sensirion.com/products/catalog/SCD41", "maturity": "stable",
        "checked_at": AT, "tried": False,
        "trial_notes": "read-only: datasheet and product page; bench comparison not run",
        "works": ["±(40 ppm + 5%) with on-chip humidity compensation", "ESPHome driver exists", "photoacoustic, small footprint"],
        "doesnt": ["3.3 V SMD part: needs a carrier board", "same drift story as any NDIR/photoacoustic cell; calibration still required", "not cheaper than the incumbent at one-off volume"],
        "fit": [
            {"capability_id": "C2", "score": 0.8, "meets_bar": True, "notes": "meets the accuracy Bar; the incumbent cand-co2 is cheaper per unit at volume"},
        ],
        "evidence": ev("https://sensirion.com/products/catalog/SCD41", "SCD41 product page and SCD4x datasheet"),
    },
]

SEARCHES = [
    ("C3", "commercial_cots", "AirGradient open-source air quality monitor indoor", "web_search", 4, ["cand-airgradient"]),
    ("C2", "physical_supplier", "SCD41 CO2 sensor module Sensirion datasheet", "web_search", 4, ["cand-scd41"]),
    ("C4", "open_source", "Home Assistant air quality dashboard Grafana history", "web_search", 4, ["cand-grafana"]),
    ("C4", "commercial_cots", "Airthings Wave Plus Home Assistant integration local", "web_search", 4, ["cand-airthings"]),
    ("C5", "open_source", "3D printed enclosure SCD41 CO2 sensor filter", "web_search", 4, ["cand-cyd-scd41", "cand-printables-scd41"]),
    ("C5", "open_source", "Sensor.Community indoor air quality kit", "web_search", 4, ["cand-sensor-community"]),
]


def main():
    land = json.loads(P.read_text())
    have = {c["id"] for c in land["candidates"]}
    land["candidates"] += [c for c in NEW if c["id"] not in have]
    for cap, cls, query, tool, n, kept in SEARCHES:
        land["search_log"].append({"capability_id": cap, "source_class": cls, "query": query, "tool": tool,
                                   "at": AT, "results_count": n, "kept": kept})
    land["time_box"] = "2 h for the original canvass; +40 min re-canvass on 2026-10-23 for C2-C6"
    land["summary"] += (" Re-canvass 2026-10-23: seven candidates added across C2-C6 (AirGradient, Airthings, "
                        "Grafana, cyd-scd41, Printables enclosures, Sensor.Community, SCD41 module). No new candidate "
                        "beats the incumbent fit on any capability, so the verdicts stand; the G2 target of >=3 "
                        "candidates per capability is now met.")
    P.write_text(json.dumps(land, indent=2) + "\n")
    print("candidates:", len(land["candidates"]), "search rows:", len(land["search_log"]))


if __name__ == "__main__":
    main()
