"""Read-only synthetic characterization of upstream Ist/Soll accounting.

Run with the generator venv and PYTHONPATH pointing at the library checkout.
No API, DBF files or personal data are accessed. Assertions characterize the
audited upstream behavior, NOT the desired accounting contract; after an
upstream fix they should fail and the documented findings must be revisited.
"""

import json

from sp5lib.database import SP5Database


def probe(plan_types: tuple[int, ...], *, cycle: bool = False) -> dict:
    day = "2026-09-07"
    employee = {"ID": 10, "CALCBASE": 0, "HRSDAY": 0}
    shift = {"ID": 5, **{f"DURATION{i}": 8 for i in range(8)},
             **{f"STARTEND{i}": "08:00-16:00" for i in range(8)}}
    tables = {
        "MASHI": [
            {"EMPLOYEEID": 10, "DATE": day, "SHIFTID": 5, "TYPE": kind}
            for kind in plan_types
        ],
        "CYCLE": [{"ID": 1, "SIZE": 1, "UNIT": 0}] if cycle else [],
        "CYENT": [{"CYCLEEID": 1, "INDEX": 0, "SHIFTID": 5}],
        "CYASS": [
            {"EMPLOYEEID": 10, "CYCLEID": 1, "START": day, "END": day,
             "ENTRANCE": 0}
        ] if cycle else [],
    }
    # Bypass the filesystem constructor; replace only source readers.
    db = object.__new__(SP5Database)
    db._read = lambda table: tables.get(table, [])
    db.get_employee = lambda employee_id: employee
    db.get_shifts = lambda **kwargs: [shift]
    db.get_leave_types = lambda **kwargs: []
    db.get_employees = lambda **kwargs: [employee]
    db.get_extracharges = lambda **kwargs: [
        {"ID": 1, "NAME": "Synthetic all-day", "VALIDITY": 1,
         "DATE": day, "START": 0, "END": 0}
    ]
    result = db.calculate_time_balance(10, 2026)
    charges = db.calculate_extracharge_hours(2026, 9, 10)
    daily_charges = db.extracharge_hours_by_day(2026, 9, 10)
    month = result["months"][8]
    return {
        "plan_types": plan_types,
        "cycle": cycle,
        "september_actual_hours": month["actual_hours"],
        "annual_actual_hours": result["total_actual_hours"],
        "surcharge_hours": charges[0]["hours"],
        "surcharge_employee_days": charges[0]["shift_count"],
        "daily_surcharge_hours": sum(row["hours"] for row in daily_charges),
    }


def main() -> None:
    cases = [((0,), False, 8), ((1,), False, 8), ((0, 1), False, 16),
             ((), True, 8), ((1,), True, 8), ((0, 1), True, 16)]
    results = []
    for kinds, cycle, expected in cases:
        result = probe(kinds, cycle=cycle)
        assert result["september_actual_hours"] == expected, result
        assert result["annual_actual_hours"] == expected, result
        assert result["surcharge_hours"] == expected, result
        assert result["daily_surcharge_hours"] == expected, result
        assert result["surcharge_employee_days"] == 1, result
        results.append(result)
    print(json.dumps({"synthetic_only": True, "characterization": results}, indent=2))


if __name__ == "__main__":
    main()
