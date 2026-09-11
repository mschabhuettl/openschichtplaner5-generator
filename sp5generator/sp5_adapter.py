"""Read-only translation of the optional sp5lib facade into the public contract."""

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from hashlib import sha256
import json
import math
import re
from zoneinfo import ZoneInfo

from .hierarchy import group_tree, resolve_group_selection
from .domain import MAX_PLANNING_DAYS

from .models import (
    BoundaryWork,
    Employee,
    Objectives,
    Interval,
    Position,
    Shift,
    Demand,
    Restriction,
    RuleProfile,
    Snapshot,
    Assignment,
)


def _unique_rows(rows):
    seen = set()
    result = []
    for row in rows:
        key = json.dumps(row, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def _nominal_bookings(db, employees, start, end, *, actual_bookings=None):
    """Normalize the public BOOK facade, without mistaking missing access for zero."""
    if not hasattr(db, "get_bookings"):
        return None
    from sp5lib.database import SP5Database
    from sp5lib.dbf_reader import get_table_fields

    if isinstance(db, SP5Database):
        # The library maps missing/unreadable files and short headers to [].
        # Use its schema reader, but verify access separately so those states
        # cannot be mistaken for a successfully read empty BOOK table.
        path = db._table("BOOK")
        try:
            with open(path, "rb") as source:
                source.read(1)
        except FileNotFoundError:
            return None
        except OSError:
            raise ValueError("Buchungsquelle ist nicht lesbar.") from None
        fields = {field["name"] for field in get_table_fields(path)}
        if not {"EMPLOYEEID", "DATE", "TYPE", "VALUE"} <= fields:
            raise ValueError("Buchungsquelle enthält keine vollständigen Pflichtfelder.")
    result = {e["ID"]: [] for e in employees}
    month = start.replace(day=1)
    while month <= end:
        rows = db.get_bookings(year=month.year, month=month.month)
        if not isinstance(rows, list):
            raise ValueError("Unvollständige Buchungsquelle")
        for row in rows:
            if not isinstance(row, dict) or type(row.get("employee_id")) is not int:
                raise ValueError("Unvollständige Buchungszuordnung")
            if row["employee_id"] not in result:
                continue
            # Validate dates before period filtering; a missing date is not an
            # out-of-period row. The facade contract uses ISO calendar dates.
            day = date.fromisoformat(row["date"])
            if (day.year, day.month) != (month.year, month.month):
                continue
            if not start <= day <= end:
                continue
            kind = row["type"]
            if type(kind) is not int:
                raise ValueError("Ungültiger Buchungstyp")
            if kind not in (0, 1):
                continue
            value = row["value"]
            if value is None or value == "" or isinstance(value, bool):
                raise ValueError("Ungültiger Buchungswert")
            _minutes(value)  # Reject non-finite/malformed values, retain hours.
            if kind == 0:
                if actual_bookings is not None:
                    actual_bookings[row["employee_id"]].append({
                        "date": day.isoformat(), "type": 0,
                        "value_hours": float(value),
                        "source_id": row.get("id"),
                    })
                continue
            result[row["employee_id"]].append(
                {"DATE": day.isoformat(), "TYPE": 1, "VALUE": value}
            )
        if month.year == end.year and month.month == end.month:
            break
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    return result


def _scope_schedule(db, scope, year, month, **kwargs):
    rows = _unique_rows(
        row
        for gid in scope
        for row in db.get_schedule(year, month, group_id=gid, **kwargs)
    )
    if not hasattr(db, "get_spshi_entries_for_day"):
        return rows
    details = {}
    for day in sorted({r["date"] for r in rows if r.get("kind") == "special_shift"}):
        details[day] = _unique_rows(
            entry for gid in scope for entry in db.get_spshi_entries_for_day(day, group_id=gid)
        )
    result = []
    for row in rows:
        if row.get("kind") == "special_shift":
            matches = [v for v in details.get(row.get("date"), [])
                       if v.get("employee_id") == row.get("employee_id")
                       and v.get("shift_id") == row.get("shift_id")
                       and v.get("workplace_id") == row.get("workplace_id")
                       and v.get("type", 0) == row.get("spshi_type", 0)]
            if len(matches) == 1:
                row = {**row, "startend": matches[0].get("startend"),
                       "duration": matches[0].get("duration"), "detail_id": matches[0].get("id")}
        result.append(row)
    return result


def _reference_schedule(db, scope, year, month, period_start, period_end, plan):
    """Select regular baseline duties only; preserve Ist context and availability."""
    from sp5lib.calculations import to_date

    actual = _scope_schedule(db, scope, year, month, plan="ist")
    if plan == "ist" or (year, month) < (period_start.year, period_start.month) or (year, month) > (period_end.year, period_end.month):
        return actual

    def selected(row):
        day = to_date(row.get("date"))
        return row.get("kind") == "shift" and day is not None and period_start <= day <= period_end

    planned = _scope_schedule(db, scope, year, month, plan=plan)
    return [row for row in actual if not selected(row)] + [row for row in planned if selected(row)]


def _parse_native_windows(value):
    """Parse every native interval; never silently discard malformed pieces."""
    tokens = str(value or "").replace(";", " ").split()
    windows = []
    for token in tokens:
        match = re.fullmatch(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", token)
        if not match:
            raise ValueError("Ungültiges Dienstzeitformat")
        a, b, c, d = map(int, match.groups())
        if a > 23 or b > 59 or c > 24 or d > 59 or (c == 24 and d):
            raise ValueError("Ungültige Uhrzeit")
        # Native 00:00-00:00 is an unused time slot, not a 24-hour duty.
        if (a, b, c, d) != (0, 0, 0, 0):
            windows.append((a * 60 + b, c * 60 + d))
    return windows


def _minutes(hours):
    try:
        value = Decimal(str(hours or 0))
        if not value.is_finite():
            raise ValueError("Ungültige Stundenangabe")
        return int((value * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except DecimalException:
        raise ValueError("Ungültige Stundenangabe") from None


def _local(day, minute, zone):
    naive = datetime.combine(day, datetime.min.time()) + timedelta(minutes=minute)
    candidates = [naive.replace(tzinfo=zone, fold=f) for f in (0, 1)]
    valid = [
        v
        for v in candidates
        if v.astimezone(dt_timezone.utc).astimezone(zone).replace(tzinfo=None) == naive
    ]
    if not valid or len({v.utcoffset() for v in valid}) != 1:
        raise ValueError("Lokale Zeit benötigt explizite Klärung der Zeitumstellung")
    return valid[0]


def import_snapshot(
    db, period_start: date, period_end: date, team_id: str | None = None,
    timezone: str = "Europe/Vienna", team_ids: list[str] | None = None,
    existing_plan_mode: str = "reference",
    reference_plan: str = "ist",
) -> Snapshot:
    """Read from an explicitly supplied library database; never writes or opens a default source.

    Imports are intentionally unconfirmed until source ambiguities and additional
    rule/approval data have been resolved. Native names are runtime display data.
    """
    from sp5lib import calculations as calc

    if not 0 <= (period_end - period_start).days < MAX_PLANNING_DAYS:
        raise ValueError(f"Planungszeitraum muss 1 bis {MAX_PLANNING_DAYS} Kalendertage umfassen.")
    if (period_start - date.min).days < 31 or (date.max - period_end).days < 32:
        raise ValueError("Zeitraum bietet keinen Platz für den erforderlichen Randkontext.")
    if existing_plan_mode not in ("reference", "fixed"):
        raise ValueError("Bestehender Plan: Modus muss reference oder fixed sein.")
    if reference_plan not in ("ist", "soll"):
        raise ValueError("Referenzplansicht muss ist oder soll sein.")
    zone = ZoneInfo(timezone)
    groups = db.get_groups() if hasattr(db, "get_groups") else [{"ID": int(str(team_id).removeprefix("sp5:group:"))}]
    scope = resolve_group_selection(groups, team_id, team_ids)
    native_team = scope[0]
    context_start, context_end = (
        period_start - timedelta(days=31),
        period_end + timedelta(days=31),
    )
    unresolved = [
        "Regelprofile, Dienstarten und Freigaben ausdrücklich bestätigen. Zusätzliche Qualifikationsanforderungen bei Bedarf hinterlegen.",
        "Konsistenz des Imports gegen gleichzeitige Quelländerungen lokal bestätigen.",
        "Randkontext und Ausgleichszeiträume nach Auswahl der wirksamen Regeln bestätigen.",
    ]
    metadata = {
        "adapter": "sp5lib",
        "provenance": {},
        "unresolved_native": {},
        "context_schedule": [],
        "existing_plan_mode": existing_plan_mode,
        "reference_schedule": [],
        "reference_plan": reference_plan,
        "context_plan": "ist",
        "availability_plan": "ist",
        "special_shift_plan": "ist",
        "service_matrix_version": 1,
        "selected_team_id": str(native_team),
        "selected_group_ids": scope,
        "group_tree": group_tree(groups),
    }
    source_employees = db.get_employees(include_hidden=True)
    def person_id(value):
        # DBF numeric fields may be integral floats; never use Python's bool/int
        # equality or hash containers before validating native join keys.
        if not (type(value) is int or (
            type(value) is float and math.isfinite(value) and value.is_integer()
        )):
            raise ValueError("Personenquelle ungültig: invalid_person_identity.")
        return int(value)

    members = {person_id(eid) for gid in scope for eid in db.get_group_members(gid)}
    # Validate the join before scope filtering/deduplication can conceal people
    # or silently select different employment dates and nominal-hour inputs.
    employee_index = {}
    for employee in source_employees:
        if not isinstance(employee, dict):
            raise ValueError("Personenquelle ungültig: invalid_person_identity.")
        eid = person_id(employee.get("ID"))
        employee = {**employee, "ID": eid}
        if eid in employee_index and employee_index[eid] != employee:
            raise ValueError("Personenquelle widersprüchlich: conflicting_employee.")
        employee_index[eid] = employee
    if members - employee_index.keys():
        raise ValueError("Personenquelle unvollständig: orphan_membership.")
    source_employees = [e for eid, e in employee_index.items() if eid in members]
    holidays = calc.holiday_calendar(db.get_holidays())
    actual_bookings = {e["ID"]: [] for e in source_employees}
    nominal_bookings = _nominal_bookings(
        db, source_employees, period_start, period_end, actual_bookings=actual_bookings,
    )
    native_shifts = {s["ID"]: s for s in db.get_shifts(include_hidden=True)}
    metadata["services"] = [
        {"function_id": f"sp5:service:{sid}", "name": service.get("NAME", "")}
        for sid, service in native_shifts.items()
    ]
    native_workplaces = {w["ID"]: w for w in db.get_workplaces(include_hidden=True)}
    metadata["workplaces"] = [
        {"id": f"sp5:workplace:{wid}", "name": workplace.get("NAME", "")}
        for wid, workplace in native_workplaces.items()
    ]
    def checked_staffing_rows(rows, source, key):
        # Validate before Python equality/scope filtering and tuple-key grouping.
        # None/zero retain their existing explicit unresolved/sentinel semantics.
        for row in rows:
            invalid = [field for field in ("group_id", "shift_id", "workplace_id")
                       if row.get(field) is not None and not (
                           type(row[field]) is int
                           or (type(row[field]) is float and math.isfinite(row[field])
                               and row[field].is_integer())
                       )]
            if invalid:
                unresolved.append(
                    f"{source}: Ungültige Kennung ({', '.join(f.upper() for f in invalid)}); "
                    "ganze numerische Kennungen erforderlich."
                )
                metadata["unresolved_native"].setdefault(key, []).append(row)
                continue
            yield {**row, **{field: int(row[field])
                            for field in ("group_id", "shift_id", "workplace_id")
                            if row.get(field) is not None}}

    requirements = db.get_staffing_requirements()
    requirements = {**requirements, "shift_requirements": list(checked_staffing_rows(
        requirements.get("shift_requirements", []), "SHDEM", "regular_requirements"
    ))}
    if any(r.get("workplace_id") == 0 for r in requirements.get("shift_requirements", [])):
        metadata["workplaces"].append({"id": "sp5:workplace:0", "name": "Ohne feste Arbeitsplatzbindung"})
    specials = _unique_rows(
        row for gid in scope for row in db.get_special_staffing(group_id=gid)
    )
    daily = []
    for row in requirements.get("daily_requirements", []):
        # DADEM remains raw and uninterpreted. A malformed team identifier
        # must not silently remove an unresolved planning prerequisite.
        group = row.get("GROUPID", row.get("group_id"))
        if group is not None and not (
            type(group) is int
            or (type(group) is float and math.isfinite(group) and group.is_integer())
        ):
            unresolved.append(
                "DADEM: Ungültige Kennung (GROUPID); ganze numerische Kennungen erforderlich."
            )
            daily.append(row)
        elif group in (*scope, 0, None):
            daily.append(row)
    if daily:
        unresolved.append(
            "DADEM: Verhältnis zum Schichtbedarf und Zeitfenster noch zu klären."
        )
        metadata["unresolved_native"]["daily_requirements"] = daily
    special_cells = {}
    for row in checked_staffing_rows(specials, "SPDEM", "special_requirements"):
        if any(row.get(k) is None for k in ("group_id", "shift_id", "workplace_id", "min", "max")):
            unresolved.append("SPDEM: Unvollständige Bedarfsangabe.")
            metadata["unresolved_native"].setdefault("special_requirements", []).append(row)
            continue
        day = calc.to_date(row.get("date"))
        if day is None:
            unresolved.append("SPDEM: Ungültiges Datum.")
            continue
        if not period_start <= day <= period_end:
            continue
        key = (row.get("group_id"), day, row.get("shift_id"))
        special_cells.setdefault(key, []).append({**row, "_date": day.isoformat(), "_source": "SPDEM"})
    for key, values in special_cells.items():
        if len(values) > 1:
            unresolved.append("SPDEM: Mehrdeutiger tagesbezogener Bedarf; lokal auflösen.")
            metadata["unresolved_native"].setdefault("special_requirements", []).extend({k: v for k, v in r.items() if not k.startswith("_")} for r in values)
    employees = []
    parents = {int(g["id"]): int(g["parent_id"]) for g in metadata["group_tree"]}
    metadata["direct_group_memberships"] = {}
    for e in source_employees:
        eid = f"sp5:employee:{e['ID']}"
        direct_groups = set(db.get_employee_groups(e["ID"]))
        effective_groups = set(direct_groups)
        for group in direct_groups:
            parent = parents.get(group, 0)
            while parent:
                if parent in scope:
                    effective_groups.add(parent)
                parent = parents.get(parent, 0)
        metadata["direct_group_memberships"][eid] = sorted(direct_groups)
        if effective_groups != direct_groups:
            message = "Übergeordnete ausgewählte Teams umfassen die geladenen Unterteammitglieder; Einsatzbereich bestätigen."
            if message not in unresolved:
                unresolved.append(message)
        ctx = calc.EmployeeContext.from_record(e)
        target = calc.get_nominal_hours(
            ctx, period_start, period_end, holidays=holidays,
            bookings=nominal_bookings[e["ID"]] if nominal_bookings is not None else (),
        )
        if _minutes(target) < 0:
            unresolved.append(
                f"Negatives Quell-Soll für {eid}: Der nichtnegative Zielstundenvertrag kann diesen Wert nicht abbilden; lokal klären."
            )
        employees.append(
            Employee(
                id=eid,
                name=" ".join(
                    str(e.get(k) or "").strip() for k in ("FIRSTNAME", "NAME")
                ).strip(),
                team_ids=[f"sp5:group:{g}" for g in sorted(effective_groups)],
                employment_start=calc.to_date(e.get("EMPSTART")) or date.min,
                employment_end=calc.to_date(e.get("EMPEND")) or date.max,
                profile_ids=["sp5:unconfirmed"],
                target_minutes=max(0, _minutes(target)),
            )
        )
        metadata["provenance"][eid] = {
            "table": "EMPL",
            "id": e["ID"],
            "target": "sp5lib.calculations.get_nominal_hours; " + (
                "TYPE-1 bookings included" if nominal_bookings is not None else "bookings not included"
            ),
            "nominal_hours": {
                "calcbase": ctx.calcbase,
                "hours_day": ctx.hrs_day,
                "hours_week": ctx.hrs_week,
                "hours_month": ctx.hrs_month,
                "hours_total": ctx.hrs_total,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "target_minutes": employees[-1].target_minutes,
                "bookings_included": nominal_bookings is not None,
            },
        }
        if nominal_bookings is not None:
            # Evidence for explicit setup only: TYPE 0 includes signed manual
            # corrections and carry-in, not a confirmed replanning credit.
            metadata["provenance"][eid]["actual_bookings"] = {
                "table": "BOOK", "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(), "applied": False,
                "classification": "unresolved", "rows": actual_bookings[e["ID"]],
            }
            metadata["provenance"][eid]["nominal_hours"].update({
                "source_target_minutes": _minutes(target),
                "nominal_booking_count": len(nominal_bookings[e["ID"]]),
                "nominal_booking_minutes": _minutes(calc.booking_sum(
                    nominal_bookings[e["ID"]], 1, period_start, period_end
                )),
            })
    unresolved.append(
        ("Sollbuchungen nicht verfügbar; " if nominal_bookings is None else "")
        + "Zeitgutschriften und Anfangssalden für den gewählten Zeitraum ergänzen."
    )
    employee_map = {e.id: e for e in employees}
    shifts, positions, demands, restrictions, assignments = {}, {}, [], [], []
    boundary_work = {}
    rows = _unique_rows(list(requirements.get("shift_requirements", [])) + [values[0] for values in special_cells.values() if len(values) == 1])
    for row in rows:
        gid = row.get("group_id")
        if gid not in (*scope, 0, None):
            continue
        # SHDEM uses 0=Monday .. 7=holiday. Do not silently lose hard
        # requirements through a failed day comparison. Dated SPDEM rows
        # have their own validated date and do not carry a weekday.
        if "_date" not in row and (
            type(row.get("weekday")) is not int or not 0 <= row["weekday"] <= 7
        ):
            unresolved.append(f"SHDEM {row.get('id')}: Ungültiger Wochentag (erwartet 0–7).")
            metadata["unresolved_native"].setdefault("regular_requirements", []).append(row)
            continue
        if (
            gid in (0, None)
            or row.get("workplace_id") is None
            or row.get("max") is None
            or row.get("min") is None
        ):
            unresolved.append(
                f"SHDEM {row.get('id')}: Sonder-/Nullwerte benötigen Klärung."
            )
            metadata["unresolved_native"].setdefault("regular_requirements", []).append(
                row
            )
            continue
        invalid_counts = [
            field.upper() for field in ("min", "max")
            if not (
                type(row[field]) is int
                or (type(row[field]) is float and math.isfinite(row[field])
                    and row[field].is_integer())
            ) or (field == "min" and isinstance(row[field], (int, float))
                  and row[field] < 0)
        ]
        if invalid_counts:
            unresolved.append(
                f"{row.get('_source', 'SHDEM')} {row.get('id')}: "
                f"Ungültige Besetzungszahl ({', '.join(invalid_counts)}); "
                "ganze Zahlen erforderlich, MIN muss mindestens 0 sein."
            )
            metadata["unresolved_native"].setdefault("regular_requirements", []).append(row)
            continue
        # DBF numeric fields and JSON numbers may represent integers as floats.
        # Normalize only proven integral numbers, never booleans or numeric text.
        row = {**row, "min": int(row["min"]), "max": int(row["max"])}
        sid, wid = row.get("shift_id"), row["workplace_id"]
        if sid not in native_shifts or (wid != 0 and wid not in native_workplaces):
            unresolved.append(f"SHDEM {row.get('id')}: Stammdatenreferenz fehlt.")
            continue
        if row["max"] < -1 or (row["max"] != -1 and row["max"] < row["min"]):
            unresolved.append(f"SHDEM {row.get('id')}: Ungültiges MAX oder MAX kleiner als MIN.")
            metadata["unresolved_native"].setdefault("regular_requirements", []).append(row)
            continue
        if row["max"] in (-1, 0) or wid == 0:
            interpretation = "Importinterpretation bestätigen: MAX=-1 ohne Obergrenze, MAX=0 keine Besetzung, Arbeitsplatz=0 ohne feste Arbeitsplatzbindung."
            if interpretation not in unresolved:
                unresolved.append(interpretation)
        metadata["provenance"][f"sp5:requirement:{row['id']}"] = {
            "native_min": row["min"], "native_max": row["max"],
            "native_workplace_id": wid,
            "interpretation": "explicit-boundaries-v1",
        }
        position_id = f"sp5:position:{sid}:{wid}"
        positions[position_id] = Position(
            id=position_id,
            name=native_shifts[sid].get("NAME", ""),
            function_id=f"sp5:service:{sid}",
            workplace_id=f"sp5:workplace:{wid}",
            qualifications_required=False,
        )
        d = period_start
        while d <= period_end:
            idx = calc.day_index(d, holidays)
            cell = (gid, d, sid)
            applies = (d.isoformat() == row["_date"]) if "_date" in row else (idx == row.get("weekday") and cell not in special_cells)
            if applies:
                shift_id = f"sp5:shift:{sid}:{d.isoformat()}" + (
                    f":group:{gid}" if len(scope) > 1 else ""
                )
                native = native_shifts[sid]
                try:
                    windows = _parse_native_windows(
                        str(native.get(f"STARTEND{idx}") or "")
                    )
                    if not windows:
                        raise ValueError("Zeitfenster fehlt")
                    segments = [
                        Interval(
                            start=_local(d, a, zone),
                            end=_local(d, b + (1440 if b <= a else 0), zone),
                        )
                        for a, b in windows
                    ]
                    shifts[shift_id] = Shift(
                        id=shift_id,
                        name=native.get("NAME", ""),
                        kind="unconfirmed",
                        team_id=f"sp5:group:{gid}",
                        segments=segments,
                        paid_minutes=_minutes(native.get(f"DURATION{idx}")),
                        holiday=d in holidays,
                        source="sp5:SHIFT",
                    )
                    demands.append(
                        Demand(
                            id=f"sp5:demand:{row.get('_source', 'SHDEM')}:{gid}:{sid}:{wid}:{row['id']}:{d}",
                            shift_id=shift_id,
                            position_id=position_id,
                            minimum=row["min"],
                            maximum=None if row["max"] == -1 else row["max"],
                            source=f"sp5:{row.get('_source', 'SHDEM')}",
                        )
                    )
                except ValueError as exc:
                    unresolved.append(f"SHIFT {sid} {d}: {exc}")
            d += timedelta(days=1)
    native_restrictions = db.get_restrictions()
    restriction_counts = dict.fromkeys(
        ("outside_employee_scope", "outside_shift_scope", "outside_day_scope",
         "invalid_weekday", "invalid_grade", "mapped_rows", "mapped_instances"), 0
    )
    metadata["restriction_mapping_counts"] = restriction_counts
    # Refinement of outside_shift_scope, not additional exclusive row outcomes.
    # Keep the aggregate stable for existing consumers. Only selected employees
    # enter this scope; a dangling foreign row must not block unrelated planning.
    shift_scope_counts = dict.fromkeys(("unknown_source_shift", "known_shift_not_generated"), 0)
    metadata["restriction_shift_scope_counts"] = shift_scope_counts
    for row in native_restrictions:
        eid = f"sp5:employee:{row['employee_id']}"
        if eid not in employee_map:
            restriction_counts["outside_employee_scope"] += 1
            continue
        candidates = []
        for sid, shift in shifts.items():
            d = shift.segments[0].start.date()
            if (sid == f"sp5:shift:{row['shift_id']}:{d}"
                    or sid.startswith(f"sp5:shift:{row['shift_id']}:{d}:group:")):
                candidates.append((sid, d))
        if not candidates:
            restriction_counts["outside_shift_scope"] += 1
            reason = (
                "known_shift_not_generated" if row["shift_id"] in native_shifts
                else "unknown_source_shift"
            )
            shift_scope_counts[reason] += 1
            continue
        weekday = row.get("weekday")
        if type(weekday) is not int or weekday not in range(8):
            restriction_counts["invalid_weekday"] += 1
            unresolved.append(f"RESTR {row.get('id')}: ungültiger Wochentag (erwartet 0–7).")
            continue
        matching = [sid for sid, d in candidates if weekday == calc.day_index(d, holidays)]
        if not matching:
            restriction_counts["outside_day_scope"] += 1
            continue
        grade = row.get("restrict")
        if type(grade) is not int or grade not in (0, 1, 2):
            restriction_counts["invalid_grade"] += 1
            unresolved.append(f"RESTR {row.get('id')}: unbekannte Stufe.")
            continue
        restriction_counts["mapped_rows"] += 1
        restriction_counts["mapped_instances"] += len(matching)
        restrictions.extend(
            Restriction(employee_id=eid, shift_id=sid, level=grade, approved=False)
            for sid in matching
        )
    month = context_start.replace(day=1)
    seen_schedule = set()
    while month <= context_end:
        schedule = _reference_schedule(
            db, scope, month.year, month.month, period_start, period_end, reference_plan
        )
        # Library replacement is person-day-wide, independent of TYPE/workplace.
        # Normalize Ist work and references, never replace Soll target duties.
        replaced_days = {
            (row.get("employee_id"), calc.to_date(row.get("date")))
            for row in schedule
            if row.get("kind") == "special_shift"
            and row.get("shift_id") not in (None, 0, "", "0")
        }
        replaced_rows = {}
        for row in schedule:
            day = calc.to_date(row.get("date"))
            key = (row.get("employee_id"), day)
            if (row.get("kind") == "shift" and key in replaced_days
                    and day is not None
                    and (reference_plan == "ist" or not period_start <= day <= period_end)):
                replaced_rows.setdefault(key, []).append({
                    field: row.get(field)
                    for field in ("employee_id", "date", "shift_id", "workplace_id", "group_id")
                })
        for row in schedule:
            d = calc.to_date(row.get("date"))
            eid = f"sp5:employee:{row.get('employee_id')}"
            if (
                d is None
                or not context_start <= d <= context_end
                or eid not in employee_map
            ):
                continue
            # Preserve only scheduling structure, not arbitrary notes or display metadata.
            safe = {
                k: row.get(k)
                for k in (
                    "employee_id",
                    "group_id",
                    "date",
                    "kind",
                    "leave_type_id",
                    "shift_id",
                    "workplace_id",
                    "interval",
                    "start_time",
                    "end_time",
                    "startend",
                    "duration",
                    "spshi_type",
                )
            }
            schedule_key = json.dumps(safe, sort_keys=True, default=str)
            if schedule_key in seen_schedule:
                continue
            seen_schedule.add(schedule_key)
            metadata["context_schedule"].append(safe)
            kind = row.get("kind")
            if kind == "shift" and (row.get("employee_id"), d) in replaced_rows:
                # Preserve raw context above; unknown special times still block.
                continue
            if kind == "special_shift" and row.get("spshi_type", 0) == 0 and row.get("shift_id") in native_shifts:
                idx = calc.day_index(d, holidays)
                try:
                    actual = _parse_native_windows(row.get("startend"))
                    nominal = _parse_native_windows(native_shifts[row["shift_id"]].get(f"STARTEND{idx}"))
                    if actual and actual == nominal and row.get("duration") is not None and _minutes(row["duration"]) == _minutes(native_shifts[row["shift_id"]].get(f"DURATION{idx}")):
                        kind = "shift"
                except ValueError:
                    pass
            if kind == "absence":
                mode = row.get("interval", 0)
                bounds = {0: (0, 1440), 1: (0, 720), 2: (720, 1440)}.get(mode)
                if mode == 3:
                    try:
                        a, b = (int(str(row.get("start_time"))), int(str(row.get("end_time"))))
                        bounds = ((a, b + (1440 if b < a else 0))
                                  if 0 <= a < 1440 and 0 <= b <= 1440 and a != b else None)
                    except (ValueError, TypeError):
                        bounds = None
                if bounds is None:
                    unresolved.append(f"ABSEN {eid} {d}: ungültiges Intervall.")
                    continue
                try:
                    employee_map[eid].unavailable.append(
                        Interval(
                            start=_local(d, bounds[0], zone),
                            end=_local(d, bounds[1], zone),
                        )
                    )
                except ValueError as exc:
                    unresolved.append(f"ABSEN {eid} {d}: {exc}")
            elif kind == "shift" and row.get("shift_id") in native_shifts:
                if period_start <= d <= period_end:
                    # A baseline must reference actual demand, never create it.
                    member_teams = set(employee_map[eid].team_ids) & {
                        f"sp5:group:{g}" for g in scope
                    }
                    explicit_group = row.get("group_id")
                    if explicit_group not in (None, 0, "", "0"):
                        member_teams &= {f"sp5:group:{explicit_group}"}
                    wid = row.get("workplace_id")
                    date_service_candidates = [
                        demand for demand in demands
                        if demand.source in ("sp5:SHDEM", "sp5:SPDEM")
                        and shifts[demand.shift_id].segments[0].start.date() == d
                        and positions[demand.position_id].function_id == f"sp5:service:{row['shift_id']}"
                    ]
                    team_candidates = [demand for demand in date_service_candidates
                                       if shifts[demand.shift_id].team_id in member_teams]
                    workplace_candidates = [demand for demand in team_candidates
                                            if wid in (None, "") or positions[demand.position_id].workplace_id
                                            in {f"sp5:workplace:{wid}", "sp5:workplace:0"}]
                    candidates = [demand for demand in workplace_candidates if demand.maximum != 0]
                    reference = {**safe, "candidate_demand_ids": [v.id for v in candidates]}
                    if row.get("kind") == "special_shift":
                        reference["replaced_normal_rows"] = replaced_rows.get((row.get("employee_id"), d), [])
                    metadata["reference_schedule"].append(reference)
                    if len(candidates) == 1:
                        reference["demand_id"] = candidates[0].id
                        assignment = Assignment(
                            employee_id=eid, demand_id=candidates[0].id,
                            fixed=existing_plan_mode == "fixed",
                        )
                        if assignment not in assignments:
                            assignments.append(assignment)
                    else:
                        reference["resolution"] = "unmatched" if not candidates else "ambiguous"
                        reference["resolution_reason"] = (
                            "missing_demand" if not date_service_candidates else
                            "team_mismatch" if not team_candidates else
                            "workplace_mismatch" if not workplace_candidates else
                            "zero_capacity" if not candidates else "ambiguous"
                        )
                        reference["planning_blocker"] = existing_plan_mode == "fixed"
                        metadata["unresolved_native"].setdefault("reference_schedule", []).append(reference)
                        # Comparison-only duties are not mandatory source
                        # assignments. Preserve their mapping diagnostics, but
                        # only an explicitly requested fixation blocks planning.
                        # This branch covers regular duties inside the period;
                        # fixed boundary context and special duties stay strict.
                        if reference["planning_blocker"]:
                            unresolved.append(
                                f"Bestehender Dienst {eid} {d}: keine eindeutige Zuordnung zum tatsächlichen Besetzungsbedarf."
                            )
                    continue
                native = native_shifts[row["shift_id"]]
                idx = calc.day_index(d, holidays)
                try:
                    windows = _parse_native_windows(
                        str(native.get(f"STARTEND{idx}") or "")
                    )
                    if not windows:
                        raise ValueError("Zeitfenster fehlt")
                    segments = [
                        Interval(
                            start=_local(d, a, zone),
                            end=_local(d, b + (1440 if b <= a else 0), zone),
                        )
                        for a, b in windows
                    ]
                    workplace = row.get("workplace_id")
                    workplace = "unresolved" if workplace in (None, "") else str(workplace)
                    sid = (f"sp5:context:{row['employee_id']}:{d}:{row['shift_id']}"
                           f":workplace:{workplace}:group:{row.get('group_id') or 'unresolved'}")
                    if sid in boundary_work:
                        # Nominal duty and an identical special replacement
                        # describe the same personal work, not two duties.
                        continue
                    metadata["provenance"][sid] = {
                        "function_id": f"sp5:service:{row['shift_id']}",
                        "name": native.get("NAME", ""),
                        "schedule_group_id": row.get("group_id"),
                        "workplace_id": row.get("workplace_id"),
                        "time_source": f"sp5:SHIFT.STARTEND{idx}",
                        "replaced_normal_rows": replaced_rows.get((row.get("employee_id"), d), []),
                    }
                    boundary_work[sid] = BoundaryWork(
                        id=sid,
                        employee_id=eid,
                        segments=segments,
                        kind="unknown",
                        source="sp5:existing",
                    )
                except ValueError as exc:
                    unresolved.append(f"Bestehender Dienst {eid} {d}: {exc}")
            else:
                unresolved.append(
                    f"Sonderdienst {eid} {d}: individuelle Zeit-/Stundenabweichung oder fehlende eindeutige Detailzuordnung; gezielt ergänzen."
                )
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    profile = RuleProfile(
        id="sp5:unconfirmed",
        valid_from=context_start,
        valid_until=context_end,
        min_rest_minutes=660,
        weekly_rest_minutes=2160,
        weekly_rest_frame="calendar_week",
        weekly_rest_add_daily=False,
        confirmed=False,
        source="unresolved",
    )
    payload = dict(
        id="sp5:import",
        revision="",
        created_at=datetime.now(dt_timezone.utc),
        timezone=timezone,
        period_start=period_start,
        period_end=period_end,
        context_start=context_start,
        context_end=context_end,
        context_complete=False,
        rule_version="unconfirmed",
        source="sp5",
        employees=employees,
        positions=list(positions.values()),
        shifts=list(shifts.values()),
        demands=demands,
        profiles=[profile],
        objectives=Objectives(workday_transitions=100),
        restrictions=restrictions,
        assignments=assignments,
        boundary_work=list(boundary_work.values()),
        unresolved=list(dict.fromkeys(unresolved)),
    )
    from .absence_evidence import absence_evidence

    for native_id, evidence in absence_evidence(
        db, source_employees, metadata["context_schedule"],
        period_start, period_end, holidays,
    ).items():
        metadata["provenance"][f"sp5:employee:{native_id}"]["absence_accounting"] = evidence
    if "metadata" in Snapshot.model_fields:
        payload["metadata"] = metadata
    else:
        raise RuntimeError(
            "Snapshot metadata contract is required for lossless source diagnostics"
        )
    payload["revision"] = sha256(
        json.dumps(
            {k: v for k, v in payload.items() if k != "created_at"},
            default=str,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    payload["id"] = "sp5:import:" + payload["revision"][:16]
    return Snapshot(**payload)


def _source_database(directory):
    """Resolve a selected root or one direct database child, without writing it."""
    from pathlib import Path
    import os
    from sp5lib.database import SP5Database

    root = Path(directory).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Bitte ein SP5-Stammverzeichnis auswählen.")
    allowed = os.environ.get("SP5_SOURCE_ROOT")
    if allowed and not root.is_relative_to(Path(allowed).resolve(strict=True)):
        raise ValueError(
            "Verzeichnis liegt außerhalb des freigegebenen Quellenbereichs."
        )
    required = {"5EMPL.DBF", "5GROUP.DBF", "5GRASG.DBF", "5SHIFT.DBF", "5WOPL.DBF"}
    candidates = []
    for folder in [
        root,
        *sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink()),
    ]:
        files = {
            p.name.upper(): p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.upper() == ".DBF"
        }
        if required.issubset(files):
            if any(
                p.is_symlink() or not p.resolve().is_relative_to(root)
                for p in files.values()
            ):
                raise ValueError("Verknüpfte Quelldateien werden nicht eingelesen.")
            if len(files) != sum(
                1
                for p in folder.iterdir()
                if p.is_file() and p.suffix.upper() == ".DBF"
            ):
                raise ValueError("Mehrdeutige Tabellennamen im Quellverzeichnis.")
            candidates.append((folder, files))
    if len(candidates) != 1:
        raise ValueError(
            "Genau ein SP5-Datenverzeichnis mit 5EMPL, 5GROUP, 5GRASG, 5SHIFT und 5WOPL wird benötigt; bitte das konkrete Unterverzeichnis auswählen."
        )
    folder, files = candidates[0]

    class SelectedDatabase(SP5Database):
        def _table(self, name):
            return str(files.get(f"5{name}.DBF", folder / f"5{name}.DBF"))

    return SelectedDatabase(str(folder)), files


def _source_fingerprint(files):
    """Fingerprint original DBF bytes locally; no data is exported to services."""
    result = {}
    for name, path in sorted(files.items()):
        digest = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result[name] = digest.hexdigest()
    return result


def inspect_directory(directory):
    db, files = _source_database(directory)
    return {
        "directory": db.db_path,
        "groups": group_tree(db.get_groups()),
        "files": sorted(files),
        "source_read_only": True,
    }


def historical_matrix(db, snapshot, history_start, history_end, history_plan="ist"):
    """Past assignments are evidence for editable proposals, never permissions."""
    from collections import defaultdict
    from sp5lib import calculations as calc

    if history_end < history_start or (history_end - history_start).days > 1096:
        raise ValueError(
            "Historienzeitraum muss gültig und auf höchstens drei Jahre begrenzt sein."
        )
    if history_plan not in ("ist", "soll", "both"):
        raise ValueError("Historische Plansicht muss ist, soll oder both sein.")
    employees = {e.id: e for e in snapshot.employees}
    shifts = {str(s["ID"]): s for s in db.get_shifts(include_hidden=True)}
    position_ids = {p.id for p in snapshot.positions}
    by_employee = {
        eid: {
            "employee_id": eid,
            "observed_assignment_count": 0,
            "observed_shifts": {},
            "approvals": defaultdict(int),
            "approval_days": defaultdict(set),
            "dates": [],
        }
        for eid in employees
    }
    primary_team = snapshot.metadata.get("selected_team_id")
    team = int(primary_team) if primary_team else None
    month = history_start.replace(day=1)
    seen = set()
    while month <= history_end:
        for row in _scope_schedule(
            db,
            snapshot.metadata.get("selected_group_ids", [team]),
            month.year,
            month.month,
            plan=history_plan,
        ):
            day = calc.to_date(row.get("date"))
            eid = f"sp5:employee:{row.get('employee_id')}"
            if (
                eid not in employees
                or day is None
                or not history_start <= day <= history_end
                or row.get("kind") not in ("shift", "special_shift")
            ):
                continue
            if row.get("kind") == "special_shift" and row.get("spshi_type", 0) != 0:
                continue
            sid = str(row.get("shift_id") or "")
            wid = row.get("workplace_id")
            if sid not in shifts:
                continue
            key = (
                eid,
                str(day),
                sid,
                wid,
                row.get("kind"),
                row.get("start_time"),
                row.get("end_time"),
            )
            if key in seen:
                continue
            seen.add(key)
            item = by_employee[eid]
            item["observed_assignment_count"] += 1
            item["dates"].append(str(day))
            observation = item["observed_shifts"].setdefault(
                sid,
                {
                    "shift_id": sid,
                    "name": shifts[sid].get("NAME", ""),
                    "count": 0,
                    "first_date": str(day),
                    "last_date": str(day),
                },
            )
            observation["count"] += 1
            observation["first_date"] = min(observation["first_date"], str(day))
            observation["last_date"] = max(observation["last_date"], str(day))
            item["approvals"][sid] += 1
            item["approval_days"][sid].add(str(day))
            # History is service evidence, not physical permission or demand.
            workplace = str(wid) if wid not in (None, 0, "0", "") else "unresolved"
            pid = f"sp5:position:{sid}:{workplace}"
            if pid not in position_ids:
                snapshot.positions.append(Position(
                    id=pid,
                    name=shifts[sid].get("NAME", ""),
                    function_id=f"sp5:service:{sid}",
                    workplace_id=f"sp5:workplace:{workplace}",
                    qualifications_required=False,
                ))
                position_ids.add(pid)
                snapshot.metadata.setdefault("historical_only_position_ids", []).append(pid)
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    output = []
    for item in by_employee.values():
        output.append(
            {
                "employee_id": item["employee_id"],
                "observed_assignment_count": item["observed_assignment_count"],
                "observed_shifts": list(item["observed_shifts"].values()),
                "suggested_approvals": [
                    {
                        "function_id": f"sp5:service:{sid}",
                        "workplace_id": "*",
                        "evidence_count": count,
                        "evidence_days": len(item["approval_days"][sid]),
                        "confirmed": False,
                        "source": "historical",
                    }
                    for sid, count in sorted(item["approvals"].items())
                ],
                "first_date": min(item["dates"]) if item["dates"] else None,
                "last_date": max(item["dates"]) if item["dates"] else None,
            }
        )
    return output


def import_directory(
    directory,
    period_start,
    period_end,
    team_id=None,
    timezone="Europe/Vienna",
    history_start=None,
    history_end=None,
    history_plan="ist",
    team_ids=None,
    existing_plan_mode="reference",
    reference_plan="ist",
):
    """Explicit local directory import with change detection and matrix suggestions."""
    if not 0 <= (period_end - period_start).days < MAX_PLANNING_DAYS:
        raise ValueError(f"Planungszeitraum muss 1 bis {MAX_PLANNING_DAYS} Kalendertage umfassen.")
    db, files = _source_database(directory)
    before = _source_fingerprint(files)
    snapshot = import_snapshot(
        db, period_start, period_end, team_id, timezone, team_ids=team_ids,
        existing_plan_mode=existing_plan_mode, reference_plan=reference_plan,
    )
    history_end = history_end or period_start - timedelta(days=1)
    history_start = history_start or history_end - timedelta(days=89)
    if history_end >= period_start:
        raise ValueError(
            "Die historische Basis muss vor dem neuen Planungszeitraum enden."
        )
    snapshot.metadata["history_matrix"] = historical_matrix(
        db, snapshot, history_start, history_end, history_plan
    )
    snapshot.metadata["history_plan"] = history_plan
    snapshot.metadata["history_period"] = {
        "start": str(history_start),
        "end": str(history_end),
    }
    snapshot.metadata["history_notice"] = (
        "Bisherige Einsätze sind Vorschläge, keine Qualifikations- oder Einsatzfreigaben. Jede Freigabe muss ausdrücklich bestätigt und befristet werden."
    )
    snapshot.metadata["source_fingerprint"] = before
    snapshot.metadata["source_read_only"] = True
    _, after_files = _source_database(directory)
    if files != after_files or before != _source_fingerprint(after_files):
        raise ValueError(
            "Quelldateien haben sich während des Imports verändert. Import erneut ausführen."
        )
    # A before/after comparison detects changes but does not claim a native transaction.
    snapshot.metadata["source_consistency"] = (
        "before-after-file-fingerprint; no cross-file transaction"
    )
    expected = {
        "5BOOK.DBF",
        "5SHDEM.DBF",
        "5SPDEM.DBF",
        "5DADEM.DBF",
        "5RESTR.DBF",
        "5MASHI.DBF",
        "5SPSHI.DBF",
        "5ABSEN.DBF",
        "5HOLID.DBF",
        "5CYCLE.DBF",
        "5CYENT.DBF",
        "5CYASS.DBF",
        "5CYEXC.DBF",
    }
    missing = sorted(expected - set(files))
    if missing:
        snapshot.unresolved.append(
            "Quelltabellen fehlen; Vollständigkeit prüfen: " + ", ".join(missing)
        )
    from uuid import uuid4

    snapshot.metadata["source_import_id"] = snapshot.id
    snapshot.id = "sp5:import:" + str(uuid4())
    snapshot.revision = "1"
    return snapshot
