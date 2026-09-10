# Nachprüfbarer Prüfstand

Geprüft unter Linux x86_64, CPython 3.12.14, OR-Tools 9.15.6755. Ausschließlich neu erzeugte synthetische Eingaben. Keine Originalpersonalbestände oder unbekannten Testdaten wurden für diese Prüfungen verwendet.

## Automatisierte Prüfungen

```sh
python -m pytest -q
python tools/benchmark.py --employees 120 --days 31 --time-limit 45
```

Der Generator-Testlauf bestand mit 74 Tests. Abgedeckt sind unter anderem Freigaben, Qualifikation/RESTR, Betreuungskapazität, Teilplanung, harte Dienstartgrenzen versus Wünsche, Ruhegrenzen, rollierende und Kalenderwochenruhe, Randkontext, Profilwechsel, mehrteilige Dienste, Zeitumstellung, korrumpierte Ergebnisse und ein vollständig enumerierter kleiner Referenzfall. Jobtests prüfen Revisionen, Benutzerisolation, tatsächlichen Workerprozess, Abbruch, Wiederanlauf, konkurrierende idempotente Übernahme und Rückabwicklung bei injiziertem Auditfehler.

Der Adapter ist sowohl gegen neue synthetische Fassadenstrukturen als auch über frisch erzeugte minimale dBASE-Dateien mit `sp5lib`-Schreib-/Lesefunktionen geprüft. Die minimalen Testtabellen sind keine Behauptung vollständiger Originalformatparität. Ungeklärte Originalsemantik bleibt gesondert blockierend dokumentiert.

`tests/test_offline.py` installiert unter Linux einen seccomp-Filter, der Netzwerk-Systemaufrufe im Testprozess auf Kernel-Ebene mit EPERM abweist. Nach nachgewiesenem fehlgeschlagenem Socket-Aufruf funktionieren Demo, Berechnung, unabhängige Prüfung und CSV/XLSX-Export. Der Test verwendet keine externe Quelle und keinen externen Berechnungsdienst.

## Saubere Paketinstallation

Wheel und Quellarchiv wurden mit `python -m build` erzeugt. In einer frischen virtuellen Umgebung wurde ausschließlich das Kernwheel mit hinterlegten Abhängigkeiten installiert; `sp5lib` und `sp5api` waren nachweislich nicht importierbar. Aus einem Verzeichnis außerhalb des Checkouts wurden 14-Tage-Demo, Berechnung, unabhängige Validierung und XLSX-Export erfolgreich ausgeführt. Der optionale Library-Stand 1.32.3 ist separat über den Paketindex installierbar.

## Integration und Oberfläche

Elf neue API-Tests wurden isoliert von fremden Fixtures ausgeführt:

```sh
python -m pytest tests/generator --confcutdir=tests/generator -q
```

Sie prüfen unter anderem Rollen/Dienstschreibrecht, Read-only, Impersonation, Eigentümerisolation, Versionskonflikt und nachträglich widerrufene Sichtbarkeit.

Im Frontend wurden `npm run build`, gezielte Typ-/Lintprüfung und drei neue Komponententests erfolgreich ausgeführt. Chromium durchlief die tatsächlichen Generator-HTTP-Endpunkte mit separat laufendem Worker: Demo laden, speichern, berechnen, 56 Einteilungen unabhängig bestätigen, synthetisch übernehmen, fixieren und neu berechnen. Die Fixierung blieb erhalten. Desktop und 390-Pixel-Ansicht wurden visuell geöffnet; keine Browserfehler und kein horizontaler Seitenüberlauf. Externe Browserzugriffe waren gesperrt.

Diese Browserprüfung verwendete eine isolierte synthetische Testanmeldung und neutrale Antworten für übrige Anwendungsbereiche. Zusätzlich wurde der mitgelieferte separate Demo-Server einschließlich seines anonymen Loginformulars durch dieselbe Browserkette geprüft. Der reguläre Loginflow gegen Originaldaten, der vollständige Anwendungs-Lifecycle und native SP5-Schreibvorgänge sind damit nicht geprüft. Die ursprünglichen Schwesterprojekt-Testbestände wurden wegen nicht bestätigter Datenherkunft nicht pauschal ausgeführt. Die Library blieb unverändert.

Die eigenständige Weboberfläche wurde zusätzlich mit Chromium auf Desktop und 390-Pixel-Breite geprüft: Demo bearbeiten, speichern, berechnen, unabhängig prüfen, fixieren und neu berechnen; außerdem frisch synthetisiertes DBF-Stammverzeichnis prüfen, Team wählen, importieren, historischen Freigabevorschlag ausdrücklich bestätigen und speichern. Keine JavaScript-Fehler oder horizontalen Seitenüberläufe. Drei zusätzliche Webtests und vier Verzeichnisimporttests bestehen.

## Container und eigenständiges Paket

Version 0.1.1 wurde als Wheel und Quellarchiv gebaut und deren Dateiinhalte geprüft. Eine frische Wheel-Installation mit den Extras `web,sp5` startete die enthaltene Oberfläche und einen echten Worker außerhalb des Checkouts; die Demo ergab 56 vollständige, unabhängig gültige Einteilungen.

Der [Containerlauf für Commit 352b1b3](https://github.com/mschabhuettl/openschichtplaner5-generator/actions/runs/34527690138) hat das Linux-amd64-Image gebaut, die CLI-Berechnung und unabhängige Validierung mit `--network none` sowie den HTTP-Webstart erfolgreich geprüft. Das Image wird als herunterladbares Workflow-Artefakt mit Prüfsumme bereitgestellt, nicht in einer Containerregistry veröffentlicht.

## HTTP-Quelle

Zwei weitere synthetische Tests bestätigen die explizite Dev-Anbindung ohne Token-Datei und die Ablehnung einer API, die ihren Dev-Modus nicht bestätigt.

Die API-Anbindung ist gegen den Quellcode der bestehenden Leseendpunkte und synthetische HTTP-Antworten geprüft. Fünf Transporttests prüfen unter anderem Berechtigungsfehler, ausgeblendete Abwesenheiten, Quelländerungen, verweigerte Weiterleitungen und den Ausschluss von Zugangsdaten aus Snapshots. Ein zusätzlicher Webtest prüft die serverseitige Anbindung. Chromium durchlief außerdem einen echten lokalen HTTP-Testserver: API wählen, Team laden, importieren, historische Matrix anzeigen und speichern; Desktop und 390-Pixel-Ansicht ohne JavaScript-Fehler oder Seitenüberlauf. Keine produktive API wurde kontaktiert.

## Benchmark

Der synthetische Lauf mit 120 Personen über 31 Tage umfasst 62 Schichten,
124 Bedarfsgruppen und 1.240 zwingende Einteilungen. Auf Linux x86_64 mit
Intel Core i7-10700T und 12 sichtbaren logischen CPUs, CPython 3.12.14 und OR-Tools 9.15.6755 (vier Solverthreads)
ergab ein konfiguriertes Limit von 45 Sekunden:

- Laufzeit: 39,876 Sekunden
- Status: `FEASIBLE`; 1.240 Einteilungen, unabhängig gültig und vollständig
- Bewertungswert: 848.640; keine globale Schranke und kein Optimalitätsabstand verfügbar
- Ein allgemeiner konstruktiver Startplan wurde zuerst unabhängig geprüft und
  anschließend von CP-SAT mit fixierten Einteilungsvariablen bestätigt. Das
  eingeschränkte Zertifikat meldete `OPTIMAL`; dies ist ausdrücklich **kein**
  Optimalitätsbeweis für das freie Planungsproblem, dessen Ergebnis `FEASIBLE` bleibt.

Frühere Versuche ohne diesen Startplan fanden bei 30, 60 und 120 Sekunden noch
keine Lösung. Ein Zeitlimit ohne gefundene Lösung wurde korrekt als `UNKNOWN`
behandelt. Der Benchmark ist kein universelles Laufzeitversprechen.

## Tatsächliche Grenzen

- Lokal ist keine Containerlaufzeit verfügbar; die Containerprüfung erfolgt auf GitHub Actions.
- Native SP5-Gesamtübernahme nicht implementiert; Zusatzregeln und bestehende Writer haben noch keine gemeinsame Transaktionsgrenze.
- Bedarfskombinationen und Sonderwerte aus SP5 benötigen belegte fachliche Klärung. Ungeklärte Imports sind nicht freigabefähig.
- Erweiterte UI-Regeln teilweise als strukturierter JSON-Editor, Detailtexte derzeit deutsch.
- Keine vollständige Abnahme aller beschriebenen Integrationsanforderungen; Testerfolge ersetzen die ausdrücklich genannten fehlenden Funktionen nicht.

## Teamhierarchie

Fünf synthetische Hierarchietests und ein HTTP-Regressionstest prüfen `SUPERID`, verschachtelte Unterteams, Elternteams ohne direkte Mitglieder, Mehrfachmitgliedschaften, bedarfsspezifische Gruppenzuordnung, unvervielfachte Historie und fehlerhafte Zyklen. Chromium importierte über einen lokalen synthetischen HTTP-Server einen Elternknoten mit zwei Unterteam-Ebenen: eine Person mit zwei Mitgliedschaften erscheint einmal, ihre Teams sind sichtbar. Desktop und schmale Ansicht ohne JavaScript-Fehler oder Seitenüberlauf.

## Mehrfachauswahl und Tabellenoberfläche

Exakte Teamlisten, Legacy-Einzelauswahl und historische Funktionen ohne zusätzlichen Bedarf sind mit synthetischen Regressionen geprüft. Der automatisierte Chromium-Ablauf prüft ausgeblendete Unterteams, mehrfach zugeordnete Personen, historische Vorschläge, Achsentausch, Speichern, zeitlich begrenzte und betreute Freigaben, beide Monatsansichten sowie Fixierung und Neuberechnung mit echtem Worker. Die Prüfungen laufen vor der Image-Veröffentlichung im Container-Workflow. Anleitung: [Matrix und Monatsplan](matrix-and-monthly-plan.md).

## Dienstbezogene Matrix (0.3.0)

78 Python-Tests prüfen zusätzlich getrennte Dienst- und Arbeitsplatzidentitäten,
arbeitsplatzübergreifende Dienstfreigaben, fortgeltende Qualifikations- und
Betreuungspflichten sowie historische Einteilungen ohne Arbeitsplatzangabe.
Der Browserablauf prüft mehrere Dienste am selben Arbeitsplatz, Dienste ohne
Historie, Achsentausch, Dienst-Monatsansicht, Fehleranzeigen und doppelte Klicks.
Alle Referenzdaten sind neu erzeugt und synthetisch.
