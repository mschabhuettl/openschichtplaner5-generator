"""Synthetic characterization, not desired behavior; no DBF/HTTP/personal data.

Run with PYTHONPATH pointing at the original library checkout.
"""
import uuid

from sp5lib.database import SP5Database


def probe(order):
    day = "2026-09-07"
    tables = {"MASHI": [
        {"EMPLOYEEID": 10, "DATE": day, "SHIFTID": 5 + kind, "TYPE": kind}
        for kind in order
    ]}
    db = object.__new__(SP5Database)
    db.db_path = f"synthetic-views-{uuid.uuid4()}"
    db._read = lambda table: tables.get(table, [])
    db.get_employees = lambda **kwargs: [{"ID": 10}]
    db.get_shifts = lambda **kwargs: [{"ID": 5}, {"ID": 6}]
    db.get_workplaces = lambda **kwargs: []
    db.get_leave_types = lambda **kwargs: []
    monthly = {
        plan: [r["shift_id"] for r in db.get_schedule(2026, 9, plan=plan)
               if r["kind"] == "shift"]
        for plan in ("ist", "soll", "both")
    }
    daily = db.get_schedule_day(day)[0]["shift_id"]
    weekly = db.get_schedule_week(day)["days"][0]["entries"][0]["shift_id"]
    return monthly, daily, weekly


def main():
    checks = 0
    for order in ((0,), (1,), (0, 1), (1, 0)):
        monthly, daily, weekly = probe(order)
        assert monthly["ist"] == ([5] if 0 in order else [])
        assert monthly["soll"] == ([6] if 1 in order else [])
        assert sorted(monthly["both"]) == sorted(5 + kind for kind in order)
        assert daily == 5 + order[-1]
        assert weekly == daily
        checks += 5
    print(f"PASS: 4 synthetic source orders, {checks} assertions; day/week last-row wins")


if __name__ == "__main__":
    main()
