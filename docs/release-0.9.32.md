# Version 0.9.32 – abgesicherte Teilplanung und strengere Importdiagnose

Diese gebündelte Freigabe baut auf 0.9.31 auf. Sie verändert keine
Benutzerinstallation automatisch und führt keine neuen fachlichen Regeln ein.

## Teilplanung unter Zeitbudget

- Offene Besetzungen werden exakt gezählt, auch bei FEASIBLE-Ergebnissen.
  Offene Bedarfszeilen sind nicht dasselbe wie fehlende Besetzungen.
- Ein gespeicherter Teilplan kann als Rückfalllösung dienen, wenn er erneut
  unabhängig validiert und im vollständigen Modell zertifiziert wurde.
  Gespeicherte Einteilungen werden dadurch nicht zu festen Vorgaben.
- Die Abdeckungssuche reserviert ein Fünftel ihres verbleibenden Zeitbudgets
  für Qualität. Diese zweite Phase hält die erreichte Zahl offener Stellen
  fest und optimiert die vorhandenen gewichteten Ziele mit nativer OR-Tools-
  Nachbarschaftssuche und einem Worker. Harte Regeln bleiben erhalten.
- Wird eine neue Lösung nicht akzeptiert oder läuft die Suche aus, bleibt
  die zertifizierte Rückfalllösung erhalten. Ohne Nachweis optimaler Abdeckung
  wird keine globale Optimalität behauptet. FEASIBLE ist weder Vollständigkeit
  noch ein Beweis maximaler Freizeit.
- Die Ergebnisparameter enthalten phasenbezogene Such- und Validierungsnachweise.

## Import und Regelabgleich

- Ungültige Bedarfszahlen, Wochentage, zeitliche Quellen und widersprüchliche
  Personen-/Mitgliedschaftsbezüge werden vor stiller Filterung oder Zuordnung
  diagnostiziert. Fehlerantworten werden ohne private Quellinhalte erklärt.
- Einschränkungsreferenzen werden von tatsächlich nicht erzeugbaren Diensten
  unterschieden. Explizite Sonderdienstintervalle bleiben im Randkontext erhalten;
  über Mitternacht reichender Kontext geht nicht durch eine verkürzte Abdeckung
  verloren.
- Datierte Kalenderwochenruhe wurde an den unabhängigen Validator angeglichen.
  Codepfade, Gegenbeispiele und Regressionen stehen in
  [source-semantics.md](source-semantics.md).

## Belegter Stand und verbleibende Grenzen

Der Runtime-Stand `bdf505a` bestand 1288 Python-Tests und die
[Feature-CI einschließlich Browser, Paket und Docker](https://github.com/mschabhuettl/openschichtplaner5-generator/actions/runs/34657786525).
Ein kontrollierter privater 600-Sekunden-Vergleich zeigte bei gleicher Zahl
offener Stellen geringere gewichtete Qualitätskosten mit der nativen Suche.
Das ist ein einzelner Vergleich, keine allgemeine Leistungs- oder Optimalitätsgarantie.

Der private Docker-Test des Runtime-Stands erzeugte einen unabhängig gültigen,
aber unvollständigen Teilplan aus einer bereits eingerichteten Testkopie.
Frische Ist-/Soll-Importe blieben dagegen MODEL_INVALID: ungeklärte Zeiten,
Sonderdienste und Einrichtung sind weiterhin echte Blocker. Der Randkontext
ist nicht vollständig; daraus folgt keine vollständige Dienstplanfreigabe.
Diese Nachweise sind noch keine Abnahme eines veröffentlichten 0.9.32-Images.

Sollstunden sind keine harten Wochenhöchststunden. 11 Stunden tägliche und
36 Stunden Kalenderwochenruhe erfinden weder ein Wochenmaximum noch ein
pauschales 24-Stunden-Verbot. Es besteht keine neue Pflicht, alle Personen
einzuplanen. Persönliche Freigaben werden nicht aus Historie automatisch erteilt.
Der exakte Eingangs-/Ergebnisstand des originalen 0.9.29-Laufs fehlt weiterhin.

Der Release-Commit benötigt eigene Paket-, Browser- und Container-Gates sowie
die private lesende Abnahme des veröffentlichten Images. Veröffentlichungsstatus
und Downloads sind auf der GitHub-Release-Seite maßgeblich, nicht diese Notiz.
