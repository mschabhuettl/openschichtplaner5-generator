"""Independent Python JSON semantic oracle; no JS codec expected values."""
import json
import math
import sys


def signature(value):
    if type(value) is int:
        return ["int", str(value)]
    if type(value) is float:
        assert math.isfinite(value), "nonfinite float"
        return ["float", value.hex()]
    if isinstance(value, dict):
        return {key: signature(item) for key, item in value.items()}
    if isinstance(value, list):
        return [signature(item) for item in value]
    return [type(value).__name__, value]


def compare(source, output):
    expected = signature(json.loads(source))
    actual = signature(json.loads(output))
    assert actual == expected, (expected, actual)


if __name__ == "__main__":
    cases = json.load(sys.stdin)
    for case in cases:
        compare(case["source"], case["output"])
    print(json.dumps({"compared": len(cases), "oracle": "Python int / float.hex / recursive type"}))
