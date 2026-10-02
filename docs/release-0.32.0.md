# Version 0.32.0 – Personen und Sollstunden zuerst

## Team ohne Umweg

Der Bereich **Team** startet mit der Personenliste. **Planen**, **Soll** und
**Bearbeiten** stehen direkt an jeder Person. Weitere persönliche Vorgaben,
Abwesenheiten und Freigaben bleiben erhalten; die neue Reihenfolge ändert keine
fachlichen Regeln und bestätigt keine ungeprüften Annahmen.

- **Personen** und **Freigaben** sind benannte lokale Ansichten. Die Matrix mit
  Suche, vertauschbaren Achsen und zeitlich begrenzten Freigaben liegt unter
  **Freigaben**.
- Gruppen- und Sammelwerkzeuge sind zunächst eingeklappt und bei Bedarf
  erreichbar. Die häufige Personenaufgabe erfordert kein Öffnen dieser Werkzeuge.
- Das Wechseln der lokalen Ansicht erhält bestehende Eingabeknoten und noch
  nicht übernommene Texte. Ein anderes geöffnetes Projekt startet bei Personen.
- Korrekturaktionen öffnen die passende Personen- oder Freigabenansicht.
  Verhindert eine ungültige Eingabe oder ein offener Abwesenheitsentwurf das
  Speichern oder Berechnen, wird das vorhandene Feld offengelegt und nach Ende
  der Sperre fokussiert, ohne den Entwurf neu aufzubauen.
- Der vorhandene zentrale Schutz gegen überlappende Änderungen bleibt erhalten.
  Die Browserregressionen öffnen nach einem Import die tatsächlich benötigte
  lokale Ansicht über deren sichtbares Bedienelement.

## Gemessene Erstaufgabe

Die Messung verwendet dasselbe ausdrücklich synthetische Drei-Personen-Team
für den 5. bis 9. Oktober 2026, Zeitzone Europe/Vienna. Referenz ist der
veröffentlichte Stand 0.31.1, nicht eine nachträglich vereinfachte Ausgangsseite.

- Bei **1440 × 1000** sank die Zahl layout-sichtbarer Bedienelemente in der
  Team-Einstiegsansicht von **53 auf 27**, bei **390 × 1000 von 52 auf 26**.
  Geschlossene Detailinhalte werden nicht mitgezählt. Layout-sichtbar bedeutet
  nicht automatisch innerhalb des aktuellen Viewports.
- Name, Einplanung und Sollfeld der ersten Person sind bei diesen beiden
  Größen ohne Scrollen und ohne Matrix-/Gruppenumweg vollständig sichtbar und
  per Hit-Test erreichbar. Bei **320 × 1000** gilt der engere Vertrag:
  kein dokumentweiter horizontaler Überlauf; lokales Scrollen ist erlaubt.
- Die Sollaufgabe ändert den ersten Wert auf **32 Stunden**, speichert über die
  ursprüngliche Aktion und öffnet das Projekt erneut. Der persistierte Wert
  beträgt exakt **1920 Minuten**; andere Projektwerte bleiben unverändert,
  abgesehen von der serverseitigen Revision.

Dies sind reproduzierbare Browseroperationen und Geometriemessungen, keine
menschlichen Bearbeitungszeiten oder Ergebnisse einer Nutzerstudie. Lange Namen
werden zusätzlich auf Überlauf und erreichbare Bearbeitung geprüft; daraus
folgt keine Zusage, dass jeder beliebig lange Name im ersten Viewport Platz hat.

## Abgegrenzter Prüfumfang

Die Regressionen umfassen lokale Navigation, unverarbeitete Eingaben,
Tastaturaktionen und Fokus nach beendetem Scrollen, Save/Solve mit offenem
Abwesenheitsentwurf sowie synthetisch verzögerte Speicher- und Prüfantworten.
Die vorhandenen Prüfungen für numerische Werte, Datenhaltung, Freigaben,
Begleitung, persönliche Grenzen, Exporte, Planlayout und Hauptbedienelemente
bleiben erforderlich. Es gibt keine Änderungen an API, Schema oder Solver.

Headless-Chromium-Prüfungen sind keine vollständige WCAG-, Screenreader- oder
Betriebssystemdialog-Abnahme. CSV-/XLSX-Erzeugung und programmgesteuertes
Zurücklesen sind keine Ausführung einer nativen Tabellenkalkulation.
Die weiteren Schritte für Import, Diagnose und Plankorrektur sind nicht mit
UX-03A abgeschlossen.

## Aktualisierung

Vor einem Update das vollständige Zustandsverzeichnis sichern. Die neue
Paket- und Imageversion ist **0.32.0**; für reproduzierbare Installationen den
zugehörigen Commit-Tag oder Image-Digest verwenden. Veröffentlichte Downloads
anhand ihrer `SHA256SUMS` prüfen. Eine veröffentlichte neue Version aktualisiert
oder startet eine bestehende Installation nicht automatisch.
