"""Read-only translation of the optional sp5lib facade into the public contract."""

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

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


def _minutes(hours):
    return int(
        (Decimal(str(hours or 0)) * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


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
    db, period_start: date, period_end: date, team_id: str, timezone: str
) -> Snapshot:
    """Read from an explicitly supplied library database; never writes or opens a default source.

    Imports are intentionally unconfirmed until source ambiguities and additional
    rule/approval data have been resolved. Native names are runtime display data.
    """
    from sp5lib import calculations as calc

    if period_end < period_start:
        raise ValueError("Ungültiger Zeitraum")
    zone = ZoneInfo(timezone)
    native_team = int(team_id.removeprefix("sp5:group:"))
    team = f"sp5:group:{native_team}"
    context_start, context_end = (
        period_start - timedelta(days=31),
        period_end + timedelta(days=31),
    )
    unresolved = [
        "Regelprofile, Dienstarten, Freigaben und Qualifikationsanforderungen ausdrücklich bestätigen.",
        "Konsistenz des Imports gegen gleichzeitige Quelländerungen lokal bestätigen.",
        "Randkontext und Ausgleichszeiträume nach Auswahl der wirksamen Regeln bestätigen.",
    ]
    metadata = {
        "adapter": "sp5lib",
        "provenance": {},
        "unresolved_native": {},
        "context_schedule": [],
    }
    source_employees = db.get_employees(include_hidden=True)
    members = set(db.get_group_members(native_team))
    source_employees = [e for e in source_employees if e["ID"] in members]
    holidays = calc.holiday_calendar(db.get_holidays())
    native_shifts = {s["ID"]: s for s in db.get_shifts(include_hidden=True)}
    native_workplaces = {w["ID"]: w for w in db.get_workplaces(include_hidden=True)}
    requirements = db.get_staffing_requirements()
    specials = db.get_special_staffing(group_id=native_team)
    daily = requirements.get("daily_requirements", [])
    if daily:
        unresolved.append(
            "DADEM: Verhältnis zum Schichtbedarf und Zeitfenster noch zu klären."
        )
        metadata["unresolved_native"]["daily_requirements"] = daily
    if specials:
        unresolved.append(
            "SPDEM: Vorrang gegenüber regelmäßigem Bedarf noch zu klären."
        )
        metadata["unresolved_native"]["special_requirements"] = specials
    employees = []
    for e in source_employees:
        eid = f"sp5:employee:{e['ID']}"
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
                team_ids=[f"sp5:group:{g}" for g in db.get_employee_groups(e["ID"])],
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
        }
    unresolved.append(
        "Sollbuchungen, Zeitgutschriften und Anfangssalden für den gewählten Zeitraum ergänzen."
    )
    employee_map = {e.id: e for e in employees}
    shifts, positions, demands, restrictions, assignments = {}, {}, [], [], []
    rows = requirements.get("shift_requirements", [])
    for row in rows:
        gid = row.get("group_id")
        if gid not in (native_team, 0, None):
            continue
        if (
            gid in (0, None)
            or not row.get("workplace_id")
            or row.get("max") in (0, None)
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
        if sid not in native_shifts or wid not in native_workplaces:
            unresolved.append(f"SHDEM {row.get('id')}: Stammdatenreferenz fehlt.")
            continue
        if row["max"] < row["min"]:
            unresolved.append(f"SHDEM {row.get('id')}: MAX kleiner als MIN.")
            continue
        position_id = f"sp5:position:{wid}"
        positions[position_id] = Position(
            id=position_id,
            name=native_workplaces[wid].get("NAME", ""),
            function_id=f"sp5:function:{wid}",
            workplace_id=f"sp5:workplace:{wid}",
            qualifications_required=True,
        )
        d = period_start
        while d <= period_end:
            idx = calc.day_index(d, holidays)
            if idx == row.get("weekday"):
                shift_id = f"sp5:shift:{sid}:{d.isoformat()}"
                native = native_shifts[sid]
                try:
                    windows = calc.parse_startend(
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
                        team_id=team,
                        segments=segments,
                        paid_minutes=_minutes(native.get(f"DURATION{idx}")),
                        holiday=d in holidays,
                        source="sp5:SHIFT",
                    )
                    demands.append(
                        Demand(
                            id=f"sp5:demand:{row['id']}:{d}",
                            shift_id=shift_id,
                            position_id=position_id,
                            minimum=row["min"],
                            maximum=row["max"],
                            source="sp5:SHDEM",
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
            if sid == f"sp5:shift:{row['shift_id']}:{d}" and row.get(
                "weekday"
            ) == calc.day_index(d, holidays):
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
    while month <= context_end:
        for row in db.get_schedule(month.year, month.month, group_id=native_team):
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
                    "date",
                    "kind",
                    "shift_id",
                    "workplace_id",
                    "interval",
                    "start_time",
                    "end_time",
                )
            }
            metadata["context_schedule"].append(safe)
            kind = row.get("kind")
            if kind == "absence":
                mode = row.get("interval", 0)
                bounds = {0: (0, 1440), 1: (0, 720), 2: (720, 1440)}.get(mode)
                if mode == 3:
                    a, b = (
                        int(row.get("start_time") or 0),
                        int(row.get("end_time") or 0),
                    )
                    bounds = (a, b + (1440 if b < a else 0)) if a != b else None
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
                native = native_shifts[row["shift_id"]]
                idx = calc.day_index(d, holidays)
                try:
                    windows = calc.parse_startend(
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
                    sid = f"sp5:context:{row['employee_id']}:{d}:{row['shift_id']}"
                    pid = f"sp5:context-position:{row.get('workplace_id') or 'unresolved'}"
                    positions[pid] = Position(
                        id=pid,
                        name="Übernommener Dienst",
                        function_id=pid,
                        workplace_id=f"sp5:workplace:{row.get('workplace_id') or 'unresolved'}",
                        qualifications_required=True,
                    )
                    shifts[sid] = Shift(
                        id=sid,
                        name=native.get("NAME", ""),
                        kind="unconfirmed",
                        team_id=team,
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
                    f"Sonderdienst {eid} {d}: originale Zeitabweichung fehlt im öffentlichen Lesemodell; gezielt ergänzen."
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
        "groups": [
            {"id": str(g["ID"]), "name": g.get("NAME", "")} for g in db.get_groups()
        ],
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
    by_employee = {
        eid: {
            "employee_id": eid,
            "observed_assignment_count": 0,
            "observed_shifts": {},
            "approvals": defaultdict(int),
            "dates": [],
        }
        for eid in employees
    }
    primary_team = snapshot.metadata.get("selected_team_id")
    team = int(primary_team) if primary_team else None
    month = history_start.replace(day=1)
    seen = set()
    while month <= history_end:
        for row in db.get_schedule(
            month.year, month.month, group_id=team, plan=history_plan
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
            if wid not in (None, 0, "0", ""):
                item["approvals"][str(wid)] += 1
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
                        "function_id": f"sp5:function:{wid}",
                        "workplace_id": f"sp5:workplace:{wid}",
                        "evidence_count": count,
                        "confirmed": False,
                        "source": "historical",
                    }
                    for wid, count in sorted(item["approvals"].items())
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
    team_id,
    timezone,
    history_start=None,
    history_end=None,
    history_plan="ist",
):
    """Explicit local directory import with change detection and matrix suggestions."""
    if (period_end - period_start).days > 366:
        raise ValueError("Planungszeitraum auf höchstens 366 Tage begrenzen.")
    db, files = _source_database(directory)
    before = _source_fingerprint(files)
    native_team = int(str(team_id).removeprefix("sp5:group:"))
    if native_team not in {g["ID"] for g in db.get_groups()}:
        raise ValueError("Die ausgewählte Gruppe existiert nicht in der Quelle.")
    snapshot = import_snapshot(db, period_start, period_end, str(native_team), timezone)
    history_end = history_end or period_start - timedelta(days=1)
    history_start = history_start or history_end - timedelta(days=89)
    if history_end >= period_start:
        raise ValueError(
            "Die historische Basis muss vor dem neuen Planungszeitraum enden."
        )
    snapshot.metadata["selected_team_id"] = str(native_team)
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
    if before != _source_fingerprint(files):
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
