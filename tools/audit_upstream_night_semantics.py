"""Execute existing night classifiers on synthetic rows, without DB/network.

These statistical heuristics are not authoritative night-rule assignments.
Pass the library database.py and API reports.py from the audited checkouts.
"""
import argparse
import ast
import json
from pathlib import Path

from sp5lib import calculations as calc


def load_classifiers(database, reports):
    tree = ast.parse(database.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'SP5Database')
    names = {'_decode_startend', '_time_str_to_minutes', '_is_night_shift'}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods} == names
    cls.body = methods
    namespace = {'calc': calc}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(database), 'exec'), namespace)
    tree = ast.parse(reports.read_text())
    for name in ('is_night', 'categorize_shift'):
        matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                   and n.name == name]
        assert len(matches) == 1, (name, len(matches))
        exec(compile(ast.Module(body=matches, type_ignores=[]), str(reports), 'exec'), namespace)
    return namespace['SP5Database'](), namespace['is_night'], namespace['categorize_shift']


def verify(database, reports):
    db, fairness, category = load_classifiers(database, reports)
    cases = [
        ('18:00-23:00', None, (False, False, 'Nacht')),
        ('20:00-08:00', None, (False, True, 'Nacht')),
        ('05:00-13:00', None, (False, True, 'Früh')),
        ('22:00-06:00', None, (True, True, 'Nacht')),
        # The statistical fallback still counts a night when the actual weekday is day.
        ('22:00-06:00', '08:00-16:00', (True, True, 'Nacht')),
        ('08:00-16:00', '22:00-06:00', (True, False, 'Früh')),
        ('', None, (False, False, 'Sonstige')),
    ]
    for default, weekday, expected in cases:
        row = {'STARTEND0': default, 'STARTEND1': weekday or default}
        actual = (db._is_night_shift(row, 1), fairness(row), category(row))
        assert actual == expected, (row, actual, expected)
    return {'synthetic_only': True, 'cases': len(cases),
            'authoritative_night_mapping': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('reports', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.database, args.reports)))
