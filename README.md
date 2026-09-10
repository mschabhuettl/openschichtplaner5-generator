# OpenSchichtplaner5 Generator

Branchenneutraler Dienstplangenerator mit lokaler mathematischer Optimierung, eigener Weboberfläche und CLI. Er erzeugt Dienstplanvorschläge, prüft sie unabhängig und exportiert sie als JSON, CSV oder Excel.

**Version 0.7.0:** eigenständig installierbare Anwendung für lokale Planung und Export. Unterstützter Betriebsweg ist Linux mit Python 3.12 oder das Linux-amd64-Containerimage. Regelprofile müssen zum jeweiligen Einsatz passen; die Anwendung garantiert keine Rechtskonformität. [Änderungen und Grenzen dieser Version](docs/release-0.7.0.md).

## Stand

Der allgemeine Python-Kern liest versionierte JSON-Snapshots, erzeugt vollständige oder ausdrücklich gekennzeichnete Teilpläne, prüft Regeln und exportiert JSON, CSV und XLSX. Konfigurierbar sind Funktionen, Arbeitsplätze, Freigaben, Qualifikationen, Verfügbarkeiten, wechselnde Wochenmodelle, Abwesenheiten, Fixierungen, Ruheprofile und Optimierungsgewichte. Eine eigene Weboberfläche mit Hintergrundworker ist enthalten; eine optionale Integration ergänzt die Generatoransicht im Schwesterprojekt.

**SP5 wird lesend angebunden.** Der Adapter bewahrt ungeklärte Originalsemantik als blockierende Diagnosen. Native Rückübernahme in originale SP5-Dienstpläne ist nicht implementiert. Die vollständige Schreibintegration ist nicht Bestandteil dieses Releases; der interne synthetische Übernahmetest ändert daran nichts.

## Erster Start

Nach dem Klonen bzw. Entpacken im Projektverzeichnis ausführen:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -c requirements-web.lock '.[web,sp5]'
python -m pip check
sp5-generator --version
sp5-generator serve --host 127.0.0.1 --port 8080 --state-dir ./generator-state
```

Im Browser `http://127.0.0.1:8080` öffnen. **Synthetische Demo laden**, **Speichern und berechnen**, anschließend **Entwurf prüfen** und **XLSX exportieren**. Dafür sind weder SP5-Bestand noch API oder Zugangsdaten erforderlich. Der Server startet den Berechnungsworker automatisch. Gespeicherte Stände und Aufträge liegen im Zustandsverzeichnis und können nach einem Neustart wieder geöffnet werden.

Alternativ das Wheel aus dem Workflow-Artefakt `openschichtplaner5-generator-python` installieren:

```sh
python -m pip install './openschichtplaner5_generator-0.7.0-py3-none-any.whl[web,sp5]'
sp5-generator serve --host 127.0.0.1 --port 8080 --state-dir ./generator-state
```

Das Extra `web` ergänzt die Oberfläche, `sp5` den DBF-Adapter. Für reine JSON-Planung über die CLI genügt die Installation ohne Extras. Native Windows-Ausführung wird nicht unterstützt; Worker und Dateisperren benötigen POSIX-Funktionen.

## Webbetrieb und Updates

Die Weboberfläche enthält eine Dienstmatrix, Monatsansichten und vollständige Ruheprofil-Formulare. Optionaler Passwortschutz, Docker-Healthcheck und versionierte Images unterstützen den lokalen Betrieb. Siehe [Betriebsanleitung](docs/web-operation.md).

## Eigenständig starten

Python 3.12 unter Linux ist der geprüfte Referenzbetrieb. Die Engine benötigt weder ein SP5-System noch einen laufenden Webserver.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -c requirements.lock .
sp5-generator demo -o /tmp/example.json
sp5-generator solve /tmp/example.json --time-limit 30 -o /tmp/result.json
sp5-generator validate /tmp/example.json /tmp/result.json
sp5-generator export /tmp/example.json /tmp/result.json /tmp/result.xlsx
sp5-generator export /tmp/example.json /tmp/result.json /tmp/result.csv
```

Die Demo ist vollständig neu konstruiert und ausschließlich synthetisch. Sie nutzt UTC, Testperson 001 usw., zwei Funktionen, verschiedene Beschäftigungsausmaße, Tag/Nacht, ein befristetes kurzes Verfügbarkeitsfenster, wechselnde Wochen, eine Abwesenheit und eine Fixierung. Kontext außerhalb des Beispiels ist ausdrücklich dienstfrei.

```sh
sp5-generator demo --impossible -o /tmp/impossible.json
sp5-generator solve /tmp/impossible.json -o /tmp/impossible-result.json
sp5-generator solve /tmp/impossible.json --partial -o /tmp/partial-result.json
sp5-generator schema input -o /tmp/input.schema.json
sp5-generator schema result -o /tmp/result.schema.json
```

Exitcodes: `0` vollständiger geprüfter Plan/erfolgreicher Export; `2` ungültige Eingabe oder Modell; `3` Teilplan bzw. unvollständige/fehlgeschlagene Prüfung; `4` bewiesen unlösbar; `5` noch keine Lösung. `FEASIBLE` bedeutet nicht bewiesene Optimalität. Der konkrete Solverstatus steht immer im Ergebnis. Verarbeitungsfehler sind JSON auf stderr; fehlerhafte Kommandozeilenargumente zeigt argparse mit Nutzungshinweis an.

## Eigenständige Weboberfläche

```sh
python -m pip install '.[web,sp5]'
sp5-generator serve --host 127.0.0.1 --port 8080 --state-dir ./generator-state
```

Browser: `http://127.0.0.1:8080`. Kein separates Frontend oder SP5-API-Projekt nötig.
SP5-Stammverzeichnis oder konfigurierte SP5-API laden, Teams im Auswahlbaum an-/abwählen und den Zeitraum festlegen und aus bisherigen Einteilungen
unbestätigte Matrixvorschläge erzeugen. Freigaben, Verfügbarkeiten, Profile und
Dienstarten bleiben bearbeitbar; Historie ersetzt keine Qualifikationsnachweise.
Originaldateien werden nur gelesen. Die Excel-artige Personen-/Funktionsmatrix lässt sich transponieren; Ergebnisse erscheinen als Monatsplan nach Personen oder Funktionen. [Matrix und Monatsplan](docs/matrix-and-monthly-plan.md), [Bedienung und Import](docs/standalone-web.md).

## Docker

```sh
docker compose pull
docker compose up -d
```

Die Weboberfläche ist über `http://127.0.0.1:8080` erreichbar. Ein SP5-Verzeichnis
wird ausdrücklich schreibgeschützt nach `/source` eingebunden, nicht ins Image
kopiert. [Start mit Quellverzeichnis, Download und Laden des Images](docs/container.md).
Der Workflow **Container** baut und prüft das Image auf `main` und veröffentlicht
`ghcr.io/mschabhuettl/openschichtplaner5-generator:latest`. Compose verwendet dieses
Image ohne lokalen Build. [API-Anbindung und lokaler Datentest](docs/api-source.md).

## Optionale Integration

Die Integration benötigt die Änderungen der entsprechenden Featurebranches von `openschichtplaner5-api` und `openschichtplaner5`. Installation aus drei benachbarten Checkouts:

```sh
python -m pip install ./openschichtplaner5-generator ./openschichtplaner5-api
```

Für den lesenden SP5-Adapter zusätzlich `python -m pip install './openschichtplaner5-generator[sp5]'`. Details zu expliziter Aktivierung, separatem Worker, Zustandsverzeichnis und synthetischer Testübernahme stehen in [Betrieb](docs/operations.md). Eine vollständig synthetische Webdemo ohne Originalbestand startet mit `python -m sp5api.generator_demo --state-dir /tmp/sp5-generator-demo --port 8000`; anschließend im Frontend `npm ci` und `npm run dev -- --host 127.0.0.1`. Der Demo-Server startet seinen Worker selbst und verwendet eine ausdrücklich anonyme Testanmeldung. Produktionsbereitstellung gehört nicht zu diesem Startweg.

## Dokumentation und Prüfung

- [Architektur und Integration](docs/architecture.md)
- [Regeln, Zeitberechnung und Zielfunktion](docs/rules.md)
- [SP5-Zuordnung und offene Semantik](docs/sp5-mapping.md)
- [Jobs, Datenhaltung und Übernahme](docs/operations.md)
- [Bedienung](docs/usage.md)
- [Prüfungen und Benchmark](docs/verification.md)
- [Release 0.7.0 und Aktualisierung](docs/release-0.7.0.md)

```sh
python -m pip install -c requirements-web.lock '.[dev,web,sp5]'
python -m pip check
python -m pytest -q
python -m build
python tools/check_distribution.py
```
