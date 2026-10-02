"""Independent strict typed/raw-wire oracle; no source imports or normalization."""
import json
import math
import sys


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, ('duplicate JSON key', key)
        result[key] = value
    return result


def parse(text):
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=lambda x: (_ for _ in ()).throw(AssertionError(x)))


def equal(a, b, path='$'):
    assert type(a) is type(b), (path, type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        assert a.keys() == b.keys(), (path, a.keys() ^ b.keys())
        for key in a:
            equal(a[key], b[key], path + '.' + key)
    elif isinstance(a, list):
        assert len(a) == len(b), (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            equal(x, y, f'{path}[{i}]')
    elif isinstance(a, float):
        assert math.isfinite(a) and a.hex() == b.hex(), (path, a.hex(), b.hex())
    else:
        assert a == b, (path, a, b)


# Negative controls establish that value equality alone is insufficient.
for left, right in [(1, 1.0), (True, 1), (0.0, -0.0), ({"id": "a"}, {"id": "b"})]:
    try:
        equal(left, right)
    except AssertionError:
        pass
    else:
        raise AssertionError("typed oracle accepted a changed value")
left, right = parse(sys.stdin.read())
assert type(left) is str and type(right) is str
equal(parse(left), parse(right))
print("typed wire equal")
