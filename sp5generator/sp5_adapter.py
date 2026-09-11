"""Read-only translation of the optional sp5lib facade into the public contract."""

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from zoneinfo import ZoneInfo

from .hierarchy import group_tree, resolve_group_selection
from .domain import MAX_PLANNING_DAYS

from .models import (
    Employee,
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
    members = {eid for gid in scope for eid in db.get_group_members(gid)}
    source_employees = list(
        {e["ID"]: e for e in source_employees if e["ID"] in members}.values()
    )
    holidays = calc.holiday_calendar(db.get_holidays())
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
    requirements = db.get_staffing_requirements()
    if any(r.get("workplace_id") == 0 for r in requirements.get("shift_requirements", [])):
        metadata["workplaces"].append({"id": "sp5:workplace:0", "name": "Ohne feste Arbeitsplatzbindung"})
    specials = _unique_rows(
        row for gid in scope for row in db.get_special_staffing(group_id=gid)
    )
    daily = [
        r
        for r in requirements.get("daily_requirements", [])
        if r.get("group_id") in (*scope, 0, None)
    ]
    if daily:
        unresolved.append(
            "DADEM: Verhältnis zum Schichtbedarf und Zeitfenster noch zu klären."
        )
        metadata["unresolved_native"]["daily_requirements"] = daily
    special_cells = {}
    for row in specials:
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
            ctx, period_start, period_end, holidays=holidays
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
            "target": "sp5lib.calculations.get_nominal_hours; bookings not included",
            "nominal_hours": {
                "calcbase": ctx.calcbase,
                "hours_day": ctx.hrs_day,
                "hours_week": ctx.hrs_week,
                "hours_month": ctx.hrs_month,
                "hours_total": ctx.hrs_total,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "target_minutes": employees[-1].target_minutes,
                "bookings_included": False,
            },
        }
    unresolved.append(
        "Sollbuchungen, Zeitgutschriften und Anfangssalden für den gewählten Zeitraum ergänzen."
    )
    employee_map = {e.id: e for e in employees}
    shifts, positions, demands, restrictions, assignments = {}, {}, [], [], []
    rows = _unique_rows(list(requirements.get("shift_requirements", [])) + [values[0] for values in special_cells.values() if len(values) == 1])
    for row in rows:
        gid = row.get("group_id")
        if gid not in (*scope, 0, None):
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
    for row in native_restrictions:
        eid = f"sp5:employee:{row['employee_id']}"
        if eid not in employee_map:
            continue
        for sid, shift in shifts.items():
            d = shift.segments[0].start.date()
            if (
                sid == f"sp5:shift:{row['shift_id']}:{d}"
                or sid.startswith(f"sp5:shift:{row['shift_id']}:{d}:group:")
            ) and row.get("weekday") == calc.day_index(d, holidays):
                grade = row.get("restrict")
                if grade not in (0, 1, 2):
                    unresolved.append(f"RESTR {row.get('id')}: unbekannte Stufe.")
                else:
                    restrictions.append(
                        Restriction(
                            employee_id=eid, shift_id=sid, level=grade, approved=False
                        )
                    )
    month = context_start.replace(day=1)
    seen_schedule = set()
    while month <= context_end:
        for row in _reference_schedule(db, scope, month.year, month.month, period_start, period_end, reference_plan):
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
                    candidates = [
                        demand for demand in demands
                        if demand.source in ("sp5:SHDEM", "sp5:SPDEM")
                        and shifts[demand.shift_id].segments[0].start.date() == d
                        and shifts[demand.shift_id].team_id in member_teams
                        and positions[demand.position_id].function_id == f"sp5:service:{row['shift_id']}"
                        and (wid in (None, "") or positions[demand.position_id].workplace_id
                             in {f"sp5:workplace:{wid}", "sp5:workplace:0"})
                        and demand.maximum != 0
                    ]
                    reference = {**safe, "candidate_demand_ids": [v.id for v in candidates]}
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
                        metadata["unresolved_native"].setdefault("reference_schedule", []).append(reference)
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
                    if sid in shifts:
                        # The source may expose a nominal entry and an identical
                        # special replacement; this is one duty, not two.
                        continue
                    pid = f"sp5:context-position:{row['shift_id']}:{workplace}"
                    positions[pid] = Position(
                        id=pid,
                        name=native.get("NAME", ""),
                        function_id=f"sp5:service:{row['shift_id']}",
                        workplace_id=f"sp5:workplace:{workplace}",
                        qualifications_required=False,
                    )
                    member_teams = [
                        g
                        for g in employee_map[eid].team_ids
                        if g in {f"sp5:group:{v}" for v in scope}
                    ]
                    explicit_group = row.get("group_id")
                    if explicit_group not in (None, 0, "", "0"):
                        member_teams = [g for g in member_teams if g == f"sp5:group:{explicit_group}"]
                    if len(member_teams) != 1:
                        unresolved.append(
                            f"Bestehender Dienst {eid} {d}: konkrete Gruppe bei mehrfacher oder fehlender Mitgliedschaft bestätigen."
                        )
                    metadata["provenance"][sid] = {
                        "team_source": "schedule_group" if explicit_group not in (None, 0, "", "0") else "employee_membership",
                        "team_confirmed": len(member_teams) == 1,
                    }
                    shifts[sid] = Shift(
                        id=sid,
                        name=native.get("NAME", ""),
                        kind="unconfirmed",
                        team_id=next(iter(member_teams), f"sp5:group:{native_team}"),
                        segments=segments,
                        paid_minutes=_minutes(native.get(f"DURATION{idx}")),
                        holiday=d in holidays,
                        source="sp5:existing",
                    )
                    demand_id = sid + ":fixed"
                    demands.append(
                        Demand(
                            id=demand_id,
                            shift_id=sid,
                            position_id=pid,
                            minimum=1,
                            maximum=1,
                            source="sp5:existing",
                        )
                    )
                    assignments.append(
                        Assignment(employee_id=eid, demand_id=demand_id, fixed=True)
                    )
                    unresolved.append(
                        f"Bestehender Dienst {eid} {d}: Zuordnung zum Besetzungsbedarf und Freigaben bestätigen."
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
        min_rest_minutes=0,
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
        restrictions=restrictions,
        assignments=assignments,
        unresolved=list(dict.fromkeys(unresolved)),
    )
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
