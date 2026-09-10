# Version 0.8.0

Diese Version überarbeitet den täglichen Planungsablauf: Projekte lassen sich
in der Anwendung anlegen, wieder öffnen und durch klar getrennte Arbeitsbereiche
bearbeiten. Größere Teams und Pläne werden mit begrenzter Darstellung geladen,
ohne Daten für Berechnung oder Export abzuschneiden.

## Projekte und Oberfläche

- Geführte Projektanlage mit Name, Zeitraum, Zeitzone, Personen, Funktionen und
  wiederkehrenden Schichten einschließlich Mindest- und Höchstbesetzung.
- Ausdrückliche Bestätigung der Regeln, Freigaben und des Randkontexts. Die
  Anlage eines Projekts bestätigt keine Qualifikation oder Verfügbarkeit stillschweigend.
- Projektübersicht und gespeicherte Berechnungen; die Bereiche Team, Regeln,
  Berechnung und Dienstplan sind über die Navigation erreichbar.
- Neue Gestaltung für Desktop und schmale Bildschirme, Statusanzeigen,
  leere Zustände und verständliche Prüfhinweise. Technische Detailberichte
  bleiben bei Bedarf zugänglich.
- Vollständige Projektsicherung und Wiederimport; Schutz vor unbeabsichtigtem
  Verwerfen ungespeicherter Änderungen.

## Leistung und Stabilität

Der Browser erzeugt Detailtabellen erst bei Bedarf. Monatspläne enthalten
höchstens 30 Zeilen pro Seite, die Liste der Einteilungen höchstens 40.
Personenauswahllisten entstehen beim tatsächlichen Bearbeiten einer Einteilung.
Suche und Freigabeänderungen müssen dafür nicht den gesamten Plan neu aufbauen.

Die Optimierung verwendet weiterhin einen CP-SAT-Suchworker. Ein in Version
0.7 reproduzierter nativer Absturz bei paralleler Suche wird damit vermieden.
Messwerte dieser Version unterscheiden Modellaufbau, ersten gültigen Plan und
gesamte Optimierungszeit. Ein früh gefundener gültiger Startplan und eine
Bestätigung unter fixierten Variablen beweisen keine globale Optimalität.

Im gemessenen synthetischen Fall mit 120 Personen, 31 Tagen und 1.240
Einteilungen lag nach 3,673 Sekunden ein unabhängig gültiger Plan vor. Der
gesamte Aufruf dauerte bei 10 Sekunden eingestelltem Budget 9,752 Sekunden;
die Vergleichsversion 0.7.0 benötigte 19,153 Sekunden. Beide Ergebnisse hatten
denselben Zielfunktionswert und den Status `FEASIBLE`. Gemessen wurde unter
Linux x86_64, Python 3.12.14 und OR-Tools 9.15.6755 mit einem Suchworker.

Die [Prüfdokumentation](verification.md) beschreibt den reproduzierbaren
120-Personen-/31-Tage-Fall und die getrennte Messung der Browserdarstellung.
Die Werte sind konkrete Messergebnisse, kein allgemeines Laufzeitversprechen.

## Excel-Ausgabe

Excel-Exporte öffnen mit Monatsplänen und enthalten zusätzlich eine numerische
Stundenübersicht, offene Stellen und sämtliche einzelnen Einteilungen.
Monatsübergreifende und nächtliche Dienste bleiben erkennbar. Fixierte
Überschriften, Druckeinstellungen und Schutz vor als Formeln interpretierten
Texten gehören zur Ausgabe. Der Export prüft die tatsächlichen Einteilungen
vor der Erstellung erneut.

## Lieferung und Aktualisierung

Das Python-Wheel und Quellarchiv enthalten sämtliche Webressourcen. Die
Paketprüfung vergleicht deren Inhalt und startet die installierte Anwendung
außerhalb des Checkouts einschließlich echtem Berechnungsworker. Der
Container-Workflow prüft Browser, Pakete und Offline-Berechnung vor der
Veröffentlichung von `0.8.0`, `latest` und `sha-<Commit-ID>` auf `main`.

1. Anwendung geordnet stoppen und das vollständige Zustandsverzeichnis oder
   Compose-Volume sichern.
2. Neues Image laden beziehungsweise Version 0.8.0 installieren und mit
   demselben Zustandsverzeichnis starten.
3. Versionsanzeige und `/healthz` prüfen und ein vorhandenes Projekt öffnen.
4. Zunächst einen synthetischen Plan berechnen, prüfen und exportieren.

Für nachvollziehbare Installationen den Image-Digest oder Commit-Tag notieren.
Ein Versions-Tag kann bei einem erneuten Build derselben Version ersetzt werden.
Die [Betriebsanleitung](web-operation.md) beschreibt Zugriffsschutz und Updates.

**Zurückwechseln auf 0.7.0:** Version 0.8.0 erweitert die SQLite-Datenbank um
zusätzliche Spalten. Ein älterer 0.7.0-Dienst kann diese aktualisierte Datenbank
nicht unverändert weiterverwenden. Für ein Zurückwechseln Anwendung stoppen,
die vollständige Sicherung von vor dem Update wiederherstellen und erst dann
das alte Image starten. Änderungen seit dieser Sicherung vorher als Projektdateien
sichern; sie sind in der alten Datenbanksicherung nicht enthalten.

## Unterstützter Umfang

- Eigenständige lokale Planung unter Linux mit Python 3.12; Container für
  `linux/amd64`. Native Windows-Ausführung ist nicht unterstützt.
- Eine lokale Planungsinstanz mit optionalem gemeinsamem Passwort; keine
  getrennten Benutzerkonten oder Mandanten.
- SP5-Import ist lesend. Native Rückübernahme in originale SP5-Dienstpläne
  ist weiterhin nicht implementiert.
- Vollständige und gekennzeichnete Teilpläne, unabhängige Prüfung und Export.
  Ein Zeitlimit ohne Lösung bleibt von bewiesener Unlösbarkeit unterscheidbar.
- Erweiterte Datenfelder können im strukturierten JSON-Editor bearbeitet werden.
  Regelprofile und ungeklärte Originalsemantik benötigen fachliche Bestätigung;
  technische Tests bestätigen keine Rechtskonformität eines frei gewählten Profils.
