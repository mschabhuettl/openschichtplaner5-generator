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

## Lokaler Prüfstand für 0.8.0

Der lokale Python-Prüfumfang umfasst 287 Tests. Den vollständigen erfolgreichen
Lauf für den veröffentlichten Commit dokumentiert der zugehörige GitHub-Workflow.

Der vollständige Browserlauf bestand unter Linux x86_64 mit Chromium
152.0.7977.0 auf Desktop und bei 390 Pixel Breite. Neben den bisherigen
Regressionen wurden Projektanlage, ein abgewiesener Erstellungsversuch mit
erhaltenen Eingaben und anschließendem erfolgreichen Wiederholen, Änderung
einer Person, eine Abwesenheit in Europe/Vienna, persistente Freigaben und die
nachträgliche Bestätigung des Randkontexts geprüft. Nach Neuladen wurde das
Projekt berechnet und als Excel-Datei heruntergeladen. Escape schloss den
Assistenten und stellte den Fokus wieder her. Der abschließende Browserlauf
prüft auch das Anlegen und persistente Speichern einer zusätzlichen Person,
deren ausdrückliches Entfernen sowie das Erreichen eines Projekts jenseits der
ersten API-Listenseite bei 1.001 synthetischen Projektzusammenfassungen.

Für die Darstellungsmessung wurde der tatsächlich unabhängig gültige
Benchmarkplan mit 120 Personen, 31 Tagen und 1.240 Einteilungen geladen. Die
Messungen umfassen Browseraktionen und zwei Darstellungszyklen; die Suche
enthält ihre bewusste Eingabeverzögerung.

| Browseraktion | Gemessene Dauer |
| --- | ---: |
| Projektdatei öffnen einschließlich HTTP-Vorprüfung | 326 ms |
| Eine Matrixfreigabe ändern | 68 ms |
| Person suchen einschließlich Eingabeverzögerung | 233 ms |
| Monatsansicht öffnen | 94 ms |
| Nächste Seite mit 30 Personen anzeigen | 160 ms |
| Bearbeitungsliste mit 40 Einteilungen öffnen | 60 ms |

Danach enthielt das Dokument 3.422 DOM-Elemente. Es wurden noch keine
Personenauswahllisten für die 1.240 Einteilungen erzeugt. Alle Daten bleiben
im Projekt; die Seitengröße begrenzt ausschließlich die Darstellung. Diese
lokalen Einzelmessungen sind keine Lastprüfung mit vielen gleichzeitigen
Benutzern und keine Zusicherung für jedes Endgerät.

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

## Browserablauf und Darstellungsleistung für 0.8.0

Die Browserprüfung navigiert durch die tatsächlichen Arbeitsbereiche. Sie prüft
zusätzlich die Projektanlage ohne SP5 oder JSON, das Speichern einer geänderten
Freigabe, Neuladen und Wiederöffnen, Berechnung und Excel-Download. Escape
schließt den Projektassistenten und gibt den Fokus an den Auslöser zurück.

Ein separater Darstellungsfall lädt 120 Personen, 31 Tage und 1.240 Einteilungen.
Die Prüfung misst Import, Freigabeänderung, Suche, Monatsansicht, Seitenwechsel
und das Öffnen der Einteilungsliste; außerdem zählt sie DOM-Elemente. Ein
synthetischer Darstellungsfall ist kein Solver-Benchmark. Optional kann das
unabhängig gültige Ergebnis eines tatsächlichen Benchmarks verwendet werden:

```sh
WEB_TEST_PERFORMANCE_INPUT=/tmp/large-snapshot.json \
WEB_TEST_PERFORMANCE_RESULT=/tmp/large-result.json \
WEB_TEST_SCREENSHOT_DIR=/tmp/browser-results \
npm test --prefix tests/browser
```

Das Screenshot-Verzeichnis muss vorhanden sein. Die tatsächlichen Werte werden
im Konsolenprotokoll und dort als `ui-performance.json` gespeichert. Der Lauf
prüft 30 Monatszeilen und 40 bearbeitbare Einteilungen pro Seite, ohne für jede
Einteilung sofort eine vollständige Personenauswahl zu erzeugen. Eine großzügige
10-Sekunden-Grenze erkennt grobe Blockaden auch auf langsameren Testrechnern;
sie ist kein Zielwert für die normale Bedienung.

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

1. Wheel-Metadaten, Versionsnummer und sämtliche enthaltenen Webressourcen prüfen.
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

## Vergleichbarer Solverlauf für 0.8.0

Im selben synthetischen Fall mit 120 Personen, 31 Tagen und 1.240 zwingenden
Einteilungen wurden Version 0.7.0 und der abschließende Stand von 0.8.0 mit
jeweils 10 Sekunden eingestelltem Budget ausgeführt. Beide lieferten eine
unabhängig gültige, vollständige `FEASIBLE`-Lösung mit Zielfunktionswert 848.640.

| Messwert | 0.7.0 | 0.8.0 |
| --- | ---: | ---: |
| Tatsächliche Gesamtdauer des Aufrufs | 19,153 s | 9,752 s |
| Erster unabhängig gültiger Plan | nicht erfasst | 3,673 s |
| Globale untere Schranke | nicht verfügbar | 573.900 |

Umgebung: Linux x86_64, Python 3.12.14, OR-Tools 9.15.6755, neun sichtbare
logische CPUs, ein Suchworker und Seed 0. Der abschließende Lauf enthält
1,032 Sekunden Modellaufbau und 0,152 Sekunden unabhängige Ergebnisprüfung.
Er umfasst 26.941 Modellvariablen und 36.767 Bedingungen. `FEASIBLE` und die
vorhandene Schranke belegen weiterhin keine globale Optimalität.

Die frühere Überschreitung des eingestellten Budgets wurde insbesondere durch
die zusätzliche Vorverarbeitung des Optimierungsmodells verursacht. Der
abschließende Suchpfad vermeidet diese zusätzliche Runde, wenn bereits ein
unabhängig geprüfter und unter Fixierungen bestätigter Startplan vorliegt.
Ein eingestelltes Solverbudget ist dennoch keine harte Frist für den gesamten
Prozess: Eingabeprüfung, Modellaufbau, native Aufrufe und abschließende Prüfung
benötigen ebenfalls Zeit.

## Nicht durch diese Prüfungen zugesichert

- Fachliche Richtigkeit ungeklärter importierter Originalsemantik.
- Native transaktionale Rückübernahme in originale SP5-Dienstpläne.
- Rechtskonformität eines frei konfigurierten Regelprofils.
- Öffentlicher Mehrbenutzerbetrieb oder native Windows-Unterstützung.
- Vollständige Abnahme des getrennten Schwesterprojekt-Frontends und dessen
  regulären Anmeldeablaufs gegen Originaldaten.

Siehe [Release 0.8.0](release-0.8.0.md) für Lieferumfang und Aktualisierung.


## Dauerhafte Release-Dateien

Der Workflow **Verified release assets** übernimmt die bereits geprüften Dateien
unverändert; er baut weder Wheel noch Container neu. Er läuft bei veröffentlichten
Releases oder manuell mit einem vorhandenen Tag. Die manuelle Ausführung prüft
standardmäßig nur; `publish=true` aktiviert die Veröffentlichung.

Die Herkunft wird über die GitHub-API aufgelöst: existierender veröffentlichter
Release, dessen exakter Git-Commit und ein vollständig erfolgreicher Push-Lauf
von `container.yml` auf `main` im eigenen Repository. Fehlende oder abgelaufene
Artefakte führen zum Abbruch; es gibt keinen Rückfall auf `latest`, einen anderen
Commit oder einen Neubau. Die Quell-CI wird im Workflow-Bericht verlinkt.

GitHubs [Download-Action](https://github.com/actions/download-artifact/tree/v4)
lädt die beiden benannten Artefakte dieses Laufs. Vor dem Upload prüft
`tools/prepare_release_assets.py` die exakte Dateiliste, zur Tagversion passende
Paketnamen und alle SHA-256-Prüfsummen. Zusätzliche Dateien, symbolische Links,
unvollständige oder widersprüchliche Manifeste werden abgewiesen. Erst danach
werden Wheel, Quellarchiv, Dockerarchiv und eine gemeinsame `SHA256SUMS` bereitgestellt.

Der Upload verwendet [GitHub CLI](https://cli.github.com/manual/gh_release_upload)
ohne `--clobber`: Bereits vorhandene Release-Dateien werden nicht gelöscht oder
ersetzt. Bei einem bereits teilweise erfolgten Upload ist eine gezielte Prüfung
nötig; ein Wiederholungslauf überschreibt die vorhandenen Dateien nicht. Nach dem
Upload lädt der Workflow die veröffentlichten Dateien erneut und prüft das
Manifest gegen die lokale Fassung sowie alle Dateiprüfsummen. Ein Erfolg darf
erst nach diesem Rücklesen gemeldet werden.

Die Herkunftsauswahl wird mit `node --test tests/release_source.test.cjs` geprüft;
die Dateigrenzen mit `pytest tests/test_release_assets.py`. Diese synthetischen
Tests ersetzen nicht den echten Download-/Upload-/Rückprüfungsablauf in GitHub.
