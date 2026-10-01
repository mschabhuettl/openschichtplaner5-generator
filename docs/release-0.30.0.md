# Version 0.30.0 – Gespeicherten Plan direkt fortsetzen

Diese Hinweise beschreiben den ersten Umsetzungsschritt UX-02A gegenüber 0.29.1.
Den tatsächlichen Veröffentlichungsstand belegen das GitHub-Release und die
CI-Läufe seines exakten Commits, nicht dieses Dokument.

## Änderungen

- **Direkt zum gespeicherten Entwurf:** Eine Projektkarte mit Einteilungen öffnet
  den Dienstplan, auch per Enter mit Fokus auf der Planüberschrift. Ohne
  Einteilungen bleibt die Team-Einrichtung der Einstieg. Es wird der aktuelle
  gespeicherte Projektstand geöffnet, nicht das Ergebnis einer älteren Berechnung.
- **Kalender vor Analyse:** Kennzahlen, Suchverlauf, Freigabedecke,
  Freigabevorschau und technische Auswertung stehen gesammelt unter
  „Berechnung & Kennzahlen“ hinter dem Kalender. Der Abschnitt beginnt geschlossen
  und ist per Tastatur bedienbar. Alle bisherigen Inhalte bleiben erreichbar.
- **Eindeutige Zustände:** Die Kopfzeile nennt ausdrücklich die Eingabeprüfung,
  der Ergebnisstatus die Planvalidierung. Ein wieder geöffneter Entwurf ist
  gespeichert, aber noch nicht aktuell geprüft. Änderungen machen die Prüfung
  veraltet; Speichern ersetzt keine Prüfung und Prüfen ersetzt kein Speichern.
- Die Besetzungsübersicht verwendet auch schmal die ganze verfügbare Breite,
  statt ihren Erklärungstext in eine schmale Kennzahlenspalte zu quetschen.

## Gemessener Umfang

`tests/browser/review-plan-workspace.cjs` verwendet dieselbe synthetische
Drei-Personen-Aufgabe wie die [Ausgangsmessung](ux/BASELINE.md):
5.–9. Oktober 2026, Europe/Vienna, sechs Mindestplätze und sechs Einteilungen.

- Von der Projektübersicht zum gespeicherten Plan: **eine statt zwei
  Aktivierungen**, ohne den separat gezählten Reload. Das ist keine gemessene
  menschliche Bearbeitungszeit.
- Bei 1440×1000 liegt der erste Dienst im Ausgangsstand bei etwa y=1046,
  mit dieser Anordnung bei etwa y=580 und ohne Scrollen im sichtbaren Bereich.
- Bei 390×1000 sind Kalenderanfang und erste Personenzeile ohne vertikales
  Scrollen sichtbar. Der Monat bleibt horizontal scrollbar; damit ist **nicht**
  behauptet, sämtliche Dienste oder Tage seien zugleich im schmalen Viewport.
- Die Regressionen lesen den echten gespeicherten Snapshot zurück: IDs,
  Fixierungen, Einteilungen und Revision bleiben beim Öffnen exakt erhalten.
  Abgebrochene Wechsel, Ladefehler und verspätete Antworten behalten lokale
  Änderungen. Verzögerungen und Fehler sind ausdrücklich synthetisch eingespritzt.

Das sind reproduzierbare Browserprüfungen, kein Nutzertest und keine allgemeine
Barrierefreiheitszertifizierung. Der [Zielablauf](ux/TARGET-WORKFLOW.md) bleibt
weiterführender Entwurf: vier Hauptbereiche, vereinfachte Team-/Importpflege,
gezielte Diagnose und schmale Navigation sind **noch nicht vollständig umgesetzt**.
Die dortigen historischen Aussagen beziehen sich auf den unveränderten
Ausgangsstand und sind keine zusätzlichen Fertigmeldungen für 0.30.0.

## Daten und Aktualisierung

Kein Wechsel von Solver, API, Datenbankschema, Importsemantik oder numerischem
JSON-Vertrag. Persönliche Grenzen, Begleitpflichten, Freigaben und ausdrückliche
Bestätigungen bleiben erhalten. Ungültige Exporte werden weiterhin serverseitig
abgewiesen. Die bestehenden Dirty-, Versions- und Operationssperren werden
verwendet, nicht durch eine zweite Navigationszustandsmaschine ersetzt.

Vor einer selbst durchgeführten Aktualisierung die eigenen Projektsicherungen
und das Zustandsverzeichnis sichern. Image-Version: `0.30.0`; für einen eindeutig
reproduzierbaren Stand den veröffentlichten `sha-…`-Tag oder Digest verwenden.
Die Image-Publikation aktualisiert keine laufende Installation automatisch.
