# Version 0.33.0 – Schichten einrichten, Regeln bewusst prüfen

## Ein klarer Abschluss statt eines überfüllten Schritts

**Neues Projekt** führt durch vier Schritte: **Zeitraum**, **Team**,
**Schichten** und **Regeln prüfen**. Wiederkehrende Schichten und Bedarf stehen
nicht mehr zwischen Regelwerten und Bestätigungen. Das bedeutet bewusst einen
zusätzlichen Weiter-Klick, nicht weniger Schritte insgesamt.

- Alle sieben Regelwerte stehen mit Einheiten in einer lesbaren Übersicht.
  **Regeln anpassen** öffnet die bestehenden Zahlenfelder bei Bedarf.
- **Weiter** und **Projekt erstellen** bleiben in der unteren Aktionsleiste
  erreichbar. Lange Inhalte scrollen innerhalb des Dialogs.
- Die drei Bestätigungen starten weiterhin ungesetzt. Ein Projekt lässt sich
  ohne ausdrückliche Regelbestätigung nicht erstellen; Freigaben und
  dienstfreier Randkontext werden durch Navigation nicht bestätigt.
- Ungültige Angaben führen zum konkreten Feld, auch bei fehlendem Wochentag,
  gleichen Start-/Endzeiten oder widersprüchlicher Mindest-/Höchstbesetzung.
- Zurück/Weiter, Zuklappen und Abbrechen/Wiederöffnen erhalten den Entwurf in
  derselben geöffneten Browserseite. Auch unvollständiger Zahlentext bleibt in
  bestehenden Feldern erhalten, wenn Funktionen ergänzt oder umgeordnet und
  andere Vorlagen hinzugefügt oder entfernt werden. Gelöschte Felder sind
  davon ausgenommen. Ein Neuladen der Seite ist keine Entwurfssicherung.

## Gemessener Umfang

Die Referenzaufgabe verwendet ausschließlich drei synthetische Personen,
eine Funktion und eine Tagschicht Montag bis Freitag vom 5. bis 9. Oktober
2026, Zeitzone Europe/Vienna. Verglichen wird mit Version 0.32.0.

Bei **1440 × 1000** und **390 × 1000 CSS-Pixeln** hatte der bisherige gemeinsame
Schritt 27 layout-sichtbare Bedienelemente. Der getrennte Schichtschritt hat
jetzt **17**, die Regelprüfung zunächst **7**, mit geöffnetem Regeleditor **14**.
Geschlossene Details und der Hintergrund hinter dem Modal zählen nicht mit.
Layout-sichtbar bedeutet nicht vollständig im aktuellen Viewport sichtbar.

Im Standardfall sind **Weiter** und **Projekt erstellen** am Schritteinstieg
vollständig sichtbar und per Mittelpunkt-Hit-Test erreichbar. Dokument und
Dialog haben bei diesen beiden Größen keinen horizontalen Überlauf. Die
Scrollinhalt-Höhen liegen für Schichten unter 1000 Pixeln am Desktop bzw.
1500 mobil, für die Regelprüfung mit geschlossenem Editor unter 1000 bzw.
1200 Pixeln. Für zusätzliche Vorlagen oder den geöffneten Editor gelten diese
Höhengrenzen nicht; deren Ende bleibt durch Scrollen erreichbar.

Diese Messungen sind reproduzierbare Headless-Chromium-Browseroperationen,
keine gemessenen menschlichen Bearbeitungszeiten und keine Nutzerstudie.
Weniger gleichzeitig angebotene Eingaben ist das Gestaltungsziel, keine
behauptete Zeitersparnis.

## Daten, Tastatur und Grenzen

Die Regressionen prüfen gültige und ungültige Texte, Änderungen an Funktionen
und Vorlagen, echte Erstellungs-Payloads, Speichern/Wiederöffnen sowie eine
gezielt eingespritzte HTTP-422-Antwort. Tab und Umschalt+Tab bleiben im Modal;
Escape kehrt außerhalb einer laufenden Erstellung zum Öffner zurück.
Fehlerfokus wird nach beendetem Scrollen auf Sichtbarkeit und Überdeckung
geprüft. Die neuen Hauptaktionsziele sind mindestens 44 × 44 CSS-Pixel groß.

Solver, API, Schemata, Kennungen, Freigabesemantik und gespeicherte Projekte
werden nicht geändert. Der bestehende Team- und Planablauf bleibt erhalten.
Die Browserprüfungen sind keine vollständige WCAG-, Screenreader-, Touchgeräte-
oder Betriebssystemdialog-Abnahme. Programmatisches CSV-/XLSX-Zurücklesen ist
keine Ausführung einer nativen Tabellenkalkulation. Import, Diagnose und
Plankorrektur sind mit diesem Wizard-Slice nicht abgeschlossen.

## Aktualisierung

Vor einem Update das vollständige Zustandsverzeichnis sichern. Paket- und
Imageversion ist **0.33.0**. Für reproduzierbare Installationen den zugehörigen
Commit-Tag oder Image-Digest verwenden und Downloads anhand ihrer
`SHA256SUMS` prüfen. Eine Veröffentlichung aktualisiert oder startet eine
bestehende Installation nicht automatisch.
