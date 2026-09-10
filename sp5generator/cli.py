"""Standalone command line interface."""

import argparse
import json
import sys
from pathlib import Path
from . import __version__
from .models import Snapshot, Result


def _write(value, path):
    text = (
        value.model_dump_json(indent=2)
        if hasattr(value, "model_dump_json")
        else json.dumps(value, ensure_ascii=False, indent=2)
    )
    if path:
        Path(path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sp5-generator")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--employees", type=int, default=12)
    demo.add_argument("--days", type=int, default=14)
    demo.add_argument("--impossible", action="store_true")
    demo.add_argument("-o", "--output")
    solve = commands.add_parser("solve")
    solve.add_argument("input")
    solve.add_argument("-o", "--output")
    solve.add_argument("--time-limit", type=float, default=30)
    solve.add_argument("--partial", action="store_true")
    validate = commands.add_parser("validate")
    validate.add_argument("input")
    validate.add_argument("result")
    validate.add_argument("-o", "--output")
    export = commands.add_parser("export")
    export.add_argument("input")
    export.add_argument("result")
    export.add_argument("output")
    schema = commands.add_parser("schema")
    schema.add_argument("model", choices=["input", "result"])
    schema.add_argument("-o", "--output")
    worker = commands.add_parser("worker")
    worker.add_argument("--store", required=True)
    worker.add_argument("--once", action="store_true")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--state-dir", default="./generator-state")
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            try:
                import uvicorn
                from .webapp import create_app
            except ImportError:
                print(
                    json.dumps(
                        {
                            "error": "missing_web_dependencies",
                            "message": "Install openschichtplaner5-generator[web]",
                        }
                    ),
                    file=sys.stderr,
                )
                return 2
            uvicorn.run(create_app(args.state_dir), host=args.host, port=args.port, access_log=False)
            return 0
        if args.command == "demo":
            from .demo import make_demo

            if not 4 <= args.employees <= 1000 or not 1 <= args.days <= 366:
                raise ValueError("employees: 4..1000; days: 1..366")
            _write(make_demo(args.employees, args.days, args.impossible), args.output)
            return 0
        if args.command == "schema":
            _write(
                (Snapshot if args.model == "input" else Result).model_json_schema(),
                args.output,
            )
            return 0
        if args.command == "worker":
            from .jobs import run_worker

            run_worker(args.store, once=args.once)
            return 0
        snapshot = Snapshot.model_validate_json(
            Path(args.input).read_text(encoding="utf-8")
        )
        if args.command == "solve":
            from .solver import solve as compute

            result = compute(snapshot, time_limit=args.time_limit, partial=args.partial)
            _write(result, args.output)
            if result.solver_status in ("OPTIMAL", "FEASIBLE"):
                return 0 if result.validation.complete else 3
            return {"INFEASIBLE": 4, "UNKNOWN": 5, "MODEL_INVALID": 2}[
                result.solver_status
            ]
        result = Result.model_validate_json(
            Path(args.result).read_text(encoding="utf-8")
        )
        from .domain import snapshot_hash

        if result.snapshot_hash != snapshot_hash(snapshot):
            raise ValueError("Result does not reference this snapshot")
        if args.command == "validate":
            from .validator import validate as check

            validation = check(snapshot, result.assignments)
            _write(validation, args.output)
            return 0 if validation.valid and validation.complete else 3
        from .export import export_table

        export_table(snapshot, result, args.output)
        return 0
    except (ValueError, OSError) as exc:
        # Do not echo source payloads from schema validation errors.
        from pydantic import ValidationError

        detail = (
            "Input does not match schema; use the schema command"
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        print(
            json.dumps({"error": "invalid_input", "message": detail}), file=sys.stderr
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
