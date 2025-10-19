from __future__ import annotations
import httpx, yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# try common ATS endpoints
def probe_greenhouse(handle: str) -> bool:
    try:
        r = httpx.get(f"https://boards.greenhouse.io/{handle}", timeout=8)
        return r.status_code == 200 and "greenhouse" in r.url.host
    except Exception:
        return False

def probe_lever(handle: str) -> bool:
    try:
        r = httpx.get(f"https://jobs.lever.co/{handle}", timeout=8)
        return r.status_code == 200 and "lever.co" in r.url.host
    except Exception:
        return False

def autodetect_provider(name: str) -> Optional[Tuple[str,str]]:
    """
    Heuristic: try a few handle variants for Greenhouse/Lever.
    E.g., 'ServiceNow' -> 'servicenow'
    """
    candidates = set()
    base = name.lower().replace("&","and").replace(".","").replace(" ","")
    candidates.add(base)
    # add a dashed variant
    if "-" not in base and len(base)>4:
        candidates.add(base.replace("inc","").strip("-"))
    # Try GH
    for c in candidates:
        if probe_greenhouse(c):
            return ("greenhouse", c)
    # Try Lever
    for c in candidates:
        if probe_lever(c):
            return ("lever", c)
    return None

def load_targets(cfg_path: str = "config/targets.yml") -> Dict[str, List[Dict]]:
    data = yaml.safe_load(Path(cfg_path).read_text())
    return data

def resolve_targets(data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Returns {category: [{name, provider, handle}]}, skipping those we cannot resolve.
    If provider+handle already present, we validate. If missing, we try autodetect.
    """
    out = {}
    for cat, items in data.items():
        resolved: List[Dict] = []
        for item in items:
            name = item.get("name") or ""
            provider = item.get("provider")
            handle = item.get("handle")
            if provider and handle:
                ok = probe_greenhouse(handle) if provider=="greenhouse" else probe_lever(handle) if provider=="lever" else False
                if ok:
                    resolved.append({"name": name, "provider": provider, "handle": handle})
                continue
            # try autodetect
            found = autodetect_provider(name)
            if found:
                prov, h = found
                resolved.append({"name": name, "provider": prov, "handle": h})
        out[cat] = resolved
    return out
