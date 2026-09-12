# Arbeitsanweisungen für dieses Repository

Gilt für jede Änderung, für Tests und für jede
Veröffentlichung.

## Befehle

```
uv venv --python 3.12 .venv                                  # CI nutzt Python 3.12
uv pip install --python .venv/bin/python -c requirements-web.lock '.[dev,web,sp5]'
uv pip install --python .venv/bin/python -e . --no-deps      # sonst testet man das installierte Paket
.venv/bin/python -m pytest -q                                # Domänen- und Quelltests
.venv/bin/python -m ruff check .                             # Lint
node --test tests/release_source.test.cjs                    # Release-Provenienz
cd tests/browser && npm ci && WEB_TEST_CHROMIUM=/usr/bin/google-chrome \
  WEB_TEST_PYTHON=../../.venv/bin/python node check.cjs      # Browserablauf
```

`npx playwright install` schlägt auf dieser Ubuntu-Version fehl; `WEB_TEST_CHROMIUM`
auf das vorhandene Chrome zeigen lassen. `WEB_TEST_PORT` setzen, wenn 8765 belegt ist.

## Datenschutz (verbindlich)

- NIEMALS echte Personal-, Beschäftigungs-, Dienstplan- oder Abwesenheitsdaten,
  private API-Antworten, Projektsicherungen, Zugangsdaten oder daraus erzeugte
  Darstellungen veröffentlichen — weder in Dateien noch in der Git-Historie, in
  Branches, PRs, Issues, Kommentaren, CI-Logs, Artefakten, Caches, Releases,
  Paketen, Docker-Layern oder bei externen Diensten.
- Ein privates Repository ist kein erlaubter Speicherort für Echtdaten.
- Echtdaten liegen ausschließlich unter `~/.sp5-private/` (0700), außerhalb jedes
  Worktrees und Build-Kontexts. API-Zugriffe nur lesend; die Benutzerinstallation
  wird nie verändert.
- Keine Echtdaten an Plugins oder externe Dienste weiterreichen. Weitergegeben
  werden ausschließlich Code und synthetische Reproduktionen.
- Fixtures, Screenshots und Beispieldaten im Repository sind vollständig
  synthetisch. Namen zu entfernen genügt nicht.
- Vor jedem Push und jeder Veröffentlichung:
  `.venv/bin/python tools/privacy_scan.py --range origin/main..HEAD --paths dist`
  (optional `--names ~/.sp5-private/names.txt`). Treffer nie im Klartext ausgeben.
- Berichtet werden nur nicht-identifizierende Aggregate. Eine vollständige
  Datenschutzprüfung nie behaupten, wenn nur ein Teil geprüft wurde.

## Fachliche Leitplanken

- Persönliche Dienstfreigaben sind maßgeblich; Qualifikationen bleiben separat.
- 11 Stunden Ruhe zwischen Dienstende und nächstem Dienstbeginn, insbesondere
  Nacht → Tag. 36 Stunden zusammenhängende Wochenruhe.
- Vertragswochenstunden, Periodensoll und harte Höchstgrenzen sind drei getrennte
  Größen. Keine pauschale Monatsdivision, keine erfundene Obergrenze.
- Teilpläne lockern harte Regeln nicht.
- Keine Bedarfe, Freigaben oder fehlenden Quellwerte erfinden.
- Sichtbare Datumsangaben TT.MM.JJJJ; gespeicherte und verglichene Werte bleiben ISO.
