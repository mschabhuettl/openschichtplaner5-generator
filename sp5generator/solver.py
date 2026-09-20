"""Local CP-SAT optimization with independently checked incumbent separation."""

import os
from collections import Counter, defaultdict
from datetime import timedelta
from math import isfinite
from random import Random
from time import monotonic
from types import SimpleNamespace
from ortools.sat.python import cp_model
from .models import Assignment, Diagnostic, Result, Validation
from .domain import (
    MAX_ASSIGNMENTS,
    snapshot_hash,
    input_diagnostics,
    eligibility,
    pair_conflict,
    supervised,
    night_block_conflict,
    maximum_matching,
    staffing_gaps,
)
from .timeutils import (
    bounds,
    local_day,
    day_minutes,
    day_of,
    dates,
    segments,
    midnight,
    overlap,
)
from .validator import PreparedValidator, validate


# OR-Tools 9.15 kann bei paralleler Qualitätssuche an einem gültigen
# Demomodell abstürzen. Die Bibliotheksvorgabe bleibt deshalb einspurig: so
# bleiben Aufrufe aus Tests und Kommandozeile reproduzierbar. Der
# Auftragsprozess rechnet parallel und wiederholt bei einem Absturz einspurig.
SEARCH_WORKERS = 1

# Erfüllungsgrad in Millionsteln des persönlichen Solls: so lässt sich der
# Abstand zwischen Personen ganzzahlig und ohne Division im Modell messen.
HOURS_SCALE = 1_000_000
# Oberhalb von 150 Prozent des eigenen Solls zieht eine Person den
# gemeinsamen Maßstab nicht weiter nach oben.
HOURS_CAP = HOURS_SCALE * 3 // 2


def parallel_workers():
    """Suchprozesse für eine Auftragsrechnung.

    Mehrere Prozesse liefern an echten Daten deutlich bessere Pläne, sind aber
    nicht reproduzierbar: dieselbe Eingabe kann verschiedene gleich gültige
    Pläne ergeben.
    """
    return max(1, min(8, os.cpu_count() or 1))

# Zusammenhängende Freizeit entsteht aus wenigen, längeren Dienstblöcken;
# beide teilen sich denselben Zeitraum. Vier bis fünf Tage sind daher
# kostenfrei. Einzelne Arbeitstage sind teuer, ab sieben Tagen steigen die
# Kosten wieder: die harte Wochenruhe lässt rechnerisch bis zu zwölf Tage am
# Stück zu, was im beobachteten Betrieb nirgends vorkommt.
# Schlüssel 9 steht für neun Tage oder mehr.
LAENGENKOSTEN = {1: 300, 2: 80, 3: 15, 4: 0, 5: 0, 6: 15, 7: 60, 8: 150, 9: 400}


def _free_time_metrics(period_start, period_end, worked_days_by_person):
    lengths = []
    people = free_weekends = 0
    period_days = None
    for worked_days in worked_days_by_person:
        if not any(period_start <= day <= period_end for day in worked_days):
            continue
        people += 1
        if period_days is None:
            period_days = set(dates(period_start, period_end))
        free_days = period_days - worked_days
        previous = None
        for day in sorted(free_days):
            if previous is not None and day == previous + timedelta(days=1):
                lengths[-1] += 1
            else:
                lengths.append(1)
            previous = day
        free_weekends += sum(
            day.weekday() == 5 and day + timedelta(days=1) in free_days
            for day in free_days
        )
    return {
        "blocks": len(lengths),
        "single_days": lengths.count(1),
        "three_or_more": sum(length >= 3 for length in lengths),
        "mean_length": round(sum(lengths) / len(lengths), 2) if lengths else 0.0,
        "longest": max(lengths, default=0),
        "free_weekends": free_weekends,
        "people": people,
    }


def _plan_raster(snapshot, xs, demands, shift_day, shifts):
    """Zellen für die Live-Ansicht: je Entscheidungsvariable Zeile, Spalte, Art.

    Übertragen werden nur Indizes und Dienstarten. Namen bleiben dort, wo sie
    ohnehin schon liegen: in der geöffneten Planung.
    """
    spalten = {
        tag: i for i, tag in enumerate(
            dates(snapshot.period_start, snapshot.period_end + timedelta(days=1))
        )
    }
    zeilen = {e.id: i for i, e in enumerate(snapshot.employees)}
    zellen = []
    for (employee_id, demand_id), x in xs.items():
        tag = shift_day[demands[demand_id].shift_id]
        if tag not in spalten or employee_id not in zeilen:
            continue
        art = ord("N") if shifts[demands[demand_id].shift_id].kind == "night" else ord("T")
        zellen.append((x, zeilen[employee_id], spalten[tag], art))
    return len(zeilen), len(spalten), zellen


class _Zwischenstand(cp_model.CpSolverSolutionCallback):
    """Meldet jede verbesserte Lösung, während die Suche noch läuft.

    Die Meldung ist reine Anzeige: sie ändert weder Modell noch Auswahl und
    darf die Suche unter keinen Umständen abbrechen.
    """

    def __init__(self, phase, search_started, run_started, melden, raster=None,
                 abstand=0.5):
        super().__init__()
        self._phase = phase
        self._search_started = search_started
        self._run_started = run_started
        self._melden = melden
        self._raster = raster
        self._abstand = abstand
        self._zuletzt = 0.0
        self._anzahl = 0

    def _belegung(self):
        """Die aktuelle Einteilung als eine Zeichenkette je Person."""
        personen, tage, zellen = self._raster
        gitter = [bytearray(b"." * tage) for _ in range(personen)]
        for x, zeile, spalte, art in zellen:
            if self.boolean_value(x):
                gitter[zeile][spalte] = art
        return [zeile.decode("ascii") for zeile in gitter]

    def on_solution_callback(self):
        self._anzahl += 1
        jetzt = monotonic()
        if jetzt - self._zuletzt < self._abstand:
            return
        self._zuletzt = jetzt
        try:
            self._melden({
                "phase": self._phase,
                "kind": "incumbent",
                "solutions": self._anzahl,
                "started_seconds": self._search_started - self._run_started,
                "search_seconds": jetzt - self._search_started,
                "elapsed_seconds": jetzt - self._run_started,
                "objective": self.objective_value,
                "bound": self.best_objective_bound,
                "grid": self._belegung() if self._raster else None,
            })
        except Exception:
            pass


def _hours_metrics(snapshot, paid_by_person, assignable):
    """Wie gleichmäßig ist das Vertragssoll erfüllt?

    Gezählt wird nur, wer ein Soll hat und überhaupt einsetzbar ist: Personen
    ohne jede mögliche Stelle würden das Bild sonst nach unten ziehen, ohne
    dass die Planung daran etwas ändern könnte.
    """
    quoten = sorted(
        100 * paid_by_person.get(e.id, 0) / e.target_minutes
        for e in snapshot.employees
        if e.target_minutes and e.id in assignable
    )
    if not quoten:
        return {"people": 0}
    faecher = {"none": 0, "under_50": 0, "from_50": 0, "on_target": 0, "over_110": 0}
    for q in quoten:
        schluessel = ("none" if q == 0 else "under_50" if q < 50
                      else "from_50" if q < 90 else "on_target" if q <= 110 else "over_110")
        faecher[schluessel] += 1
    return {
        "people": len(quoten),
        "median": round(quoten[len(quoten) // 2], 1),
        "lowest": round(quoten[0], 1),
        "highest": round(quoten[-1], 1),
        **faecher,
    }


def _forced_split_weekends(snapshot):
    """Teilungen, die schon der Bedarf erzwingt, samt Hinweisen.

    Wer an einem Wochenendtag höchstens einen Dienst übernimmt, deckt die
    Mindestbesetzung des stärker besetzten Tages nur, wenn mindestens die
    Differenz zur Höchstbesetzung des anderen Tages an genau einem der beiden
    Tage arbeitet. Solche Teilungen bleiben, gleich wie die Freigaben liegen.
    """
    if not snapshot.objectives.split_weekends:
        return [], 0
    shifts = {s.id: s for s in snapshot.shifts}
    minimum, maximum, unlimited = defaultdict(int), defaultdict(int), set()
    for demand in snapshot.demands:
        # Wie die Kopplung selbst: ein Dienst belegt jeden Tag, den er berührt.
        for day in day_minutes(shifts[demand.shift_id], snapshot.timezone):
            if day is None or day.weekday() < 5:
                continue
            if not snapshot.period_start <= day <= snapshot.period_end:
                continue
            minimum[day] += demand.minimum
            if demand.maximum is None:
                unlimited.add(day)
            else:
                maximum[day] += demand.maximum
    diagnostics, total = [], 0
    for monday in sorted({day - timedelta(days=day.weekday()) for day in minimum}):
        saturday, sunday = monday + timedelta(days=5), monday + timedelta(days=6)
        if saturday < snapshot.period_start or sunday > snapshot.period_end:
            continue
        forced = 0
        for day, other in ((saturday, sunday), (sunday, saturday)):
            if other not in unlimited:
                forced = max(forced, minimum[day] - maximum[other])
        if forced <= 0:
            continue
        total += forced
        wer = "Eine Person muss" if forced == 1 else f"{forced} Personen müssen"
        diagnostics.append(Diagnostic(
            code="split_weekend_demand",
            date=str(saturday),
            message=f"Wochenende vom {saturday}: Der Bedarf verlangt am Samstag "
            f"{minimum[saturday]} und am Sonntag {minimum[sunday]} Besetzungen. "
            f"{wer} daher genau einen der beiden Tage arbeiten. Diese Teilungen "
            "entstehen aus dem Bedarf; keine Freigabe und keine Rechnung lösen sie "
            "auf. Sie verschwinden erst, wenn beide Tage gleich stark besetzt "
            "werden. Die Zahl gilt, solange niemand an einem Tag zwei Dienste "
            "übernimmt.",
        ))
    return diagnostics, total


def _split_weekend_approval_diagnostics(snapshot, assignments):
    """Geteilte Wochenenden des gewählten Plans, und welche eine Freigabe löste."""
    if not snapshot.objectives.split_weekends:
        return [], 0
    shifts = {s.id: s for s in snapshot.shifts}
    demands = {d.id: d for d in snapshot.demands}
    starts = defaultdict(set)
    for assignment in assignments:
        shift = shifts[demands[assignment.demand_id].shift_id]
        starts[assignment.employee_id].update(day_minutes(shift, snapshot.timezone))
    for work in snapshot.boundary_work:
        starts[work.employee_id].update(day_minutes(work, snapshot.timezone))

    # Visit days actually worked, not every employee/calendar-day combination.
    # Like the daily variables, a day counts once, no matter how many duties
    # touch it.
    split_weekends = []
    for employee_id, days in starts.items():
        for day in sorted(days):
            if day.weekday() < 5:
                continue
            saturday = day - timedelta(days=day.weekday() - 5)
            sunday = saturday + timedelta(days=1)
            if saturday < snapshot.period_start or sunday > snapshot.period_end:
                continue
            missing_day = sunday if day == saturday else saturday
            if missing_day not in days:
                split_weekends.append((employee_id, saturday, missing_day))
    if not split_weekends:
        return [], 0

    missing_days = {day for _, _, day in split_weekends}
    demands_by_day = defaultdict(list)
    for demand in snapshot.demands:
        for day in day_minutes(shifts[demand.shift_id], snapshot.timezone):
            if day in missing_days:
                demands_by_day[day].append(demand)
    employees = {e.id: e for e in snapshot.employees}
    diagnostics = []
    for employee_id, saturday, missing_day in split_weekends:
        employee = employees[employee_id]
        candidates = [
            (demand, set(eligibility(snapshot, employee, demand)))
            for demand in demands_by_day[missing_day]
        ]
        demand, reasons = min(candidates, key=lambda item: len(item[1]), default=(None, None))
        # An eligible alternative (empty set) wins; another exclusion means
        # that approval alone would not make this demand individually eligible.
        if reasons != {"approval"}:
            continue
        shift = shifts[demand.shift_id]
        diagnostics.append(Diagnostic(
            code="split_weekend_approval",
            employee_id=employee_id,
            demand_id=demand.id,
            date=str(missing_day),
            message=f"{employee.name}: Wochenende vom {saturday} ist geteilt. "
            f"Für {shift.name} am {missing_day} fehlt die persönliche "
            f"Dienstfreigabe. Mit ihr ließe sich das Wochenende "
            "zusammenlegen; ohne sie bleibt die Teilung bestehen. Eine Freigabe entsteht "
            "dadurch nicht und wird auch nicht angenommen.",
        ))
    return diagnostics, len(split_weekends)


def solve(snapshot, time_limit=30, partial=False, _repair=True, progress=None,
          workers=None):
    if not isfinite(time_limit):
        raise ValueError('Zeitlimit muss eine endliche Zahl in Sekunden sein.')
    workers = SEARCH_WORKERS if workers is None else max(1, int(workers))
    started = monotonic()
    deadline = started + time_limit
    # Die Reparaturphase braucht ein eigenes Budget; sonst schöpfen die
    # Suchphasen an echten Daten die gesamte Frist aus.
    repair_enabled = _repair and partial and time_limit >= 120
    phase_limit = time_limit * 0.4 if repair_enabled else time_limit
    phase_deadline = started + phase_limit
    timings = {}
    employee_candidates = None
    approval_gaps = None
    plan_raster = None
    demands = {d.id: d for d in snapshot.demands}
    dates_by_shift = {}
    parameters = {
        "time_limit": time_limit,
        "partial": partial,
        "workers": workers,
        "random_seed": 0,
        "objective_semantics": "lexicographic vacancies, then configured weighted costs",
        "phase_seconds": timings,
        # Aggregate, identifier-free evidence from this run. Native status is
        # not an independent-validation or global optimality claim.
        "search_trace": [],
    }

    def note(trace):
        """Suchverlauf festhalten und, falls gewünscht, sofort melden."""
        parameters["search_trace"].append(trace)
        if progress is None:
            return
        # Eine fehlschlagende Fortschrittsmeldung darf die Planung nie beenden.
        try:
            progress(dict(trace))
        except Exception:
            pass


    def worked_days(employee_id, plan):
        days = {
            day
            for a in plan if a.employee_id == employee_id
            for day in dates_by_shift[demands[a.demand_id].shift_id]
        }
        for work in snapshot.boundary_work:
            if work.employee_id == employee_id:
                key = ("boundary", work.id)
                # Early results may precede the model's boundary-work setup.
                days.update(dates_by_shift[key] if key in dates_by_shift
                            else day_minutes(work, snapshot.timezone))
        return days

    def result(status, assignments=None, validation=None, **kwargs):
        assignments = assignments or []
        kwargs.setdefault("metrics", {})["split_weekends_blocked_by_approval"] = 0
        kwargs.setdefault("metrics", {})["split_weekends_forced_by_demand"] = 0
        kwargs.setdefault("metrics", {})["split_weekends_in_plan"] = 0
        bezahlt = defaultdict(int)
        for a in assignments:
            if snapshot.period_start <= shift_day[demands[a.demand_id].shift_id] <= snapshot.period_end:
                bezahlt[a.employee_id] += shifts[demands[a.demand_id].shift_id].paid_minutes
        kwargs.setdefault("metrics", {})["hours_attainment"] = _hours_metrics(
            snapshot, bezahlt,
            {eid for eid, stat in (employee_candidates or {}).items()
             if stat["eligible_demands"]},
        )
        kwargs.setdefault("metrics", {})["free_time"] = _free_time_metrics(
            snapshot.period_start,
            snapshot.period_end,
            # Invalid input has no usable calendar on which to report a plan.
            (worked_days(e.id, assignments) for e in snapshot.employees)
            if status != "MODEL_INVALID" else (),
        )
        counts = defaultdict(int)
        for a in assignments:
            counts[a.demand_id] += 1
        if approval_gaps is not None:
            kwargs.setdefault("metrics", {})["missing_approvals"] = [
                {"employee_id": eid, "function_id": fid, "blocked_demands": n}
                for (eid, fid), n in sorted(
                    approval_gaps.items(), key=lambda item: (-item[1], item[0])
                )
            ]
        if employee_candidates is not None:
            selected = Counter(
                a.employee_id for a in assignments
                if snapshot.period_start <= shift_day[demands[a.demand_id].shift_id]
                <= snapshot.period_end
            )
            usable = status in ("FEASIBLE", "OPTIMAL") and validation is not None and validation.valid
            details = {}
            for eid, candidates in employee_candidates.items():
                if not usable:
                    reason = "no_valid_plan"
                elif selected[eid]:
                    reason = "assigned"
                elif not candidates["positive_capacity_demands"]:
                    reason = "no_positive_capacity_demand"
                elif not candidates["eligible_demands"]:
                    reason = "individually_ineligible"
                else:
                    reason = "not_selected_with_candidates"
                details[eid] = {
                    **candidates,
                    "exclusions": dict(candidates["exclusions"]),
                    "assigned_demands": selected[eid],
                    "reason": reason,
                }
            kwargs.setdefault("metrics", {})["planning_diagnostics"] = {
                "scope": "demands starting inside the planning period",
                "semantics": "individual eligibility only; not a joint feasibility or causal optimality proof",
                "objective_weights": snapshot.objectives.model_dump(),
                "employees": details,
            }
        return Result(
            snapshot_id=snapshot.id,
            snapshot_hash=snapshot_hash(snapshot),
            solver_status=status,
            assignments=assignments,
            vacancies={
                demand_id: gap
                for demand_id, gap in staffing_gaps(snapshot, counts).items()
                if gap
            },
            validation=validation
            or Validation(valid=False, complete=False, diagnostics=[]),
            runtime_seconds=monotonic() - started,
            parameters=parameters,
            **kwargs,
        )

    def timed_out():
        return result(
            "UNKNOWN",
            validation=Validation(valid=False, complete=False, diagnostics=[
                Diagnostic(code="time_limit", message="Zeitlimit ohne unabhängig geprüfte Lösung.")
            ]),
        )

    def finish(best):
        if repair_enabled:
            best = repair(best)
        # Report only after plan selection, including repair and fallbacks.
        # These hints never enter independent validation or search decisions.
        hints, split_total = _split_weekend_approval_diagnostics(
            snapshot, best.assignments
        )
        best.validation.diagnostics.extend(hints)
        best.metrics["split_weekends_blocked_by_approval"] = len(hints)
        # Die gewichtete Wertung sieht nur Teilungen mit Arbeitsmöglichkeit an
        # beiden Tagen. Berichtet wird die gezählte Gesamtzahl des Plans.
        best.metrics["split_weekends_in_plan"] = split_total
        forced, forced_total = _forced_split_weekends(snapshot)
        best.validation.diagnostics.extend(forced)
        best.metrics["split_weekends_forced_by_demand"] = forced_total
        # Result construction copies the parameters dictionary. Synchronize
        # later search status and timings when returning an earlier incumbent.
        best.parameters = dict(parameters)
        best.runtime_seconds = monotonic() - started
        return best

    def repair(best):
        rng = Random(0)
        employee_ids = sorted(employees)
        weekends = sorted({
            day - timedelta(days=day.weekday() - 5)
            for day in dates(snapshot.period_start, snapshot.period_end)
            if day.weekday() >= 5
        })
        round_number = 0
        while True:
            round_started = monotonic()
            remaining = deadline - round_started
            round_budget = max(15.0, remaining / 10)
            if remaining <= round_budget:
                break
            # Periods without a Saturday or Sunday use employee neighborhoods.
            neighborhood = "weekend" if round_number % 2 == 0 and weekends else "employees"
            if neighborhood == "weekend":
                saturday = rng.choice(weekends)
                first, last = saturday - timedelta(days=1), saturday + timedelta(days=2)
                released = {
                    (a.employee_id, a.demand_id) for a in best.assignments
                    if first <= shift_day[demands[a.demand_id].shift_id] <= last
                }
            else:
                chosen = set(rng.sample(employee_ids, min(6, len(employee_ids))))
                released = {
                    (a.employee_id, a.demand_id) for a in best.assignments
                    if a.employee_id in chosen
                }
            # User fixations, including boundary duties, remain hard constraints.
            released -= fixed
            candidate = snapshot.model_copy(deep=True)
            candidate.assignments = [
                a.model_copy(deep=True, update={
                    "fixed": (a.employee_id, a.demand_id) not in released,
                }) for a in best.assignments
            ]
            if deadline - monotonic() <= round_budget:
                break
            repaired = solve(candidate, round_budget, partial=True, _repair=False,
                             workers=workers)
            trace = {
                "phase": "repair",
                "neighborhood": neighborhood,
                "released_assignments": len(released),
                "started_seconds": round_started - started,
                "budget_seconds": round_budget,
                "solver_status": repaired.solver_status,
                "accepted": False,
            }
            if repaired.assignments and repaired.validation.valid:
                # Temporary neighborhood fixations must not escape into the
                # result. Recheck against the original input and its fixations.
                assignments = [
                    a.model_copy(deep=True, update={
                        "fixed": (a.employee_id, a.demand_id) in fixed,
                    }) for a in repaired.assignments
                ]
                checked = validate(snapshot, assignments)
                if checked.valid:
                    metrics = repaired.metrics
                    # Recursive solves use the incumbent as their draft. Keep
                    # comparisons and reported change costs on the original draft.
                    if snapshot.objectives.changes:
                        selected = {(a.employee_id, a.demand_id) for a in assignments}
                        changes = len(prior ^ selected)
                        metrics["objective_contributions"]["changes"] = changes
                        metrics["weighted_objective_contributions"]["changes"] = (
                            changes * snapshot.objectives.changes
                        )
                    score = (
                        metrics["vacancy_count"],
                        metrics["objective_contributions"].get("split_weekends", 0)
                        if snapshot.objectives.split_weekends else 0,
                        sum(metrics["weighted_objective_contributions"].values()),
                    )
                    previous_score = (
                        best.metrics["vacancy_count"],
                        best.metrics["objective_contributions"].get("split_weekends", 0)
                        if snapshot.objectives.split_weekends else 0,
                        sum(best.metrics["weighted_objective_contributions"].values()),
                    )
                    trace.update(
                        vacancy_count=score[0], split_weekend_count=score[1],
                        weighted_quality_cost=score[2],
                    )
                    if score < previous_score:
                        metrics["objective_phase"] = "repair"
                        metrics["quality_scope"] = "repair neighborhood; global quality unproven"
                        checked.diagnostics.extend(diagnostics)
                        best = result(
                            "FEASIBLE", assignments, checked, metrics=metrics,
                            objective_value=float(score[2]),
                        )
                        parameters["coverage_proven"] = coverage_proven or score[0] == 0
                        if couple_enabled:
                            parameters["split_weekend_count"] = score[1]
                            # A neighborhood optimum is no global proof. Keep
                            # the previous proof only at unchanged coverage and
                            # coupling, or use the universal lower bound zero.
                            parameters["split_weekends_proven"] = score[1] == 0 or (
                                parameters.get("split_weekends_proven", False)
                                and score[:2] == previous_score[:2]
                            )
                        trace["accepted"] = True
            trace["round_seconds"] = monotonic() - round_started
            note(trace)
            round_number += 1
        return best

    personal_period_paid = defaultdict(int)
    for work in snapshot.boundary_work:
        if work.in_period:
            personal_period_paid[work.employee_id] += work.paid_minutes
    issues = input_diagnostics(snapshot)
    timings["input_validation"] = monotonic() - started
    if issues:
        return result(
            "MODEL_INVALID",
            validation=Validation(valid=False, complete=False, diagnostics=issues),
        )
    if time_limit <= 0:
        return result(
            "UNKNOWN",
            validation=Validation(
                valid=False,
                complete=False,
                diagnostics=[
                    Diagnostic(
                        code="time_limit", message="Zeitlimit ohne gefundene Lösung."
                    )
                ],
            ),
        )
    model = cp_model.CpModel()
    employees = {e.id: e for e in snapshot.employees}
    shifts = {s.id: s for s in snapshot.shifts}
    positions = {p.id: p for p in snapshot.positions}
    fixed = {(a.employee_id, a.demand_id) for a in snapshot.assignments if a.fixed}
    prior = {(a.employee_id, a.demand_id) for a in snapshot.assignments}
    xs = {}
    by_employee = defaultdict(list)
    by_demand = defaultdict(list)
    dates_by_shift = {s.id: day_minutes(s, snapshot.timezone) for s in snapshot.shifts}
    shift_day = {
        s.id: local_day(bounds(s)[0], snapshot.timezone) for s in snapshot.shifts
    }

    def duty_blocks(employee_id, plan):
        blocks = []
        for day in sorted(worked_days(employee_id, plan)):
            if blocks and day == blocks[-1][1] + timedelta(days=1):
                blocks[-1] = (blocks[-1][0], day)
            else:
                blocks.append((day, day))
        # Randtage verlängern berührende Blöcke; reine Kontextblöcke zählen nicht.
        lengths = [
            (end - start).days + 1 for start, end in blocks
            if start <= snapshot.period_end and end >= snapshot.period_start
        ]
        return {
            "blocks": len(lengths),
            "single_days": lengths.count(1),
            "average_length": round(sum(lengths) / len(lengths), 2) if lengths else 0.0,
            "longest": max(lengths, default=0),
        }

    diagnostics = []
    exclusions = defaultdict(Counter)
    approval_only = defaultdict(list)
    approval_gap_counts = Counter()
    candidate_stats = {
        e.id: {"positive_capacity_demands": 0, "eligible_demands": 0,
               "eligible_required_demands": 0, "exclusions": Counter()}
        for e in snapshot.employees
    }
    reachable_minutes = {e.id: personal_period_paid[e.id] for e in snapshot.employees}
    exclusion_labels = {
        "excluded": "von der Planung ausgenommen",
        "employment": "Beschäftigungszeitraum",
        "team": "Teamzugehörigkeit",
        "kind": "Diensttypfreigabe",
        "weekend": "Wochenendfreigabe",
        "holiday": "Feiertagsfreigabe",
        "approval": "persönliche Dienstfreigabe fehlt oder ist nicht gültig",
        "profile": "bestätigtes Regelprofil für Dienstüberhang fehlt",
        "qualification": "zusätzlicher Qualifikationsnachweis",
        "restriction": "Dienstsperre",
        "absence": "Abwesenheit",
        "personal_work": "persönliche Arbeit ohne Zeitangabe an diesem Tag",
        "availability": "Verfügbarkeitsfenster",
        "context": "außerhalb des Planungszeitraums ohne Fixierung",
    }
    for e in snapshot.employees:
        for demand_number, d in enumerate(snapshot.demands):
            if demand_number % 64 == 0 and monotonic() >= deadline:
                return timed_out()
            in_period = (
                snapshot.period_start <= shift_day[d.shift_id] <= snapshot.period_end
            )
            if not in_period and (e.id, d.id) not in fixed:
                exclusions[d.id]["context"] += 1
                continue
            reasons = eligibility(snapshot, e, d)
            if in_period:
                stats = candidate_stats[e.id]
                if d.maximum == 0:
                    stats["exclusions"]["zero_capacity"] += 1
                else:
                    stats["positive_capacity_demands"] += 1
                    stats["exclusions"].update(reasons)
                    if not reasons:
                        stats["eligible_demands"] += 1
                        stats["eligible_required_demands"] += int(d.minimum > 0)
                        reachable_minutes[e.id] += shifts[d.shift_id].paid_minutes
            if in_period and d.minimum > 0 and reasons == ["approval"]:
                approval_only[d.id].append(e.id)
            if reasons:
                exclusions[d.id].update(reasons)
                if (e.id, d.id) in fixed:
                    return result(
                        "INFEASIBLE",
                        validation=Validation(
                            valid=False,
                            complete=False,
                            diagnostics=[
                                Diagnostic(
                                    code="fixed_conflict",
                                    message="Fixierung verletzt " + ", ".join(reasons),
                                    employee_id=e.id,
                                    demand_id=d.id,
                                )
                            ],
                        ),
                    )
                continue
            x = model.new_bool_var("assign:" + e.id + ":" + d.id)
            xs[e.id, d.id] = x
            by_employee[e.id].append((d, x))
            by_demand[d.id].append(x)
            if (e.id, d.id) in fixed:
                model.add(x == 1)
            elif (e.id, d.id) in prior:
                model.add_hint(x, 1)
    # Publish candidate facts only after the entire scan, never a timed-out
    # prefix. These are informational metrics, not relaxed validation rules.
    employee_candidates = candidate_stats
    for e in snapshot.employees:
        if e.target_minutes > 0 and e.target_minutes > reachable_minutes[e.id]:
            diagnostics.append(
                Diagnostic(
                    code="target_unreachable",
                    message="Das Periodensoll übersteigt die im gewählten Zuschnitt überhaupt "
                    "erreichbare Arbeitszeit; der Rückstand ist strukturell und nicht durch "
                    "Planung behebbar.",
                    employee_id=e.id,
                )
            )
    # The standalone contract and independent checker accept at most this
    # many assignments, including fixed context. Extra optional staffing must
    # not drive the optimizer outside that supported result envelope.
    model.add(sum(xs.values()) <= MAX_ASSIGNMENTS)
    vacancies = []
    # Alternativen decken denselben Posten ab: gefordert ist ihre Summe, nicht
    # jeder Bedarf für sich. Die Höchstbesetzung bleibt je Bedarf einzeln.
    alternativen = defaultdict(list)
    for d in snapshot.demands:
        alternativen[d.alternative_group].append(d)
    alternativen.pop(None, None)
    erledigt = set()
    for d in snapshot.demands:
        choices = by_demand[d.id]
        if d.maximum is not None:
            model.add(sum(choices) <= d.maximum)
        gruppe = alternativen.get(d.alternative_group)
        if gruppe is not None:
            if d.alternative_group in erledigt:
                continue
            erledigt.add(d.alternative_group)
            gemeinsam = [x for mitglied in gruppe for x in by_demand[mitglied.id]]
            bedarf = max(mitglied.minimum for mitglied in gruppe)
            if len(gemeinsam) < bedarf:
                diagnostics.append(Diagnostic(
                    code="candidate_shortage",
                    message=f"{bedarf} benötigte Stellen; nur {len(gemeinsam)} individuell "
                    "geeignete Personen über alle Alternativen dieses Postens.",
                    demand_id=d.id,
                    date=str(shift_day[d.shift_id]),
                ))
            if partial:
                v = model.new_int_var(0, bedarf, "vacancy:" + str(d.alternative_group))
                model.add_max_equality(v, [0, bedarf - sum(gemeinsam)])
                vacancies.append(v)
            else:
                model.add(sum(gemeinsam) >= bedarf)
            continue
        if len(choices) < d.minimum:
            # Eine Freigabe hilft nur dort, wo der Bedarf sonst unbesetzbar bleibt.
            for eid in approval_only.get(d.id, ()):
                approval_gap_counts[(eid, positions[d.position_id].function_id)] += 1
            explanation = "; ".join(
                f"{exclusion_labels[reason]}: {count}"
                for reason, count in sorted(exclusions[d.id].items())
            )
            diagnostics.append(
                Diagnostic(
                    code="candidate_shortage",
                    message=f"{d.minimum} benötigte Stellen; nur {len(choices)} individuell geeignete Personen."
                    + (f" Ausschlussgründe (Personen, Mehrfachzählung möglich): {explanation}."
                       if explanation else ""),
                    demand_id=d.id,
                    date=str(shift_day[d.shift_id]),
                )
            )
        if partial:
            v = model.new_int_var(0, d.minimum, "vacancy:" + d.id)
            # A time-limited FEASIBLE incumbent need not tighten inequality
            # slack. Keep the objective equal to the actual unfilled slots,
            # including when staffing exceeds the minimum.
            model.add_max_equality(v, [0, d.minimum - sum(choices)])
            vacancies.append(v)
        else:
            model.add(sum(choices) >= d.minimum)
    # Wie bei den Kandidatenzahlen: erst nach dem vollständigen Durchlauf
    # veröffentlichen, nie einen abgebrochenen Anfang.
    approval_gaps = approval_gap_counts
    for sid in shifts:
        if monotonic() >= deadline:
            return timed_out()
        slots = [
            d.id
            for d in snapshot.demands
            if d.shift_id == sid
            for _ in range(d.minimum)
        ]
        candidates = {
            did: [eid for eid in employees if (eid, did) in xs] for did in set(slots)
        }
        matched = len(maximum_matching({i: candidates[did] for i, did in enumerate(slots)}))
        if matched < len(slots):
            diagnostics.append(
                Diagnostic(
                    code="shared_candidate_shortage",
                    message=f"{len(slots)} gleichzeitig benötigte Stellen; der gemeinsame geeignete Kandidatenkreis kann höchstens {matched} davon besetzen. Dienst: "
                    + sid,
                    date=str(shift_day[sid]),
                )
            )
    costs = []
    components = defaultdict(list)
    weighted_components = defaultdict(list)

    def cost(name, expr, weight):
        if weight:
            components[name].append(expr)
            weighted_components[name].append(expr * weight)
            costs.append(expr * weight)

    # Personal context is fixed work, never an xs staffing decision. Tuple keys
    # keep its IDs disjoint from real shifts without reserved user ID prefixes.
    boundary_keys = set()
    for work in snapshot.boundary_work:
        key = ("boundary", work.id)
        boundary_keys.add(key)
        shifts[key] = work
        dates_by_shift[key] = day_minutes(work, snapshot.timezone)
        shift_day[key] = day_of(work, snapshot.timezone)
        by_employee[work.employee_id].append((SimpleNamespace(shift_id=key), 1))

    # One conflict edge per pair of duties and rule-profile set. Position
    # choices on a duty form a clique: at most one of them can be worked.
    # Expressing that clique directly avoids an employee x demand^2 scan and
    # four separate constraints for a common two-position pair of duties.
    conflict_graphs = {}
    shift_bounds = {s.id: bounds(s) for s in snapshot.shifts}
    ordered_shifts = sorted(snapshot.shifts, key=lambda s: shift_bounds[s.id][0])
    worked_vars = {}
    nights_vars = {}
    weekend_vars = {}
    # Ein gemeinsamer Erfüllungsgrad, den die Suche frei wählt: bestraft wird
    # der Abstand jeder Person zu ihm, nicht die Summe der Fehlstunden. Die
    # Summe ist bei feststehendem Bedarf konstant und lenkt deshalb nichts.
    fairness_level = (
        model.new_int_var(0, HOURS_SCALE, "hours_level")
        if snapshot.objectives.hours_fairness else None
    )
    # Dasselbe Prinzip auf die Dienstanzahl. In Plänen, deren Bedarf nur einen
    # Bruchteil der vereinbarten Arbeitszeit ausmacht, sagt die Sollerfüllung
    # fast nichts; verteilt werden muss dann die Zahl der Dienste.
    duty_level = (
        model.new_int_var(0, len(snapshot.demands), "duty_level")
        if snapshot.objectives.duty_fairness else None
    )
    for e in snapshot.employees:
        if monotonic() >= deadline:
            return timed_out()
        entries = by_employee[e.id]
        by_shift = defaultdict(list)
        for d, x in entries:
            by_shift[d.shift_id].append(x)
        # Context constrains new work and other immutable context. Normal-shift
        # edges remain shared by profile set below.
        context_entries = [(d, x) for d, x in entries if d.shift_id in boundary_keys]
        normal_entries = [(d, x) for d, x in entries if d.shift_id not in boundary_keys]
        for i, (left_d, left_x) in enumerate(context_entries):
            if monotonic() >= deadline:
                return timed_out()
            # Context constrains new work only. Two immutable duties are facts
            # the plan cannot undo; asserting a rule between them would read as
            # 1 + 1 <= 1 and make every plan unsolvable without saying where.
            # The validator reports such source contradictions as context.
            for right_d, right_x in normal_entries:
                if pair_conflict(snapshot, e, shifts[left_d.shift_id], shifts[right_d.shift_id]):
                    model.add(left_x + right_x <= 1)
        for choices in by_shift.values():
            if len(choices) > 1:
                model.add_at_most_one(choices)
        profile_key = tuple(sorted(e.profile_ids))
        if profile_key not in conflict_graphs:
            maximum_rest = max(
                [0]
                + [
                    max(p.min_rest_minutes, p.after_night_rest_minutes,
                        p.after_night_block_rest_minutes)
                    for p in snapshot.profiles if p.id in e.profile_ids
                ]
            )
            edges = []
            for i, left in enumerate(ordered_shifts):
                if monotonic() >= deadline:
                    return timed_out()
                for j in range(i + 1, len(ordered_shifts)):
                    right = ordered_shifts[j]
                    # Later duties cannot overlap, interleave, or violate any
                    # of this employee's rest profiles past this upper bound.
                    if shift_bounds[right.id][0] - shift_bounds[left.id][1] >= maximum_rest:
                        break
                    if pair_conflict(snapshot, e, left, right):
                        edges.append((left.id, right.id))
            conflict_graphs[profile_key] = edges
        for left, right in conflict_graphs[profile_key]:
            if left in by_shift and right in by_shift:
                model.add_at_most_one(by_shift[left] + by_shift[right])
        if any(
            p.id in e.profile_ids and p.after_night_block_rest_minutes
            for p in snapshot.profiles
        ):
            ordered = sorted(
                entries, key=lambda item: bounds(shifts[item[0].shift_id])[0]
            )
            for i, (da, xa) in enumerate(ordered):
                if monotonic() >= deadline:
                    return timed_out()
                for j in range(i + 1, len(ordered)):
                    db, xb = ordered[j]
                    if night_block_conflict(
                        snapshot, e, shifts[da.shift_id], shifts[db.shift_id]
                    ):
                        between = [
                            x
                            for d, x in ordered[i + 1 : j]
                            if bounds(shifts[da.shift_id])[0]
                            < bounds(shifts[d.shift_id])[0]
                            < bounds(shifts[db.shift_id])[0]
                        ]
                        model.add(xa + xb <= 1 + sum(between))
        daily = defaultdict(list)
        work = defaultdict(list)
        night = defaultdict(list)
        beginnt = defaultdict(list)
        period_weekend = defaultdict(list)
        paid = []
        planning_tails = []
        for d, x in entries:
            s = shifts[d.shift_id]
            for day, n in dates_by_shift[d.shift_id].items():
                daily[day].append(n * x)
                work[day].append(x)
            if s.kind == "night":
                night[shift_day[d.shift_id]].append(x)
            beginnt[shift_day[d.shift_id]].append(x)
            if snapshot.period_start <= shift_day[d.shift_id] <= snapshot.period_end:
                paid.append(s.paid_minutes * x)
                tail = {day for day in dates_by_shift[d.shift_id] if day > snapshot.period_end}
                if tail:
                    planning_tails.append((x, tail))
                for day in dates_by_shift[d.shift_id]:
                    if day.weekday() >= 5:
                        period_weekend[day - timedelta(days=day.weekday())].append(x)
                # Personal context is no staffing choice: it has no position
                # and satisfies no preference.
                if d.shift_id in boundary_keys:
                    continue
                if e.preferred_kind and e.preferred_kind != s.kind:
                    cost("preferences", x, snapshot.objectives.wishes)
                if (
                    e.preferred_functions
                    and positions[d.position_id].function_id
                    not in e.preferred_functions
                ):
                    cost("preferences", x, snapshot.objectives.wishes)
        wv, nv = {}, {}
        for day, choices in work.items():
            v = model.new_bool_var("work:" + e.id + ":" + str(day))
            model.add_max_equality(v, choices)
            wv[day] = v
        for day, choices in night.items():
            v = model.new_bool_var("night:" + e.id + ":" + str(day))
            model.add_max_equality(v, choices)
            nv[day] = v
        bv = {}
        for day, choices in beginnt.items():
            v = model.new_bool_var("starts:" + e.id + ":" + str(day))
            model.add_max_equality(v, choices)
            bv[day] = v
        wev = {}
        for week, choices in period_weekend.items():
            v = model.new_bool_var("weekend:" + e.id + ":" + str(week))
            model.add_max_equality(v, choices)
            wev[week] = v
        worked_vars[e.id], nights_vars[e.id], weekend_vars[e.id] = wv, nv, wev
        if snapshot.objectives.split_weekends:
            # Ein Dienst gehört zu jedem Tag, den er berührt: ein Freitagnachtdienst
            # verbraucht den Samstagmorgen und greift damit ins Wochenende ein.
            for week in sorted({day - timedelta(days=day.weekday())
                                for day in wv if day.weekday() >= 5}):
                sat, sun = week + timedelta(days=5), week + timedelta(days=6)
                # Ohne Arbeitsmöglichkeit an beiden Tagen gibt es nichts zu koppeln.
                if sat not in wv or sun not in wv:
                    continue
                if sat < snapshot.period_start or sun > snapshot.period_end:
                    continue
                split = model.new_bool_var("split_weekend:" + e.id + ":" + str(week))
                model.add_abs_equality(split, wv[sat] - wv[sun])
                cost("split_weekends", split, snapshot.objectives.split_weekends)
        if snapshot.objectives.block_shape:
            max_blocklaenge = max(LAENGENKOSTEN)
            tage = list(dates(snapshot.period_start, snapshot.period_end + timedelta(days=1)))
            # Vor dem Zeitraum enthält bv nur fixierte Dienste oder persönliche
            # Randarbeit; vorhandene Tagesvariablen sind dort zwingend belegt.
            startlaenge = 0
            vortag = snapshot.period_start - timedelta(days=1)
            while vortag in bv and startlaenge < max_blocklaenge:
                startlaenge += 1
                vortag -= timedelta(days=1)
            z_vor = model.new_constant(startlaenge)
            null = model.new_constant(0)
            tupel = [
                (z, 0, 0, LAENGENKOSTEN.get(z, 0)) for z in range(max_blocklaenge + 1)
            ] + [
                (z, 1, min(z + 1, max_blocklaenge), 0) for z in range(max_blocklaenge + 1)
            ]
            for tag in tage:
                z_nach = model.new_int_var(0, max_blocklaenge,
                                           "block_state:" + e.id + ":" + str(tag))
                c = model.new_int_var(0, max(LAENGENKOSTEN.values()),
                                      "block_cost:" + e.id + ":" + str(tag))
                model.add_allowed_assignments([z_vor, bv.get(tag, null), z_nach, c], tupel)
                cost("block_shape", c, snapshot.objectives.block_shape)
                z_vor = z_nach
            # Auch bei einem Dienstbeginn am Folgetag den offenen Block bewerten.
            c = model.new_int_var(0, max(LAENGENKOSTEN.values()), "block_close:" + e.id)
            model.add_allowed_assignments([z_vor, null, null, c], tupel)
            cost("block_shape", c, snapshot.objectives.block_shape)
        # Reuse actual local worked-day variables (including split/overnight
        # duties and fixed boundary assignments). Minimize fragmentation, not
        # a hard block length. Include both edges of the planning period.
        if snapshot.objectives.workday_transitions:
            for day in dates(snapshot.period_start, snapshot.period_end + timedelta(days=1)):
                transition = model.new_bool_var("workday_transition:" + e.id + ":" + str(day))
                model.add_abs_equality(transition, wv.get(day, 0) - wv.get(day - timedelta(days=1), 0))
                cost("workday_transitions", transition, snapshot.objectives.workday_transitions)
        if snapshot.objectives.isolated_days:
            for day in dates(snapshot.period_start, snapshot.period_end + timedelta(days=1)):
                # Ohne Arbeitsmöglichkeit am Tag selbst ist der Term konstant null.
                if day not in wv:
                    continue
                isolated = model.new_bool_var("isolated_day:" + e.id + ":" + str(day))
                model.add_max_equality(isolated, [
                    0, wv.get(day, 0) - wv.get(day - timedelta(days=1), 0)
                    - wv.get(day + timedelta(days=1), 0),
                ])
                cost("isolated_days", isolated, snapshot.objectives.isolated_days)
        for p in snapshot.profiles:
            if p.id not in e.profile_ids:
                continue
            active = list(
                dates(
                    max(p.valid_from, snapshot.period_start),
                    min(p.valid_until, snapshot.period_end),
                )
            )
            for day in active:
                if p.max_daily_minutes is not None:
                    model.add(sum(daily[day]) <= p.max_daily_minutes)
            for week in {day - timedelta(days=day.weekday()) for day in active}:
                if p.max_weekly_minutes is not None:
                    model.add(
                        sum(sum(daily[week + timedelta(days=i)]) for i in range(7))
                        <= p.max_weekly_minutes
                    )
            # Only a selected in-period duty activates checks for its spill
            # beyond period_end. Keep all fixed context in the sums, without
            # rejecting a plan for an unrelated future context-only violation.
            active_weeks = {day - timedelta(days=day.weekday()) for day in active}
            for x, tail in planning_tails:
                tail_days = {
                    day for day in tail if p.valid_from <= day <= p.valid_until
                }
                if p.max_daily_minutes is not None:
                    for day in tail_days:
                        model.add(sum(daily[day]) <= p.max_daily_minutes).only_enforce_if(x)
                if p.max_weekly_minutes is not None:
                    tail_weeks = {day - timedelta(days=day.weekday()) for day in tail_days}
                    for week in tail_weeks - active_weeks:
                        model.add(
                            sum(sum(daily[week + timedelta(days=i)]) for i in range(7))
                            <= p.max_weekly_minutes
                        ).only_enforce_if(x)
            if p.weekly_rest_minutes and p.weekly_rest_frame == "calendar_week":
                # Weekly rest is scoped by overlap with the whole planning
                # calendar week (validator.weekly_windows), not by profile days
                # inside the planning interval. Keep hour-limit scope separate.
                first_week = snapshot.period_start - timedelta(days=snapshot.period_start.weekday())
                rest_weeks = {
                    day for day in dates(first_week, snapshot.period_end)
                    if day.weekday() == 0
                    and p.valid_from <= day + timedelta(days=6)
                    and p.valid_until >= day
                }
                required = p.weekly_rest_minutes + (
                    p.min_rest_minutes if p.weekly_rest_add_daily else 0
                )
                tail_week_triggers = defaultdict(list)
                for x, tail in planning_tails:
                    weeks = {
                        day - timedelta(days=day.weekday()) for day in tail
                        if p.valid_from <= day <= p.valid_until
                    }
                    for week in weeks - rest_weeks:
                        tail_week_triggers[week].append(x)
                for week in sorted(rest_weeks | tail_week_triggers.keys()):
                    wa, wb = (
                        midnight(week, snapshot.timezone),
                        midnight(week + timedelta(days=7), snapshot.timezone),
                    )
                    if p.weekly_rest_add_daily:
                        required = p.weekly_rest_minutes + max(
                            [p.min_rest_minutes]
                            + [
                                q.min_rest_minutes
                                for q in snapshot.profiles
                                if q.id in e.profile_ids
                                and q.valid_from <= week + timedelta(days=6)
                                and q.valid_until >= week
                            ]
                        )
                    candidates = {wa}
                    relevant = []
                    for d, x in entries:
                        spans = segments(shifts[d.shift_id])
                        if any(overlap(span, (wa, wb)) for span in spans):
                            relevant.append((spans, x))
                            candidates.update(
                                b for a, b in spans if wa <= b <= wb - required
                            )
                    witnesses = []
                    for start in candidates:
                        if start + required > wb:
                            continue
                        blocking = [
                            x
                            for spans, x in relevant
                            if any(
                                overlap(span, (start, start + required))
                                for span in spans
                            )
                        ]
                        if not blocking:
                            witnesses = [1]
                            break
                        y = model.new_bool_var(
                            "weekly_rest:" + e.id + ":" + str(week) + ":" + str(start)
                        )
                        model.add(sum(blocking) == 0).only_enforce_if(y)
                        witnesses.append(y)
                    if week in rest_weeks:
                        model.add_bool_or(witnesses)
                    else:
                        # Same conditional scope as daily/weekly hour limits:
                        # the selected duty activates its affected future week.
                        for trigger in tail_week_triggers[week]:
                            model.add_bool_or(witnesses).only_enforce_if(trigger)
            if p.max_period_minutes is not None:
                model.add(
                    sum(sum(daily[day]) for day in active) <= p.max_period_minutes
                )
            if p.max_work_days is not None:
                model.add(sum(wv.get(day, 0) for day in active) <= p.max_work_days)
            if p.max_nights is not None:
                model.add(sum(nv.get(day, 0) for day in active) <= p.max_nights)
            if p.max_weekends is not None:
                relevant = defaultdict(list)
                for day in active:
                    if day.weekday() >= 5 and day in wv:
                        relevant[day - timedelta(days=day.weekday())].append(wv[day])
                profile_weekends = []
                for week, choices in relevant.items():
                    v = model.new_bool_var(
                        "profile_weekend:" + e.id + ":" + p.id + ":" + str(week)
                    )
                    model.add_max_equality(v, choices)
                    profile_weekends.append(v)
                model.add(sum(profile_weekends) <= p.max_weekends)
            for variables, limit in (
                (wv, p.max_consecutive_work_days),
                (nv, p.max_consecutive_nights),
            ):
                if limit:
                    for day in dates(
                        max(p.valid_from, snapshot.period_start),
                        min(
                            p.valid_until,
                            snapshot.context_end,
                            snapshot.period_end + timedelta(days=limit),
                        ),
                    ):
                        model.add(
                            sum(
                                variables.get(day - timedelta(days=i), 0)
                                for i in range(limit + 1)
                            )
                            <= limit
                        )
        upper = (
            sum(shifts[d.shift_id].paid_minutes for d, x in entries)
            + abs(e.balance_minutes)
            + e.credit_minutes
            + e.target_minutes
        )
        # Ein nachweislich unerreichbares Soll darf die übrigen Ziele nicht verdrängen;
        # berichtet wird weiterhin gegen das vertragliche Soll.
        optimization_target = min(
            e.target_minutes,
            reachable_minutes[e.id] + e.balance_minutes + e.credit_minutes,
        )
        deviation = model.new_int_var(0, upper, "hours:" + e.id)
        model.add_abs_equality(
            deviation,
            sum(paid) + e.balance_minutes + e.credit_minutes - optimization_target,
        )
        cost("hours", deviation, snapshot.objectives.hours)
        if (
            fairness_level is not None
            and optimization_target > 0
            and candidate_stats[e.id]["eligible_demands"]
        ):
            # Wer nirgends einsetzbar ist, bliebe sonst der Maßstab für alle.
            faktor = max(1, round(HOURS_SCALE / optimization_target))
            grenze = faktor * upper
            erfuellt = model.new_int_var(-grenze, grenze, "fill:" + e.id)
            model.add(erfuellt == faktor * (
                sum(paid) + e.balance_minutes + e.credit_minutes
            ))
            # Ein einzelnes verzerrtes Periodensoll darf nicht den Maßstab
            # für alle setzen: oberhalb des Deckels zählt der Abstand nicht
            # weiter. Ein zu hoher Einsatz bleibt über das Stundenziel bewertet.
            gedeckelt = model.new_int_var(-grenze, HOURS_CAP, "fill_cap:" + e.id)
            model.add_min_equality(gedeckelt, [erfuellt, HOURS_CAP])
            abstand = model.new_int_var(0, grenze + HOURS_SCALE, "gap:" + e.id)
            model.add_abs_equality(abstand, gedeckelt - fairness_level)
            # In Promille rechnen: die Größenordnung bleibt vergleichbar mit
            # den übrigen Zielen, die Genauigkeit bleibt erhalten.
            promille = model.new_int_var(0, (grenze + HOURS_SCALE) // 1000 + 1,
                                         "gap_promille:" + e.id)
            model.add_division_equality(promille, abstand, 1000)
            cost("hours_fairness", promille, snapshot.objectives.hours_fairness)
        if duty_level is not None and candidate_stats[e.id]["eligible_demands"]:
            # Wer nirgends einsetzbar ist, bliebe sonst der Maßstab für alle.
            obergrenze = max(1, len(normal_entries))
            dienste = model.new_int_var(0, obergrenze, "duties:" + e.id)
            model.add(dienste == sum(x for _, x in normal_entries))
            abweichung = model.new_int_var(0, max(obergrenze, len(snapshot.demands)),
                                           "duties_gap:" + e.id)
            model.add_abs_equality(abweichung, dienste - duty_level)
            cost("duty_fairness", abweichung, snapshot.objectives.duty_fairness)
        if e.contractual_weekly_minutes is not None and snapshot.objectives.hours:
            # Soft calendar-week workload, never an invented hard cap. Full
            # allowance at edges: do not infer weekdays or divide monthly targets.
            # Actual segments include fixed context; credits/pay cannot hide work.
            weeks = {day - timedelta(days=day.weekday())
                     for day in dates(snapshot.period_start, snapshot.period_end)}
            weeks.update(day - timedelta(days=day.weekday())
                         for d, _ in normal_entries
                         if snapshot.period_start <= shift_day[d.shift_id] <= snapshot.period_end
                         for day in dates_by_shift[d.shift_id])
            for week in sorted(weeks):
                terms = [term for day, values in daily.items()
                         if week <= day < week + timedelta(days=7) for term in values]
                upper_week = sum(n for d, _ in entries
                                 for day, n in dates_by_shift[d.shift_id].items()
                                 if week <= day < week + timedelta(days=7))
                excess = model.new_int_var(0, upper_week, f"weekly_contract:{e.id}:{week}")
                model.add_max_equality(excess, [0, sum(terms) - e.contractual_weekly_minutes])
                cost("weekly_contract_excess", excess, snapshot.objectives.hours)
    # Explicit mentor-to-trainee edges with bounded per-duty mentoring slots.
    mentor_load = defaultdict(list)
    for (eid, did), x in xs.items():
        if monotonic() >= deadline:
            return timed_out()
        e, d = employees[eid], demands[did]
        if not supervised(snapshot, e, d):
            continue
        s, p = shifts[d.shift_id], positions[d.position_id]
        choices = []
        for (mid, mdid), mx in xs.items():
            if mid == eid or not employees[mid].mentor_capacity:
                continue
            mentor, md = employees[mid], demands[mdid]
            ms, mp = shifts[md.shift_id], positions[md.position_id]
            if (
                mp.function_id != p.function_id
                or mp.workplace_id != p.workplace_id
                or supervised(snapshot, mentor, md)
                or eligibility(snapshot, mentor, d)
            ):
                continue
            if not all(
                any(a <= c and f <= b for a, b in segments(ms)) for c, f in segments(s)
            ):
                continue
            edge = model.new_bool_var("mentor:" + mid + ":" + eid + ":" + did)
            model.add(edge <= mx)
            choices.append(edge)
            mentor_load[mid, mdid].append(edge)
        model.add(sum(choices) == x)
    for (mid, mdid), edges in mentor_load.items():
        model.add(sum(edges) <= employees[mid].mentor_capacity * xs[mid, mdid])
    for wish in snapshot.wishes:
        choices = [
            x
            for (eid, did), x in xs.items()
            if eid == wish.employee_id and demands[did].shift_id == wish.shift_id
        ]
        cost(
            "wishes",
            1 - sum(choices) if wish.want else sum(choices),
            snapshot.objectives.wishes * wish.priority,
        )
    for key in prior | set(xs):
        cost(
            "changes",
            1 - xs.get(key, 0) if key in prior else xs[key],
            snapshot.objectives.changes,
        )
    # Opportunity-normalized burden shares. Only eligible opportunities enter
    # the denominator; contract fraction scales them. Historical counts count.
    for category, weight, history in (
        ("nights", snapshot.objectives.nights, "historical_nights"),
        ("weekends", snapshot.objectives.weekends, "historical_weekends"),
        ("holidays", snapshot.objectives.holidays, "historical_holidays"),
    ):
        if monotonic() >= deadline:
            return timed_out()
        counts, opportunities, count_bounds = {}, {}, {}
        for e in snapshot.employees:
            eligible = [
                (d, x)
                for d, x in by_employee[e.id]
                if snapshot.period_start <= shift_day[d.shift_id] <= snapshot.period_end
                and (
                    (category == "nights" and shifts[d.shift_id].kind == "night")
                    or (
                        category == "weekends"
                        and any(
                            day.weekday() >= 5 for day in dates_by_shift[d.shift_id]
                        )
                    )
                    or (category == "holidays" and shifts[d.shift_id].holiday)
                )
            ]
            opportunities[e.id] = (
                len({d.shift_id for d, x in eligible}) * e.employment_fraction
            )
            if category == "nights":
                count = sum(
                    v
                    for day, v in nights_vars[e.id].items()
                    if snapshot.period_start <= day <= snapshot.period_end
                )
                count_bounds[e.id] = len({shift_day[d.shift_id] for d, x in eligible})
            elif category == "weekends":
                # Der Zähler zählt Wochen, daher muss auch der Nenner Wochen zählen.
                opportunities[e.id] = len(weekend_vars[e.id]) * e.employment_fraction
                count = sum(weekend_vars[e.id].values())
                count_bounds[e.id] = len(weekend_vars[e.id])
            else:
                count = sum(x for d, x in eligible)
                count_bounds[e.id] = len(eligible)
            counts[e.id] = count + getattr(e, history)
            count_bounds[e.id] += getattr(e, history)
        total_opp = sum(opportunities.values())
        total_count = sum(
            counts[e.id] for e in snapshot.employees if opportunities[e.id]
        )
        if total_opp and weight:
            total_count_bound = sum(
                count_bounds[e.id] for e in snapshot.employees if opportunities[e.id]
            )
            for e in snapshot.employees:
                if opportunities[e.id]:
                    # A demand can staff several people. Both sides of the
                    # weighted share difference need their own valid bound.
                    upper = max(
                        count_bounds[e.id] * total_opp,
                        total_count_bound * opportunities[e.id],
                    )
                    if upper > cp_model.INT_MAX // 400:
                        return result(
                            "MODEL_INVALID",
                            validation=Validation(valid=False, complete=False, diagnostics=[
                                Diagnostic(
                                    code="numeric_range",
                                    message="Die kombinierte Belastungsbewertung überschreitet den unterstützten Zahlenbereich.",
                                )
                            ]),
                        )
                    deviation = model.new_int_var(
                        0, upper, "fair:" + category + ":" + e.id
                    )
                    model.add_abs_equality(
                        deviation,
                        counts[e.id] * total_opp - total_count * opportunities[e.id],
                    )
                    # Integer normalized 1/100 duty error, floor to avoid
                    # large team-size-dependent objective coefficients.
                    scaled = model.new_int_var(
                        0,
                        upper * 100 // total_opp + 1,
                        "fair_scaled:" + category + ":" + e.id,
                    )
                    model.add_division_equality(scaled, deviation * 100, total_opp)
                    cost(category, scaled, weight)
    timings["model_build"] = monotonic() - started - timings["input_validation"]
    parameters["model_variables"] = len(model.proto.variables)
    parameters["model_constraints"] = len(model.proto.constraints)
    warm_started = monotonic()
    warm = None
    if partial and prior - fixed and all(key in xs for key in prior):
        # Saved assignments are proposals, not new fixed constraints. Rebuild
        # their generated duty intervals and independently validate them before
        # requesting the same full-model certificate used for initial plans.
        candidate = [
            Assignment(
                employee_id=eid, demand_id=did, fixed=(eid, did) in fixed,
                segments=[i.model_copy(deep=True)
                          for i in shifts[demands[did].shift_id].segments],
            )
            for eid, did in sorted(prior)
        ]
        checked = validate(snapshot, candidate)
        if checked.valid:
            warm = (candidate, checked)
            model.clear_hints()
            for key, x in xs.items():
                model.add_hint(x, int(key in prior))
    if len(snapshot.employees) >= 40 and not partial:
        initial_plan_deadline = min(started + phase_limit / 2, monotonic() + 12)
        plans = {
            e.id: [
                a.model_copy(deep=True)
                for a in snapshot.assignments
                if a.fixed and a.employee_id == e.id
            ]
            for e in snapshot.employees
        }
        local_validators = {}

        def local_validator(employee):
            if employee.id not in local_validators:
                local_validators[employee.id] = PreparedValidator(
                    snapshot.model_copy(update={
                        "employees": [employee],
                        "assignments": [
                            a for a in snapshot.assignments
                            if a.employee_id == employee.id
                        ],
                        "boundary_work": [
                            w for w in snapshot.boundary_work
                            if w.employee_id == employee.id
                        ],
                        "restrictions": [
                            r for r in snapshot.restrictions
                            if r.employee_id == employee.id
                        ],
                        "wishes": [
                            w for w in snapshot.wishes
                            if w.employee_id == employee.id
                        ],
                    })
                )
            return local_validators[employee.id]
        load = {
            eid: sum(shifts[demands[a.demand_id].shift_id].paid_minutes for a in plan)
            for eid, plan in plans.items()
        }
        failed = False
        ordered_demands = sorted(
            snapshot.demands,
            key=lambda d: (bounds(shifts[d.shift_id])[0], len(by_demand[d.id])),
        )
        for d in ordered_demands:
            count = sum(a.demand_id == d.id for plan in plans.values() for a in plan)
            for _ in range(max(0, d.minimum - count)):
                chosen = None
                for eid in sorted(
                    (eid for eid in employees if (eid, d.id) in xs),
                    key=lambda eid: (
                        load[eid] * 100 / employees[eid].employment_fraction
                    ),
                ):
                    if monotonic() > initial_plan_deadline:
                        break
                    if any(a.demand_id == d.id for a in plans[eid]):
                        continue
                    candidate = Assignment(
                        employee_id=eid,
                        demand_id=d.id,
                        segments=[
                            i.model_copy(deep=True) for i in shifts[d.shift_id].segments
                        ],
                    )
                    if local_validator(employees[eid]).validate(plans[eid] + [candidate]).valid:
                        chosen = candidate
                        break
                if chosen is None:
                    failed = True
                    break
                plans[chosen.employee_id].append(chosen)
                load[chosen.employee_id] += shifts[d.shift_id].paid_minutes
            if failed:
                break
        if not failed:
            candidate = [a for plan in plans.values() for a in plan]
            checked = validate(snapshot, candidate)
            if checked.valid and not any(
                d.code == "vacancy" for d in checked.diagnostics
            ):
                warm = (candidate, checked)
                model.clear_hints()
                chosen = {(a.employee_id, a.demand_id) for a in candidate}
                for key, x in xs.items():
                    model.add_hint(x, int(key in chosen))
    timings["initial_plan"] = monotonic() - warm_started
    weighted = sum(costs)
    coupling_terms = components.get("split_weekends", [])
    coupling = sum(coupling_terms)
    couple_enabled = bool(snapshot.objectives.split_weekends and coupling_terms)
    split_weekends_proven = not couple_enabled
    if couple_enabled:
        parameters["objective_semantics"] = (
            "lexicographic vacancies, then split weekends, then configured weighted costs"
        )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 0
    solver.parameters.symmetry_level = 0
    separation_rounds = 0
    best = None
    phase = "vacancies" if partial else "feasibility"
    model.minimize(sum(vacancies) if partial else 0)
    if warm:
        certificate_started = monotonic()
        certificate = cp_model.CpSolver()
        certificate.parameters.num_search_workers = 1
        certificate.parameters.max_time_in_seconds = max(
            0.001, min(12, time_limit - (monotonic() - started))
        )
        certificate.parameters.fix_variables_to_their_hinted_value = True
        certified_status = certificate.solve(model)
        timings["initial_plan_certificate"] = monotonic() - certificate_started
        parameters["warm_start_certificate_status"] = certificate.status_name(
            certified_status
        )
        parameters["warm_start_certificate_scope"] = (
            "all assignment variables fixed to independently validated proposal"
        )
        if certified_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            warm = None
        else:
            # Carry the complete certified solution into optimization. Hints
            # only for assignments leave thousands of auxiliary variables
            # unresolved before CP-SAT can accept its first incumbent.
            model.clear_hints()
            for index in range(len(model.proto.variables)):
                variable = model.get_int_var_from_proto_index(index)
                model.add_hint(variable, certificate.value(variable))
    if warm:
        # With a complete certified hint, large presolve/probing passes can
        # consume the entire interactive budget before accepting that hint.
        # Search the original equivalent model directly in this case.
        solver.parameters.cp_model_presolve = False
        parameters["quality_presolve"] = False
        plan, checked = warm
        warm_counts = Counter(a.demand_id for a in plan)
        warm_vacancies = sum(max(0, d.minimum - warm_counts[d.id])
                             for d in snapshot.demands)
        metrics = {
            "employees": {},
            "objective_phase": "vacancies" if partial else "validated_initial_solution",
            "separation_rounds": 0,
            "vacancy_count": warm_vacancies,
        }
        for e in snapshot.employees:
            selected = [
                shifts[demands[a.demand_id].shift_id]
                for a in plan
                if a.employee_id == e.id
                and snapshot.period_start
                <= shift_day[demands[a.demand_id].shift_id]
                <= snapshot.period_end
            ]
            # Explicit personal work inside the period is worked and paid
            # time as well; the reported figure must match the objective.
            paid = sum(s.paid_minutes for s in selected) + personal_period_paid[e.id]
            metrics["employees"][e.id] = {
                "duty_blocks": duty_blocks(e.id, plan),
                "paid_minutes": paid,
                "target_minutes": e.target_minutes,
                "reachable_minutes": reachable_minutes[e.id],
                "contractual_weekly_minutes": e.contractual_weekly_minutes,
                "credit_minutes": e.credit_minutes,
                "balance_minutes": e.balance_minutes,
                "deviation_minutes": paid
                + e.credit_minutes
                + e.balance_minutes
                - e.target_minutes,
                "nights": len({shift_day[s.id] for s in selected if s.kind == "night"}),
                "weekends": len(
                    {
                        day - timedelta(days=day.weekday())
                        for s in selected
                        for day in dates_by_shift[s.id]
                        if day.weekday() >= 5
                    }
                ),
                "holidays": sum(s.holiday for s in selected),
            }
        metrics["unfulfilled_wishes"] = [
            w.model_dump(mode="json")
            for w in snapshot.wishes
            if any(
                a.employee_id == w.employee_id
                and demands[a.demand_id].shift_id == w.shift_id
                for a in plan
            )
            != w.want
        ]
        # Fixed-assignment CP-SAT certificate also evaluates every equality-
        # defined cost variable, so contributions use the identical contract.
        metrics["objective_contributions"] = {
            key: sum(
                certificate.value(expr) if not isinstance(expr, int) else expr
                for expr in terms
            )
            for key, terms in components.items()
        }
        metrics["weighted_objective_contributions"] = {
            key: sum(
                certificate.value(expr) if not isinstance(expr, int) else expr
                for expr in terms
            )
            for key, terms in weighted_components.items()
        }
        if couple_enabled:
            split_count = metrics["objective_contributions"]["split_weekends"]
            split_weekends_proven = split_count == 0
            parameters["split_weekend_count"] = split_count
            parameters["split_weekends_proven"] = split_weekends_proven
        parameters["first_feasible_seconds"] = monotonic() - started
        checked.diagnostics.extend(diagnostics)
        best = result(
            "FEASIBLE",
            plan,
            checked,
            metrics=metrics,
            objective_value=float(warm_vacancies) if partial else float(
                sum(metrics["weighted_objective_contributions"].values())
            ),
        )
        if partial:
            # Continue minimizing vacancies; a valid saved partial plan does
            # not prove optimal coverage, even if the fixed-hint solve was optimal.
            model.add(sum(vacancies) <= warm_vacancies)
        else:
            phase = "couple" if couple_enabled else "quality"
            model.minimize(coupling if couple_enabled else weighted)
            if couple_enabled:
                model.add(coupling <= split_count)
    # Coupling shares the coverage allowance when active; quality retains
    # the final fifth. Earlier tiers never trade against weighted penalties.
    phases_started = monotonic()
    phase_budget = max(0, phase_deadline - phases_started)
    coverage_deadline = phases_started + phase_budget * (0.5 if couple_enabled else 0.8)
    coupling_deadline = phases_started + phase_budget * 0.8
    coverage_proven = not partial
    while True:
        remaining = phase_limit - (monotonic() - started)
        if best:
            # Leave a small allowance to copy and independently recheck the
            # final incumbent; a validated fallback is already available.
            remaining -= min(1.0, time_limit * 0.05)
        if remaining <= 0:
            if best:
                best.solver_status = "FEASIBLE"
                return finish(best)
            return result(
                "UNKNOWN",
                validation=Validation(
                    valid=False,
                    complete=False,
                    diagnostics=diagnostics
                    + [
                        Diagnostic(
                            code="time_limit",
                            message="Zeitlimit ohne unabhängig geprüfte Lösung.",
                        )
                    ],
                ),
            )
        if phase == "vacancies" or (couple_enabled and phase == "feasibility"):
            remaining = min(remaining, max(0.001, coverage_deadline - monotonic()))
        elif phase == "couple":
            remaining = min(remaining, max(0.001, coupling_deadline - monotonic()))
        elif partial and phase == "quality":
            # Improve the certified fixed-coverage incumbent with OR-Tools'
            # native portfolio, retaining the single-worker crash workaround.
            # Do not change coverage, certification, or non-partial search.
            # The original deadline, objective cap and validator remain active.
            solver.parameters.interleave_search = True
            solver.parameters.use_lns_only = True
            solver.parameters.cp_model_presolve = True
            parameters["quality_search"] = "single_worker_interleaved_lns"
            parameters["quality_presolve"] = True
        solver.parameters.max_time_in_seconds = remaining
        search_started = monotonic()
        if progress is not None and plan_raster is None:
            plan_raster = _plan_raster(snapshot, xs, demands, shift_day, shifts)
        beobachter = (
            _Zwischenstand(phase, search_started, started, progress, plan_raster)
            if progress is not None else None
        )
        status = solver.solve(model, beobachter) if beobachter else solver.solve(model)
        search_seconds = monotonic() - search_started
        timings["search"] = timings.get("search", 0) + search_seconds
        name = solver.status_name(status)
        trace = {
            "phase": phase,
            "started_seconds": search_started - started,
            "budget_seconds": remaining,
            "search_seconds": search_seconds,
            "native_status": name,
            "independently_valid": None,
            "accepted": False,
        }
        note(trace)
        parameters["last_optimization_status"] = name
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if best:
                best.solver_status = "FEASIBLE"
                return finish(best)
            message = (
                model.validate()
                if status == cp_model.MODEL_INVALID
                else (
                    "Das verbindliche Modell ist unlösbar; Konflikte können mehrere Stellen und Regeln umfassen."
                    if status == cp_model.INFEASIBLE
                    else "Noch keine Lösung gefunden."
                )
            )
            return result(
                name,
                validation=Validation(
                    valid=False,
                    complete=False,
                    diagnostics=diagnostics
                    + [Diagnostic(code=name.lower(), message=message)],
                ),
            )
        assignments = [
            Assignment(
                employee_id=eid,
                demand_id=did,
                fixed=(eid, did) in fixed,
                segments=[
                    interval.model_copy(deep=True)
                    for interval in shifts[demands[did].shift_id].segments
                ],
            )
            for (eid, did), x in xs.items()
            if solver.value(x)
        ]
        validation_started = monotonic()
        checked = validate(snapshot, assignments)
        timings["result_validation"] = (
            timings.get("result_validation", 0) + monotonic() - validation_started
        )
        hard = [d for d in checked.diagnostics if d.code not in ("vacancy", "context")]
        trace["independently_valid"] = checked.valid
        if hard:
            # Valid inequalities: violating employee schedules cannot remain
            # entirely selected. For non-monotone rules use exact no-good.
            violating = {d.employee_id for d in hard if d.employee_id}
            if violating and all(
                d.code not in ("mentoring", "night_block") for d in hard
            ):
                for eid in violating:
                    selected = [
                        xs[a.employee_id, a.demand_id]
                        for a in assignments
                        if a.employee_id == eid
                    ]
                    model.add(sum(selected) <= len(selected) - 1)
            else:
                selected = {(a.employee_id, a.demand_id) for a in assignments}
                model.add(
                    sum(1 - x if key in selected else x for key, x in xs.items()) >= 1
                )
            separation_rounds += 1
            continue
        # Capacity hints explain vacancies, but are not rule violations.
        # Attach only after independent validation and separation so a valid
        # partial plan stays valid and does not trigger a no-good cut.
        checked.diagnostics.extend(diagnostics)
        parameters.setdefault("first_feasible_seconds", monotonic() - started)
        metrics = {
            "employees": {},
            "objective_contributions": {
                key: sum(
                    solver.value(expr) if not isinstance(expr, int) else expr
                    for expr in values
                )
                for key, values in components.items()
            },
            "weighted_objective_contributions": {
                key: sum(
                    solver.value(expr) if not isinstance(expr, int) else expr
                    for expr in values
                )
                for key, values in weighted_components.items()
            },
            "separation_rounds": separation_rounds,
            "objective_phase": phase,
            "vacancy_count": sum(staffing_gaps(snapshot, Counter(
                a.demand_id for a in assignments
            )).values()),
        }
        for e in snapshot.employees:
            selected = [
                shifts[demands[a.demand_id].shift_id]
                for a in assignments
                if a.employee_id == e.id
                and snapshot.period_start
                <= shift_day[demands[a.demand_id].shift_id]
                <= snapshot.period_end
            ]
            # Explicit personal work inside the period is worked and paid
            # time as well; the reported figure must match the objective.
            paid = sum(s.paid_minutes for s in selected) + personal_period_paid[e.id]
            metrics["employees"][e.id] = {
                "duty_blocks": duty_blocks(e.id, assignments),
                "paid_minutes": paid,
                "target_minutes": e.target_minutes,
                "reachable_minutes": reachable_minutes[e.id],
                "contractual_weekly_minutes": e.contractual_weekly_minutes,
                "credit_minutes": e.credit_minutes,
                "balance_minutes": e.balance_minutes,
                "deviation_minutes": paid
                + e.credit_minutes
                + e.balance_minutes
                - e.target_minutes,
                "nights": len({shift_day[s.id] for s in selected if s.kind == "night"}),
                "weekends": len(
                    {
                        day - timedelta(days=day.weekday())
                        for s in selected
                        for day in dates_by_shift[s.id]
                        if day.weekday() >= 5
                    }
                ),
                "holidays": sum(s.holiday for s in selected),
            }
        metrics["unfulfilled_wishes"] = [
            w.model_dump(mode="json")
            for w in snapshot.wishes
            if any(
                a.employee_id == w.employee_id
                and demands[a.demand_id].shift_id == w.shift_id
                for a in assignments
            )
            != w.want
        ]
        trace.update({
            "accepted": True,
            "vacancy_count": metrics["vacancy_count"],
            "weighted_quality_cost": sum(metrics["weighted_objective_contributions"].values()),
            "objective_value": solver.objective_value,
            "best_bound": solver.best_objective_bound,
        })
        if couple_enabled:
            split_count = metrics["objective_contributions"]["split_weekends"]
            split_weekends_proven = (
                split_count == 0
                or (phase == "couple" and status == cp_model.OPTIMAL)
                or (phase == "quality" and split_weekends_proven)
            )
            parameters["split_weekend_count"] = split_count
            parameters["split_weekends_proven"] = split_weekends_proven
            trace["split_weekend_count"] = split_count
        if phase == "quality" and not coverage_proven:
            name = "FEASIBLE"
            metrics["quality_scope"] = "fixed incumbent coverage; global coverage unproven"
        elif phase == "quality" and not split_weekends_proven:
            name = "FEASIBLE"
            metrics["quality_scope"] = "bounded incumbent split weekends; global coupling unproven"
        best = result(
            name,
            assignments,
            checked,
            metrics=metrics,
            objective_value=solver.objective_value,
            best_bound=solver.best_objective_bound,
        )
        if phase == "feasibility":
            if couple_enabled:
                model = model.clone()
                model.add(coupling <= split_count)
            model.minimize(coupling if couple_enabled else weighted)
            phase = "couple" if couple_enabled else "quality"
            best.objective_value = None
            best.best_bound = None
            model.clear_hints()
            if couple_enabled:
                for index in range(len(model.proto.variables)):
                    variable = model.get_int_var_from_proto_index(index)
                    model.add_hint(variable, solver.value(variable))
            else:
                for key, x in xs.items():
                    model.add_hint(x, solver.value(x))
            continue
        if phase in ("vacancies", "couple"):
            # Clone preserves hard rules and variable indices, while isolating
            # each tier's bound from the preceding optimization model.
            model = model.clone()
            if phase == "vacancies":
                optimum = solver.value(sum(vacancies))
                coverage_proven = status == cp_model.OPTIMAL or optimum == 0
                parameters["coverage_proven"] = coverage_proven
                parameters["quality_coverage_count"] = optimum
                model.add(sum(vacancies) == optimum)
                phase = "couple" if couple_enabled else "quality"
                if couple_enabled:
                    model.add(coupling <= split_count)
            else:
                if split_weekends_proven:
                    model.add(coupling == split_count)
                else:
                    model.add(coupling <= split_count)
                phase = "quality"
            if phase == "couple":
                model.minimize(coupling)
            else:
                model.add(weighted <= sum(metrics["weighted_objective_contributions"].values()))
                model.minimize(weighted)
            model.clear_hints()
            for index in range(len(model.proto.variables)):
                variable = model.get_int_var_from_proto_index(index)
                model.add_hint(variable, solver.value(variable))
            continue
        return finish(best)
