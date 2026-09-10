"""Read-only bridge to an explicitly configured SP5 HTTP API."""

import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

from .sp5_adapter import historical_matrix, import_snapshot
from .hierarchy import resolve_group_selection, group_tree


class APIImportError(ValueError):
    """Sanitized source error, without response bodies or credentials."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise APIImportError("API-Weiterleitungen sind nicht erlaubt.")


class APIClient:
    def __init__(self):
        base = os.environ.get("SP5_API_URL", "").rstrip("/")
        parsed = urlsplit(base)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise APIImportError(
                "SP5_API_URL muss eine HTTP(S)-Adresse ohne Zugangsdaten sein."
            )
        self.base = base[:-4] if base.endswith("/api") else base
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())
        self.cache = {}
        self.headers = {"Accept": "application/json"}
        dev = os.environ.get("SP5_API_DEV_MODE", "").lower() in ("1", "true", "yes")
        if dev:
            status = self._read("/api/dev/mode")
            if not isinstance(status, dict) or status.get("dev_mode") is not True:
                raise APIImportError("Die konfigurierte API bestätigt keinen aktiven Dev-Modus.")
            # Public protocol marker accepted only by explicitly enabled SP5 dev mode.
            self.headers["Authorization"] = "Bearer __dev_mode__"
        else:
            token_file = os.environ.get("SP5_API_TOKEN_FILE")
            if not token_file:
                raise APIImportError("SP5_API_TOKEN_FILE ist nicht konfiguriert; für eine Dev-API SP5_API_DEV_MODE explizit aktivieren.")
            try:
                token = Path(token_file).read_text().strip()
            except (OSError, UnicodeError):
                raise APIImportError("API-Token-Datei kann nicht gelesen werden.") from None
            if not token or len(token) > 16384 or any(c.isspace() for c in token):
                raise APIImportError("API-Token-Datei enthält kein gültiges Sitzungstoken.")
            self.headers["Authorization"] = "Bearer " + token

    def _read(self, path):
        try:
            with self.opener.open(
                Request(self.base + path, headers=self.headers), timeout=30
            ) as response:
                raw = response.read(32 * 1024 * 1024 + 1)
                if len(raw) > 32 * 1024 * 1024:
                    raise APIImportError("API-Antwort überschreitet die Importgrenze.")
                return json.loads(raw)
        except HTTPError as exc:
            raise APIImportError(
                f"API-Anfrage abgelehnt (HTTP {exc.code}); Zugriff und API-Version prüfen."
            ) from None
        except (URLError, OSError, ValueError, UnicodeError):
            raise APIImportError(
                "API nicht erreichbar oder Antwort ungültig."
            ) from None

    def get(self, path, **params):
        if params:
            path += "?" + urlencode(params)
        if path not in self.cache:
            self.cache[path] = self._read(path)
        return self.cache[path]

    def verify(self):
        before = json.dumps(self.cache, sort_keys=True, separators=(",", ":"))
        for path, value in self.cache.items():
            if self._read(path) != value:
                raise APIImportError(
                    "API-Daten wurden während des Imports verändert; erneut importieren."
                )
        return hashlib.sha256(before.encode()).hexdigest()

    def authorize(self):
        me = self.get("/api/auth/me")
        if not isinstance(me, dict) or me.get("showabs_mode") != 0:
            raise APIImportError(
                "API muss vollständige Abwesenheitsinformationen freigeben; eingeschränkte Sicht ist nicht planbar."
            )


class _Database:
    def __init__(self, client, team):
        self.client, self.team = client, team
        self.scope = None

    def rows(self, path, **params):
        rows = self.client.get(path, **params)
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise APIImportError("API-Listenformat ist nicht kompatibel.")
        return rows

    def get_groups(self):
        return self.rows("/api/groups", include_hidden="true")

    def get_employees(self, **kw):
        return self.rows("/api/employees", include_hidden="true")

    def get_group_members(self, group):
        return [r["ID"] for r in self.rows(f"/api/groups/{group}/members")]

    def get_employee_groups(self, employee):
        return [g for g in (self.scope if self.scope is not None else resolve_group_selection(self.get_groups(), self.team))
                if employee in self.get_group_members(g)]

    def get_holidays(self):
        return self.rows("/api/holidays")

    def get_shifts(self, **kw):
        return self.rows("/api/shifts", include_hidden="true")

    def get_workplaces(self, **kw):
        return self.rows("/api/workplaces", include_hidden="true")

    def get_staffing_requirements(self):
        data = self.client.get("/api/staffing-requirements")
        if not isinstance(data, dict) or not all(
            isinstance(data.get(k), list)
            for k in ("shift_requirements", "daily_requirements")
        ):
            raise APIImportError("API-Bedarfsformat ist unvollständig.")
        return data

    def get_special_staffing(self, **kw):
        return self.rows("/api/staffing-requirements/special", group_id=kw.get("group_id", self.team))

    def get_restrictions(self):
        return self.rows("/api/restrictions")

    def get_schedule(self, year, month, **kw):
        return self.rows(
            "/api/schedule",
            year=year,
            month=month,
            group_id=kw.get("group_id", self.team),
            plan=kw.get("plan", "ist"),
        )


def inspect_api():
    """Return only selectable groups, never configuration or login details."""
    client = APIClient()
    client.authorize()
    try:
        groups = _Database(client, None).get_groups()
        return {
            "groups": group_tree(groups),
            "source_read_only": True,
            "source": "sp5-api",
        }
    except (KeyError, TypeError):
        raise APIImportError("API-Gruppenformat ist nicht kompatibel.") from None


def import_api(
    period_start,
    period_end,
    team_id=None,
    timezone="Europe/Vienna",
    history_start=None,
    history_end=None,
    history_plan="ist",
    team_ids=None,
):
    """Read canonical snapshots and explicit history proposals through the existing API."""
    if not 0 <= (period_end - period_start).days <= 366:
        raise APIImportError("Planungszeitraum muss 1 bis 367 Kalendertage umfassen.")
    history_end = history_end or period_start - timedelta(days=1)
    history_start = history_start or history_end - timedelta(days=89)
    if (
        history_end >= period_start
        or history_end < history_start
        or (history_end - history_start).days > 1096
    ):
        raise APIImportError("Historischer Zeitraum ist ungültig oder zu lang.")
    if history_plan not in ("ist", "soll", "both"):
        raise APIImportError("Historische Plansicht muss ist, soll oder both sein.")
    try:
        client = APIClient()
        client.authorize()
        db = _Database(client, None)
        scope = resolve_group_selection(db.get_groups(), team_id, team_ids)
        team = db.team = scope[0]
        db.scope = scope
        members = {eid for gid in scope for eid in db.get_group_members(gid)}
        if not members <= {e["ID"] for e in db.get_employees()}:
            raise APIImportError(
                "API-Personensicht ist für die ausgewählte Gruppe unvollständig."
            )
        snapshot = import_snapshot(db, period_start, period_end, timezone=timezone, team_ids=[str(g) for g in scope])
        matrix = historical_matrix(
            db, snapshot, history_start, history_end, history_plan
        )
        fingerprint = client.verify()
    except APIImportError:
        raise
    except (ValueError, KeyError, TypeError, OverflowError):
        raise APIImportError(
            "API-Daten sind mit dem Importvertrag nicht kompatibel; Felder und Zeitangaben lokal prüfen."
        ) from None
    snapshot.metadata.update(
        {
            "adapter": "sp5-api",
            "source_read_only": True,
            "source_fingerprint": fingerprint,
            "source_consistency": "repeated-response-comparison; no API transaction",
            "selected_team_id": str(team),
            "history_matrix": matrix,
            "history_plan": history_plan,
            "history_period": {"start": str(history_start), "end": str(history_end)},
            "history_notice": "Bisherige Einsätze sind Vorschläge, keine bestätigten Freigaben oder Qualifikationen.",
            "source_import_id": snapshot.id,
        }
    )
    snapshot.unresolved.extend(
        [
            "API-Zusatzdaten für Verfügbarkeit, Skills und Arbeitszeitregeln sind noch nicht kanonisch zugeordnet; bestehende Regeln lokal prüfen und ergänzen.",
            "API-Sichtbarkeit, Cache-Aktualität und Vollständigkeit einschließlich angrenzender Dienste lokal bestätigen; wiederholte Antworten ersetzen keine Quelltransaktion.",
            "Mitgliedschaften in den ausgewählten Gruppen wurden übernommen; Zuordnungen außerhalb dieser Auswahl gegebenenfalls ergänzen.",
        ]
    )
    snapshot.id = "sp5:api-import:" + str(uuid4())
    snapshot.revision = "1"
    return snapshot
