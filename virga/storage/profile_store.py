from __future__ import annotations

"""
Persistent profile storage — one JSON file per operator in %APPDATA%/Virga/.

Profile schema:
    callsign    : str  (uppercase, used as filename key)
    name        : str  (operator display name)
    created     : str  (ISO datetime)
    analysis    : dict | None
        f0_hz   : float
        f0_label: str
    eq          : dict | None
        ragchew : {band_hz_str: gain_db, ...}
        contest : {band_hz_str: gain_db, ...}
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA", Path.home())
    d = Path(base) / "Virga" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(callsign: str) -> Path:
    return _appdata_dir() / f"{callsign.upper()}.json"


def _empty_profile(callsign: str, name: str) -> dict:
    return {
        "callsign": callsign.upper(),
        "name": name,
        "created": datetime.now().isoformat(timespec="seconds"),
        "analysis": None,
        "eq": None,
    }


# ── Public API ──────────────────────────────────────────────────────────────

def list_profiles() -> list[dict]:
    """Return all saved profiles, sorted by callsign."""
    profiles = []
    for p in sorted(_appdata_dir().glob("*.json")):
        try:
            profiles.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return profiles


def load(callsign: str) -> dict | None:
    p = _path(callsign)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def create(callsign: str, name: str) -> dict:
    profile = _empty_profile(callsign, name)
    save(profile)
    return profile


def save(profile: dict) -> None:
    _path(profile["callsign"]).write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )


def delete(callsign: str) -> None:
    p = _path(callsign)
    if p.exists():
        p.unlink()


def update_analysis(callsign: str, f0_hz: float, f0_label: str,
                    freqs=None, ltass_db=None) -> dict:
    profile = load(callsign) or _empty_profile(callsign, callsign)
    profile["analysis"] = {
        "f0_hz": f0_hz,
        "f0_label": f0_label,
        "freqs":    freqs.tolist() if freqs is not None else None,
        "ltass_db": ltass_db.tolist() if ltass_db is not None else None,
    }
    save(profile)
    return profile


def update_eq(callsign: str, mode: str, band_gains: dict[int, float]) -> dict:
    """mode is 'ragchew' or 'contest'."""
    profile = load(callsign) or _empty_profile(callsign, callsign)
    if profile["eq"] is None:
        profile["eq"] = {}
    profile["eq"][mode] = {str(k): v for k, v in band_gains.items()}
    save(profile)
    return profile
