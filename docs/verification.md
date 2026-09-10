# Prüfungen und Freigabeumfang

Die Releaseprüfung verwendet ausschließlich neu erzeugte synthetische Daten.
Referenzplattform ist Linux x86_64 mit Python 3.12 und den Paketständen in
`requirements.lock` bzw. `requirements-web.lock`. Native SP5-Rückübernahme und
produktive Personalbestände gehören nicht zu dieser Prüfung.

## Reproduzierbarer Prüflauf

Im Checkout:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -c requirements-web.lock '.[dev,web,sp5]'
python -m pip check
python -m pytest -q
python -m build
python tools/check_distribution.py
```

Für den Browserablauf zusätzlich:

```sh
npm ci --prefix tests/browser
cd tests/browser
npx playwright install --with-deps chromium
cd ../..
npm test --prefix tests/browser
```

Der Workflow **Container** führt diese Prüfungen vor dem Image-Build aus.
Prüfergebnis, Commit und tatsächliche Testanzahl stehen im jeweiligen
[Workflow-Lauf](https://github.com/mschabhuettl/openschichtplaner5-generator/actions/workflows/container.yml).
Die Befehle hier beschreiben den Prüfweg; sie behaupten keinen erfolgreichen
Lauf für einen beliebigen späteren Commit.

## Lokaler Prüfstand für 0.7.0

Vor dem Release-Push wurden unter Linux x86_64 mit Python 3.12.14 und OR-Tools
9.15.6755 insgesamt **213 Python-Tests** erfolgreich ausgeführt. Zwei Warnungen
betreffen veraltete Aufrufe einer Abhängigkeit. Ruff über Anwendung, Tools und
Tests sowie `git diff --check` waren ohne Befund. Die saubere Paketprüfung
einschließlich installiertem Webserver und echtem Worker bestand mit lokal
zwischengespeicherten Paketarchiven ohne Zugriff auf einen Paketindex.

Die vollständige lokale Browserprüfung bestand mit Chromium 152 auf Desktop
und bei 390 Pixel Breite. Sie umfasst Berechnung und Neuberechnung, gespeicherte
Ergebnisse, Projektsicherung und Wiederimport, ungültige Dateien und Zeitzonen,
gleichzeitige Bedienaktionen, unterbrochene Listenabfragen, Fixierungsschutz
bei Prüfung und Export sowie die UUID-Erzeugung ohne `crypto.randomUUID`,
wie sie für unverschlüsselten HTTP-Zugriff im LAN benötigt wird.

Bei der Prüfung wurde ein nativer Absturz von OR-Tools 9.15.6755 mit vier
CP-SAT-Suchworkern reproduziert, auch mit dem exportierten Modell ohne
Anwendungscode. Der Release verwendet deshalb einen Suchworker. Zehn frische
Anwendungsprozesse und vier reine Modellwiederholungen bestanden mit dieser
Einstellung. Drei Prozessregressionen mit der vollständigen 14-Tage-Demo sind
Bestandteil des Testlaufs; Regeln und Zielfunktion bleiben identisch.

Diese lokalen Ergebnisse ersetzen den Container- und Browserlauf des
zugehörigen GitHub-Workflows nicht. Der Workflow prüft den tatsächlich gepushten
Commit erneut, bevor er dessen Image veröffentlicht.

## Fachlicher Kern und Adapter

Python-Tests prüfen unter anderem Freigaben, Qualifikationen,
Betreuungskapazität, Teilplanung, harte Dienstartgrenzen, Wünsche,
Ruhegrenzen, rollierende und Kalenderwochenruhe, Randkontext, Profilwechsel,
mehrteilige Dienste, Zeitumstellung und korrumpierte Ergebnisse. Kleine
Referenzfälle prüfen die Lösung gegen unabhängig bestimmte Erwartungen.

Adapterprüfungen verwenden synthetische Fassadenstrukturen, frisch erzeugte
minimale dBASE-Dateien sowie lokale synthetische HTTP-Antworten. Sie prüfen
Teamhierarchie, Mehrfachmitgliedschaften, historische Matrixvorschläge,
Freigaben, getrennte Dienst- und Arbeitsplatzidentitäten, Quelländerungen,
Weiterleitungen und den Ausschluss von Zugangsdaten aus Snapshots. Sie belegen
keine vollständige Parität aller historischen SP5-Datenformate.

Jobtests prüfen Revisionen, Isolation, echte Workerprozesse, Abbruch,
Wiederanlauf, gespeicherte Ergebnisse und die synthetische Testübernahme.
Webtests prüfen HTTP-Grenzen, Anmeldung, Sitzungen, Entwurfsbearbeitung und
Export. Die Browserprüfung verwendet die enthaltene Oberfläche und echte
HTTP-Endpunkte mit einem separaten Worker und synthetischen Quellen.

## Saubere Paketinstallation

`tools/check_distribution.py` arbeitet in einem temporären Verzeichnis
außerhalb des Checkouts. Der Ablauf:

1. Wheel-Metadaten, Versionsnummer und alle drei enthaltenen Webressourcen prüfen.
2. Quellarchiv in einer isolierten Buildumgebung erneut zum Wheel bauen und die
   enthaltenen Anwendungsdateien mit dem ursprünglichen Wheel vergleichen.
3. Kernwheel in eine neue virtuelle Umgebung mit den Kernconstraints
   installieren und `pip check` ausführen. SP5-Library und FastAPI dürfen hier
   nicht importierbar sein.
4. Versionsanzeige, synthetische Zweitagesdemo, Berechnung, unabhängige
   Validierung, CSV/XLSX-Export und beide JSON-Schemata außerhalb des Checkouts ausführen.
5. Web- und SP5-Extras mit den Webconstraints ergänzen und erneut `pip check`
   ausführen. Den installierten HTTP-Server einschließlich echtem Worker starten,
   Healthcheck und statische Ressourcen laden, einen Snapshot speichern,
   berechnen, unabhängig prüfen und alle drei Exportformate abrufen.

Die Installation benötigt den Paketindex oder einen entsprechend gefüllten
lokalen Cache. Die eigentlichen Berechnungen benötigen keine externe Quelle.
Die Paketprüfung übernimmt keine konfigurierten SP5-Adressen oder Zugangsdaten
aus der aufrufenden Umgebung. Sie verwendet nur eine lokale HTTP-Verbindung
zur gerade gestarteten Testanwendung.

## Container und Betrieb ohne Netzwerk

Nach der Paket- und Browserprüfung baut CI das Linux-amd64-Image. Im Container
laufen Demo, Berechnung und unabhängige Validierung mit `--network none`.
Ein separater HTTP-Start prüft die Oberfläche. Anschließend veröffentlicht der
Workflow auf `main` die getesteten GHCR-Tags und stellt das Image samt Prüfsumme
als Workflow-Artefakt bereit. Die lokale Entwicklungsumgebung benötigt dafür
keine Dockerlaufzeit; ein GitHub-Workflow muss diesen Teil erfolgreich abschließen.

`tests/test_offline.py` installiert unter Linux einen seccomp-Filter, der
Netzwerk-Systemaufrufe im Testprozess mit EPERM abweist. Nach dem belegten
fehlgeschlagenen Socket-Aufruf laufen Demo, Berechnung, unabhängige Prüfung und
CSV/XLSX-Export. Fehlt libseccomp, wird dieser Test ausdrücklich übersprungen;
die CI-Containerprüfung ohne Netzwerk bleibt davon getrennt.

## Benchmark

```sh
python tools/benchmark.py --employees 120 --days 31 --time-limit 45
```

Dieser synthetische Fall umfasst 62 Schichten, 124 Bedarfsgruppen und 1.240
zwingende Einteilungen. Das Tool gibt den tatsächlich erreichten Solverstatus,
Laufzeit und die unabhängige Validierung aus. Ein Zeitlimit ohne Lösung ist
`UNKNOWN`, keine bewiesene Unlösbarkeit. Ein konstruktiver Startplan und seine
Bestätigung unter fixierten Variablen beweisen keine globale Optimalität des
freien Problems. Der Benchmark ist kein universelles Laufzeitversprechen.

Der lokale Lauf für 0.7.0 fand bei 45 Sekunden Limit nach **34,969 Sekunden**
eine `FEASIBLE`-Lösung mit 1.240 Einteilungen, unabhängig gültig und vollständig.
Der Zielfunktionswert war 848.640; eine globale Schranke war nicht verfügbar.
Umgebung: Linux x86_64, Python 3.12.14, OR-Tools 9.15.6755, neun sichtbare logische
CPUs, ein Solverworker, Seed 0. Die zusätzliche Bestätigung des konstruktiven
Startplans meldete unter fixierten Einteilungen `OPTIMAL`; dies ist kein
Optimalitätsbeweis für das freie Planungsproblem.

## Nicht durch diese Prüfungen zugesichert

- Fachliche Richtigkeit ungeklärter importierter Originalsemantik.
- Native transaktionale Rückübernahme in originale SP5-Dienstpläne.
- Rechtskonformität eines frei konfigurierten Regelprofils.
- Öffentlicher Mehrbenutzerbetrieb oder native Windows-Unterstützung.
- Vollständige Abnahme des getrennten Schwesterprojekt-Frontends und dessen
  regulären Anmeldeablaufs gegen Originaldaten.

Siehe [Release 0.7.0](release-0.7.0.md) für Lieferumfang und Aktualisierung.
