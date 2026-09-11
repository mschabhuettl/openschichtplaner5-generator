"""Synthetic characterization, not desired behavior; no DBF/HTTP/personal data.

Run with PYTHONPATH pointing at the original library checkout.
"""
import uuid

from sp5lib.database import SP5Database


def probe(order, shift_ids=None, absence_interval=None, special=None):
    day = "2026-09-07"
    shift_ids = shift_ids or [5 + kind for kind in order]
    tables = {"MASHI": [
        {"EMPLOYEEID": 10, "DATE": day, "SHIFTID": shift_id, "TYPE": kind}
        for kind, shift_id in zip(order, shift_ids, strict=True)
    ]}
    if absence_interval is not None:
        tables["ABSEN"] = [{"EMPLOYEEID": 10, "DATE": day, "LEAVETYPID": 7,
                            "INTERVAL": absence_interval, "START": 600, "END": 660}]
    if special is not None:
        tables["SPSHI"] = [{"EMPLOYEEID": 10, "DATE": day, **row} for row in special]
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
    daily_entry = db.get_schedule_day(day)[0]
    weekly_entry = db.get_schedule_week(day)["days"][0]["entries"][0]
    if absence_interval is not None:
        for entry in (daily_entry, weekly_entry):
            assert entry["kind"] == "absence"
            assert not {"interval", "start_time", "end_time"}.intersection(entry)
        absence = next(r for r in db.get_schedule(2026, 9) if r["kind"] == "absence")
        assert absence["interval"] == absence_interval
        assert absence["start_time"] == (600 if absence_interval == 3 else 0)
        assert absence["end_time"] == (660 if absence_interval == 3 else 0)
    if special is not None:
        monthly_special = [r for r in db.get_schedule(2026, 9) if r["kind"] == "special_shift"]
        assert len(monthly_special) == len(special)
        assert all("startend" not in r and "duration" not in r for r in monthly_special)
        for entry in (daily_entry, weekly_entry):
            assert entry["kind"] == "special_shift"
            assert entry["spshi_id"] == special[-1]["ID"]
            assert entry["spshi_startend"] == special[-1]["STARTEND"]
            assert entry["spshi_duration"] == special[-1]["DURATION"]
    daily = daily_entry["shift_id"]
    weekly = weekly_entry["shift_id"]
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
    for kind in (0, 1):
        for shift_ids in ([5, 6], [6, 5]):
            monthly, daily, weekly = probe((kind, kind), shift_ids)
            selected = "ist" if kind == 0 else "soll"
            other = "soll" if kind == 0 else "ist"
            assert sorted(monthly[selected]) == [5, 6]
            assert monthly[other] == []
            assert sorted(monthly["both"]) == [5, 6]
            assert daily == shift_ids[-1]
            assert weekly == daily
            checks += 5
    for interval in range(4):
        monthly, daily, weekly = probe((0,), absence_interval=interval)
        assert monthly["ist"] == [5]
        assert daily is None
        assert weekly is None
    special_cases = 0
    for kind in (0, 1):
        for shift_id in (0, 5):
            first = {"ID": 1, "SHIFTID": shift_id, "TYPE": kind,
                     "STARTEND": "0800-1000", "DURATION": 2.0}
            second = {**first, "ID": 2, "STARTEND": "1600-1900", "DURATION": 3.0}
            for rows in ([first], [first, second], [second, first]):
                monthly, daily, weekly = probe((0,), special=rows)
                assert monthly["ist"] == [5]
                assert daily == shift_id
                assert weekly == shift_id
                special_cases += 1
    print(f"PASS: {special_cases} special-duty combinations, 156 assertions; "
          "day/week keep last special, monthly omits its time detail")
    print("PASS: 4 absence intervals, 40 assertions; day/week hide duty and time window")
    print(f"PASS: 8 synthetic source orders, {checks} assertions; "
          "day/week lose both cross-plan and same-plan duties")


if __name__ == "__main__":
    main()
