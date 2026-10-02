# Version 0.31.1 – Vier Arbeitsbereiche, ein gemeinsamer Plan

Diese Hinweise beschreiben UX-02B gegenüber 0.30.0. Den tatsächlichen
Veröffentlichungsstand belegen GitHub-Release und CI des exakten Commits,
nicht dieses Dokument. Version 0.31.1 ergänzt den noch nicht als Release
veröffentlichten 0.31.0-Stand um die folgenden Bedienkorrekturen: lesbare
Navigationszustände und ausreichend hohe Hauptbedienfelder.

## Änderungen

- **Vier statt sechs Hauptbereiche:** Projekte, Plan, Team und Einrichtung.
  Unter Einrichtung sind Dienste & Bedarf sowie Regeln & Projektdaten lokal
  erreichbar. Die bisherigen Fach- und JSON-Editoren bleiben erhalten.
- **Berechnen und Ergebnis zusammen:** Speichern und berechnen, Fortschritt,
  Abbrechen, Kalender und Export liegen im Plan. Rechenoptionen und ausführliche
  Eingabeprüfung sind aufklappbar; technische Kennzahlen bleiben sekundär.
  Eingabeprüfung, Planvalidierung und Speicherstand bleiben getrennte Aussagen.
- **Korrektur am richtigen Ort:** Bedarfsverweise aus Diagnose, Importhinweisen
  und Kalender öffnen den passenden lokalen Editor und fokussieren dessen
  Suchfeld außerhalb des fixierten Kopfbereichs. Ungültige Felder werden auch
  aus geschlossenen Bereichen aufgedeckt; der originale Feldknoten und noch
  nicht übernommener Text bleiben erhalten. Ein Validierungsabbruch speichert
  nicht und startet keinen Auftrag.
- **Schmale Ansichten:** Hauptnavigation, aufklappbare Abschnitte, Jobhistorie
  und Projektkarten umbrechen lokal. Lange Projekt- und Personennamen werden
  nicht gekürzt, um Dokumentüberlauf zu verbergen. Kalenderdienste können
  mehrzeilig sein und bleiben neben der festen Personenspalte lokal scrollbar.
- **Lokales Favicon:** eine mitgelieferte SVG statt der von der bestehenden
  Content-Security-Policy gesperrten Daten-URL. Die CSP wird nicht gelockert.
- **Lesbare Navigation:** aktive und inaktive Beschriftungen, Icons und Zähler
  behalten auch bei Hover und Tastaturfokus ausreichend Kontrast.
- **Hauptbedienfelder:** „Speichern und berechnen“ und die Kalenderauswahl
  „Ansicht“ sind mindestens 44 Pixel hoch. Auf schmalen Ansichten wird dafür
  umgebender Abstand reduziert, nicht die Bedienfläche oder Beschriftung.
- Dauerhafte Regressionen sichern gleichzeitige Prüfung/Bearbeitung,
  Projektwechsel und verspätete Zulassungsantworten gegen Datenverlust ab.

## Nachvollziehbarer Prüfumfang

Die neuen Browserregressionen stehen in `tests/browser/review-navigation.cjs`,
`review-workspace-races.cjs`, `review-workspace-layout.cjs` und
`review-primary-controls.cjs`. Sie verwenden
synthetische Projekte, echte Handler, lokale Server und Backend-Readback.
Künstlich verzögerte Antworten sind Race-Proben, keine gemessene Netzleistung.

- Der bekannte Referenzfall bleibt erhalten: drei Personen, sechs
  Einteilungen und 2880 Minuten; CSV/XLSX-Readback und gespeicherte Wiederaufnahme
  prüfen IDs, Fixierungen und Inhalt. Datei-Auswahlereignisse sind kein Nachweis
  nativer Betriebssystemdialoge oder ausgeführter Tabellenkalkulation.
- Die Hauptnavigation benötigt vier statt sechs gleichrangige Ziele. Vom
  Berechnungsstart zum fertigen Kalender ist kein Wechsel zwischen „Planen“ und
  „Dienstplan“ mehr nötig. Das beschreibt die Oberfläche und reproduzierbare
  Browseraufgaben, keine menschliche Bearbeitungszeit oder Nutzertest-Ergebnisse.
- 80 Layoutfälle kombinieren fünf Viewports (320×1000, 390×800, 390×1000,
  768×1000, 1440×1000), Standard-/Langtexte, 100/125 Prozent Schriftgröße sowie
  frisch berechnete und wieder geöffnete Projekte. 125 Prozent bedeutet
  nachgemessene CSS-Schriftvergrößerung, nicht natives Browser-/OS-Zoom.
- Ohne Scrollen zugesagt ist nur der Standardtext-/100-Prozent-Referenzfall:
  beide Dienste des ersten Planungstags bei 1440×1000; bei 390×1000 die volle
  erste Personenzeile mit mindestens 32 Pixeln vertikaler Reserve. Für schmale
  Dienste und erweiterte Textfälle wird lokal gescrollt und auf tatsächliche
  Sichtbarkeit, Beschneidung und Überdeckung geprüft. Lange Namen können hohe
  Zeilen erzeugen; nicht alle Dienste sind gleichzeitig sichtbar.
- Eine getrennte Kontrollregression prüft aktive/inaktive Hauptnavigation
  bei 320×1000 und 1440×1000 in Ruhe, bei Hover und echtem Tastaturfokus:
  Beschriftungen, Icons und sichtbare Zähler erreichen mindestens 4,5:1.
  Sie prüft die beiden Hauptbedienfelder bei 320×1000, 390×1000 und 1440×1000
  mit 100/125 Prozent CSSOM-Schrift auf Höhe, Fokus, Sichtbarkeit und Hit-Tests.
  Zusätzliche unabhängige Proben umfassen die Navigation auch bei 125 Prozent
  CSSOM-Schrift; das ist kein natives Browserzoom oder vollständiges WCAG-Audit.
- Die Layoutmatrix prüft bestimmte Navigationselemente, Projekt-/Personenbezeichner,
  Kalenderdienste und das Layout des Abmeldebuttons. Sie ist keine umfassende
  Touch-, Kontrast-, Authentifizierungs-, Screenreader- oder
  Barrierefreiheitszertifizierung und deckt nicht sämtliche Controls ab.

## Bewusst noch offen

Die grundlegende Navigation ist umgesetzt, nicht das gesamte historische
[UX-Zielbild](ux/TARGET-WORKFLOW.md). Team-/Importpflege, der Einstieg leerer
Projekte (weiterhin Team), Diagnose-Rückkehrpunkte und ein kontextnaher
Einteilungseditor bleiben Folgearbeiten. Einrichtung verwendet zunächst zwei
lokale Ansichten, nicht die drei weiterführenden Zielgruppen des Entwurfs.

## Daten und Aktualisierung

Kein Wechsel von Solver, API, Datenbankschema, Importsemantik oder numerischem
JSON-Vertrag. Persönliche Grenzen, Begleitpflichten, Freigaben und notwendige
Bestätigungen bleiben erhalten. Ungültige Exporte werden serverseitig abgewiesen.

Vor einer selbst durchgeführten Aktualisierung Projektsicherungen und das
Zustandsverzeichnis sichern. Image-Version: `0.31.1`; für reproduzierbare
Installationen den veröffentlichten `sha-…`-Tag oder Digest verwenden.
Die Veröffentlichung aktualisiert keine laufende Installation automatisch.
