"""Local CP-SAT optimization with independently checked incumbent separation."""

from collections import defaultdict
from datetime import timedelta
from itertools import combinations
from time import monotonic
from ortools.sat.python import cp_model
from .models import Assignment, Diagnostic, Result, Validation
from .domain import (
    snapshot_hash,
    input_diagnostics,
    eligibility,
    pair_conflict,
    supervised,
    night_block_conflict,
    maximum_matching,
)
from .timeutils import (
    bounds,
    local_day,
    day_minutes,
    dates,
    segments,
    midnight,
    overlap,
)
from .validator import validate


# OR-Tools 9.15 can segfault during parallel quality search on a valid demo
# model. Use the verified single-worker path for every production solve.
SEARCH_WORKERS = 1


def solve(snapshot, time_limit=30, partial=False):
    started = monotonic()
    parameters = {
        "time_limit": time_limit,
        "partial": partial,
        "workers": SEARCH_WORKERS,
        "random_seed": 0,
        "objective_semantics": "lexicographic vacancies, then configured weighted costs",
    }

    def result(status, assignments=None, validation=None, **kwargs):
        assignments = assignments or []
        counts = defaultdict(int)
        for a in assignments:
            counts[a.demand_id] += 1
        return Result(
            snapshot_id=snapshot.id,
            snapshot_hash=snapshot_hash(snapshot),
            solver_status=status,
            assignments=assignments,
            vacancies={
                d.id: d.minimum - counts[d.id]
                for d in snapshot.demands
                if counts[d.id] < d.minimum
            },
            validation=validation
            or Validation(valid=False, complete=False, diagnostics=[]),
            runtime_seconds=monotonic() - started,
            parameters=parameters,
            **kwargs,
        )

    issues = input_diagnostics(snapshot)
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
    demands = {d.id: d for d in snapshot.demands}
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
    diagnostics = []
    for e in snapshot.employees:
        for d in snapshot.demands:
            in_period = (
                snapshot.period_start <= shift_day[d.shift_id] <= snapshot.period_end
            )
            if not in_period and (e.id, d.id) not in fixed:
                continue
            reasons = eligibility(snapshot, e, d)
            if reasons:
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
    vacancies = []
    for d in snapshot.demands:
        choices = by_demand[d.id]
        if d.maximum is not None:
            model.add(sum(choices) <= d.maximum)
        if len(choices) < d.minimum:
            diagnostics.append(
                Diagnostic(
                    code="candidate_shortage",
                    message=f"{d.minimum} benötigte Stellen; nur {len(choices)} individuell geeignete Personen.",
                    demand_id=d.id,
                    date=str(shift_day[d.shift_id]),
                )
            )
        if partial:
            v = model.new_int_var(0, d.minimum, "vacancy:" + d.id)
            model.add(sum(choices) + v >= d.minimum)
            vacancies.append(v)
        else:
            model.add(sum(choices) >= d.minimum)
    for sid in shifts:
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

    pair_cache = {}
    worked_vars = {}
    nights_vars = {}
    weekend_vars = {}
    for e in snapshot.employees:
        entries = by_employee[e.id]
        for (da, xa), (db, xb) in combinations(entries, 2):
            pair_key = (tuple(e.profile_ids), da.shift_id, db.shift_id)
            if pair_key not in pair_cache:
                pair_cache[pair_key] = pair_conflict(
                    snapshot, e, shifts[da.shift_id], shifts[db.shift_id]
                )
            if pair_cache[pair_key]:
                model.add(xa + xb <= 1)
        if any(
            p.id in e.profile_ids and p.after_night_block_rest_minutes
            for p in snapshot.profiles
        ):
            ordered = sorted(
                entries, key=lambda item: bounds(shifts[item[0].shift_id])[0]
            )
            for i, (da, xa) in enumerate(ordered):
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
        period_weekend = defaultdict(list)
        paid = []
        for d, x in entries:
            s = shifts[d.shift_id]
            for day, n in dates_by_shift[s.id].items():
                daily[day].append(n * x)
                work[day].append(x)
            if s.kind == "night":
                night[shift_day[s.id]].append(x)
            if snapshot.period_start <= shift_day[s.id] <= snapshot.period_end:
                paid.append(s.paid_minutes * x)
                for day in dates_by_shift[s.id]:
                    if day.weekday() >= 5:
                        period_weekend[day - timedelta(days=day.weekday())].append(x)
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
        wev = {}
        for week, choices in period_weekend.items():
            v = model.new_bool_var("weekend:" + e.id + ":" + str(week))
            model.add_max_equality(v, choices)
            wev[week] = v
        worked_vars[e.id], nights_vars[e.id], weekend_vars[e.id] = wv, nv, wev
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
            if p.weekly_rest_minutes and p.weekly_rest_frame == "calendar_week":
                required = p.weekly_rest_minutes + (
                    p.min_rest_minutes if p.weekly_rest_add_daily else 0
                )
                for week in {day - timedelta(days=day.weekday()) for day in active}:
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
                    model.add_bool_or(witnesses)
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
        deviation = model.new_int_var(0, upper, "hours:" + e.id)
        model.add_abs_equality(
            deviation,
            sum(paid) + e.balance_minutes + e.credit_minutes - e.target_minutes,
        )
        cost("hours", deviation, snapshot.objectives.hours)
    # Explicit mentor-to-trainee edges with bounded per-duty mentoring slots.
    mentor_load = defaultdict(list)
    for (eid, did), x in xs.items():
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
    warm = None
    if len(snapshot.employees) >= 40 and not partial:
        deadline = min(started + time_limit / 2, monotonic() + 12)
        plans = {
            e.id: [
                a.model_copy(deep=True)
                for a in snapshot.assignments
                if a.fixed and a.employee_id == e.id
            ]
            for e in snapshot.employees
        }
        local_snapshots = {
            e.id: snapshot.model_copy(
                update={
                    "employees": [e],
                    "assignments": [
                        a for a in snapshot.assignments if a.employee_id == e.id
                    ],
                    "restrictions": [
                        r for r in snapshot.restrictions if r.employee_id == e.id
                    ],
                    "wishes": [w for w in snapshot.wishes if w.employee_id == e.id],
                }
            )
            for e in snapshot.employees
        }
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
                    if monotonic() > deadline:
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
                    if validate(local_snapshots[eid], plans[eid] + [candidate]).valid:
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
    weighted = sum(costs)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = SEARCH_WORKERS
    solver.parameters.random_seed = 0
    solver.parameters.symmetry_level = 0
    separation_rounds = 0
    best = None
    phase = "vacancies" if partial else "feasibility"
    model.minimize(sum(vacancies) if partial else 0)
    if warm:
        certificate = cp_model.CpSolver()
        certificate.parameters.num_search_workers = 1
        certificate.parameters.max_time_in_seconds = max(
            0.001, min(12, time_limit - (monotonic() - started))
        )
        certificate.parameters.fix_variables_to_their_hinted_value = True
        certified_status = certificate.solve(model)
        parameters["warm_start_certificate_status"] = certificate.status_name(
            certified_status
        )
        parameters["warm_start_certificate_scope"] = (
            "all assignment variables fixed to independently validated proposal"
        )
        if certified_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            warm = None
    if warm:
        plan, checked = warm
        metrics = {
            "employees": {},
            "objective_phase": "validated_initial_solution",
            "separation_rounds": 0,
            "vacancy_count": 0,
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
            paid = sum(s.paid_minutes for s in selected)
            metrics["employees"][e.id] = {
                "paid_minutes": paid,
                "target_minutes": e.target_minutes,
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
        best = result(
            "FEASIBLE",
            plan,
            checked,
            metrics=metrics,
            objective_value=float(
                sum(metrics["weighted_objective_contributions"].values())
            ),
        )
        phase = "quality"
        model.minimize(weighted)
    while True:
        remaining = time_limit - (monotonic() - started)
        if remaining <= 0:
            if best:
                best.solver_status = "FEASIBLE"
                best.runtime_seconds = monotonic() - started
                return best
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
        solver.parameters.max_time_in_seconds = remaining
        status = solver.solve(model)
        name = solver.status_name(status)
        parameters["last_optimization_status"] = name
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if best:
                best.solver_status = "FEASIBLE"
                best.runtime_seconds = monotonic() - started
                return best
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
        checked = validate(snapshot, assignments)
        hard = [d for d in checked.diagnostics if d.code not in ("vacancy", "context")]
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
            "vacancy_count": sum(
                max(0, d.minimum - sum(a.demand_id == d.id for a in assignments))
                for d in snapshot.demands
            ),
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
            paid = sum(s.paid_minutes for s in selected)
            metrics["employees"][e.id] = {
                "paid_minutes": paid,
                "target_minutes": e.target_minutes,
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
        best = result(
            name,
            assignments,
            checked,
            metrics=metrics,
            objective_value=solver.objective_value,
            best_bound=solver.best_objective_bound,
        )
        if phase == "feasibility":
            model.minimize(weighted)
            phase = "quality"
            best.objective_value = None
            best.best_bound = None
            model.clear_hints()
            for key, x in xs.items():
                model.add_hint(x, solver.value(x))
            continue
        if phase == "vacancies" and status == cp_model.OPTIMAL:
            optimum = solver.value(sum(vacancies))
            model.add(sum(vacancies) == optimum)
            model.minimize(weighted)
            phase = "quality"
            continue
        return best
