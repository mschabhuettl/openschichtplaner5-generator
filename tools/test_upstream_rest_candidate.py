"""Synthetic helper regression; set SP5_REST_ROUTER to the patched API file.

No real DBF, server startup or network. These are interval diagnostics, not
proof of full API/OSP5 integration or correct plan selection/accounting.
"""
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from tools.audit_upstream_work_time_plan import load_helpers


@pytest.mark.parametrize('spans,minimum,expected', [
    ([(8, 16), (15, 19)], 11, [('shift_overlap', 1)]),
    ([(8, 16), (16, 20)], 11, [('min_rest_hours_between_shifts', 0)]),
    ([(8, 16), (17, 21)], 11, [('min_rest_hours_between_shifts', 1)]),
    ([(8, 16), (27, 31)], 11, []),
    ([(8, 16), (15, 19)], 0, [('shift_overlap', 1)]),
    ([(8, 16), (16, 20)], 0, []),
    # A short nested duty must not conceal the still-running long duty.
    ([(8, 32), (10, 12), (24, 28)], 11,
     [('shift_overlap', 22), ('shift_overlap', 8)]),
    ([(8, 32), (10, 12), (33, 37)], 11,
     [('shift_overlap', 22), ('min_rest_hours_between_shifts', 1)]),
    ([], 11, []),
    ([(8, 32)], 11, []),  # 24h is not prohibited by a between-duty rest rule.
])
def test_rest_intervals(spans, minimum, expected):
    helpers = load_helpers(Path(os.environ['SP5_REST_ROUTER']))
    base = datetime(2026, 9, 7)
    blocks = [{'start': base + timedelta(hours=start),
               'end': base + timedelta(hours=end),
               'date': (base + timedelta(hours=start)).date()}
              for start, end in spans]
    # Patch globals on the actual extracted function, not the namespace copy.
    helpers._check_employee.__globals__['_collect_day_data'] = (
        lambda *args: ({}, blocks)
    )
    result = helpers._check_employee(None, 10, date(2026, 9, 7), date(2026, 9, 9),
                                     {'min_rest_hours_between_shifts': minimum})
    assert [(v['type'], v['value']) for v in result] == expected
    assert all(v['severity'] == 'error' for v in result)
