# Version 0.7.0

Dieses Release liefert die eigenständige lokale Anwendung für Planung,
unabhängige Prüfung und Export. Die SP5-Anbindung liest Stammdaten und Historie;
sie schreibt keine originalen Dienstpläne zurück.

## Lieferumfang

- Stabiler CP-SAT-Betrieb mit einem Suchworker; der bei paralleler Suche reproduzierte native Absturz wird damit vermieden.
- Installierbares Python-Wheel und Quellarchiv einschließlich Weboberfläche.
- Linux-amd64-Container mit eingebautem Worker, persistentem Zustandsvolume und Healthcheck.
- CLI für Demo, JSON-Schemata, Berechnung, unabhängige Validierung und CSV/XLSX-Export; `sp5-generator --version` zeigt den installierten Stand.
- Weboberfläche mit Personenmatrix, Monatsplan, manueller Bearbeitung, Fixierungen und Export.
- Gespeicherte Aufträge und Ergebnisse lassen sich nach Neuladen oder Serverneustart wieder öffnen. Ein Auftrag behält seinen ursprünglichen Snapshot; veraltete Revisionen werden beim Start erkannt.
- Lesender Import aus SP5-Verzeichnis oder konfigurierter API, Teamhierarchie und ausdrücklich zu bestätigende historische Freigabevorschläge.

## Korrekturen und Bedienung

- Die Fairnessberechnung berücksichtigt Mehrfachbesetzung korrekt, damit ein
  besetzbarer Bedarf nicht allein wegen einer zu eng angesetzten Hilfsvariable
  als unlösbar erscheint.
- Solver und unabhängiger Validator behandeln Randkontext, Wochenenden,
  Nachtdienste und Zeitumstellungen konsistent. Ungültige lokale Uhrzeiten und
  nicht endliche Zeitlimits werden als Eingabefehler erkannt.
- Exporte prüfen die tatsächlichen Einteilungen erneut und berechnen offene
  Stellen aus dem Entwurf. Veraltete Status- oder Fehlstellenangaben werden
  dadurch nicht ungeprüft übernommen.
- Die Oberfläche bietet Auftragsverlauf, Wiederöffnung gespeicherter Ergebnisse
  und eine portable Projektsicherung. Ein Ergebnis wird mit dem Snapshot seines
  ursprünglichen Auftrags geöffnet. Beim Wechsel schützt eine Rückfrage noch
  nicht gespeicherte Änderungen.
- Der API-Import behandelt ungültige JSON-Antworten kontrolliert. Ungenutzte
  native Bedarfsfelder erzeugen keine erfundenen Zusatzbedarfe.

## Releaseprüfung

Vor Veröffentlichung eines Images führt der Workflow **Container** die Python-
und Browserprüfungen sowie eine saubere Paketinstallation aus. Die Paketprüfung
baut das Quellarchiv erneut, vergleicht enthaltene Anwendungsdateien und prüft
Versionskonsistenz. Sie installiert zuerst nur den Kern, anschließend die Web-
und SP5-Extras in eine neue virtuelle Umgebung und führt `pip check` aus.
Außerhalb des Checkouts werden CLI-Berechnung, Validierung, Exporte, HTTP-
Oberfläche, statische Ressourcen und ein echter Berechnungsworker geprüft.

Das Python-Artefakt enthält Wheel und Quellarchiv mit SHA-256-Prüfsummen; das Container-Artefakt enthält
das Image mit SHA-256-Prüfsumme. Artefakte werden 30 Tage aufbewahrt. Auf `main`
werden erst nach den Prüfungen die GHCR-Tags `0.7.0`, `latest` und
`sha-<Commit-ID>` veröffentlicht. Neue Läufe desselben Branches brechen ältere
Läufe ab. Ein erfolgreicher lokaler Test ist keine Bestätigung eines bereits
erfolgten Registry-Uploads; maßgeblich ist der erfolgreiche zugehörige Workflow.

Die vollständigen Befehle und Prüfumfänge stehen in [Prüfungen](verification.md).

## Aktualisieren

1. Anwendung geordnet stoppen. Bei persistentem Betrieb das gesamte
   Zustandsverzeichnis bzw. Zustandsvolume sichern, einschließlich vorhandener
   SQLite-Begleitdateien.
2. Neue Version installieren oder das getestete Image laden. Für nachvollziehbare
   Installationen den Commit-Tag oder Image-Digest festhalten; `latest` und
   Versions-Tags können bei späteren Builds ersetzt werden.
3. Mit demselben Zustandsverzeichnis starten, Versionsanzeige und `/healthz`
   prüfen und zunächst die synthetische Demo berechnen und validieren.
4. Gespeicherte Stände öffnen. Ein unterbrochener Auftrag muss ausdrücklich neu
   gestartet werden. Alte SP5-Snapshots mit arbeitsplatzbasierten statt
   dienstbasierten Freigaben erneut importieren und fachlich bestätigen.

Der temporäre Portainer-Stack verwirft seinen Zustand beim Neustart. Für
dauerhafte Entwürfe das persistente Compose-Volume verwenden.

## Unterstützter Umfang und Grenzen

- Referenzplattform: Linux, Python 3.12; das veröffentlichte Containerimage ist
  für `linux/amd64`. Native Windows-Unterstützung ist nicht vorhanden.
- Lokale Planungsinstanz mit optionalem gemeinsamem Passwort. Keine getrennten
  Benutzerkonten oder Mandanten; keine Freigabe als öffentlicher Mehrbenutzerdienst.
- Originale SP5-Gesamtübernahme ist weiterhin gesperrt. Ungeklärte importierte
  Semantik bleibt blockierend und muss anhand der Quelle geklärt werden.
- Ein bewiesener Regelverstoß, bewiesene Unlösbarkeit und ein Zeitlimit ohne
  Lösung bleiben unterschiedliche Ergebnisse. Kein allgemeines Laufzeit- oder
  Rechtskonformitätsversprechen.
- Einige erweiterte Regeln werden weiterhin im strukturierten JSON-Editor
  bearbeitet. Die optionale Schwesterprojekt-Integration hat einen separaten
  Abnahmeumfang und ist keine Voraussetzung für diese Anwendung.
