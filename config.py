import os
import yaml

_cache = {"mtime": 0, "cfg": None}

REQUIRED = {
    "account_handle": str, "profile_dir": str, "voice": str, "model": str,
    "budget": dict, "trends": dict, "posting": dict, "follows": dict, "sniping": dict,
}

def load(path="config.yaml"):
    m = os.path.getmtime(path)
    if _cache["mtime"] == m:
        return _cache["cfg"]
    raw = yaml.safe_load(open(path))
    for k, t in REQUIRED.items():
        if k not in raw:
            raise SystemExit("config missing required key: " + k)
        if not isinstance(raw[k], t):
            raise SystemExit("config key %s must be %s" % (k, t.__name__))
    for k in ("actions_per_hour", "actions_per_day", "pause_min_ms", "pause_max_ms"):
        if k not in raw["budget"]:
            raise SystemExit("config.budget missing " + k)
    raw["trends"].setdefault("seeds", ["AI agents", "startup growth"])
    raw["posting"].setdefault("max_per_day", 5)
    raw["posting"].setdefault("min_gap_minutes", 100)
    _cache.update(mtime=m, cfg=raw)
    return raw