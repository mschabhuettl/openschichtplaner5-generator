"""Characterize the upstream API TTL cache without network or real data."""
import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def verify(path):
    spec = importlib.util.spec_from_file_location("synthetic_source_cache", path)
    cache = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cache)
    now = [0.0]
    cache.time = SimpleNamespace(monotonic=lambda: now[0])
    key = "shifts:list:True"
    source = [{"ID": 1, "STARTEND0": "08:00-16:00"}]
    cache.put(key, source)
    # An external source replacement does not call the API write invalidator.
    source = [{"ID": 1, "STARTEND0": "08:00-20:00"}]
    now[0] = 30.0
    first = cache.get(key)
    now[0] = 59.0
    assert cache.get(key) == first != source
    now[0] = 61.0
    assert cache.get(key) is None
    cache.put(key, source)
    assert cache.get(key) == source
    assert cache.invalidate("shifts:") == 1
    assert cache.get(key) is None
    return {"synthetic_only": True, "cases": 3,
            "repeated_response_proves_freshness": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.cache)))
