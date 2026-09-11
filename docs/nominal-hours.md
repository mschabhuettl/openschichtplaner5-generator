# SP5-Sollstunden: Monat, Woche oder Zeitraum?

Die Quellenbasis entscheidet, nicht eine globale Annahme „pro Woche“.
Die eingebundene [SP5-Library 1.32.3](https://github.com/mschabhuettl/libopenschichtplaner5/blob/v1.32.3/sp5lib/calculations.py#L334-L417)
verwendet `CALCBASE`:

| Basis | Quelle | Bedeutung |
| --- | --- | --- |
| 0 | HRSDAY | Arbeitstage × Tagessoll |
| 1 | HRSWEEK | Ganze Kalenderwochen; Resttage nach Tagessoll |
| 2 | HRSMONTH | Ganze Kalendermonate; Resttage nach Tagessoll |
| 3 | HRSTOTAL | Gesamtsoll des Beschäftigungszeitraums, anteilig nach Arbeitstagen |

Beschäftigungsgrenzen, Arbeitstagsmaske und gegebenenfalls Feiertagsabzug
wirken in der Quellenformel mit. Kein pauschaler Faktor 4 oder 4,33.

Der Generator ruft diese Berechnung für den gewählten Planungszeitraum auf
und wandelt das Ergebnis in Minuten um. API- und Verzeichnisimport verwenden
denselben Adapter. Verfügbare Sollbuchungen (Typ 1) werden mit Vorzeichen
und exaktem Personen-/Zeitraumbezug über die vorhandene Library addiert.
Fehlende Buchungsquellen bleiben ausdrücklich ungeklärt; Zugriffs- oder
Formatfehler werden nicht als leere Quelle behandelt. Zeitgutschriften
und Anfangssalden bleiben separat zu prüfen. Negative Gesamt-Sollwerte
werden als Quellwert erhalten und wegen des nichtnegativen Zielstunden-
vertrags ausdrücklich zur Klärung markiert. Bestehende Projekte werden
nicht automatisch neu berechnet.

## In der Oberfläche

„Sollstunden im Planungszeitraum“ ist das Soll für den gesamten Zeitraum.
Die seit 0.9.11 angezeigte Herkunft nennt separat die ursprüngliche
Quellenbasis, den Importzeitraum und das damals berechnete Soll. Nach
manueller Bearbeitung bleibt dieser Importnachweis unverändert. Ältere
Projekte ohne Herkunftsdaten erhalten keine erfundene Quellenbasis.

Maximale Wochenstunden sind dagegen eine verbindliche Regelgrenze.
Weder diese Grenze noch persönliche Freigaben werden aus einem Monats-Soll
abgeleitet oder geändert.

## Synthetischer Nachweis

Bei Tagessoll 7, Wochensoll 36 und Monatssoll 156:

- 2.–8. Februar 2026: Tagesbasis 35 h, Wochenbasis 36 h, Monatsbasis 35 h.
- Vollständiger Februar: Monatsbasis 156 h.
- Februar und März vollständig: Monatsbasis 312 h.
- Geschlossener Beschäftigungszeitraum: dessen Gesamtsoll 1.800 h.

Die Importtests prüfen diese Fälle mit künstlichen Quellwerten.
Sie belegen die Adapterverwendung, keine Vollständigkeit unbekannter
Originalbestände. Zusätzliche Buchungstests prüfen Typtrennung,
Vorzeichen, Beschäftigungsränder und Jahreswechsel.

## Warum trotz passender Freigabe keine Einteilung entstehen kann

Das Stunden-Ziel bewertet den Betrag von
`bezahlte Planminuten + bestätigte Gutschrift + Anfangssaldo − Zeitraum-Soll`
(`solver.solve`: `model.add_abs_equality` für `hours:<employee>`). Eine Person,
deren Soll bereits durch ausdrücklich konfigurierte Gutschriften oder Salden
abgedeckt ist, kann deshalb ohne Dienst bleiben, während eine andere Person
mit offenem Soll den vorhandenen Bedarf übernimmt. Das ist keine fehlende
Freigabe und keine Pflichtverletzung zur Einplanung aller Personen.
Die Ergebniskennzahlen geben diese Komponenten getrennt aus; die Diagnose
`not_selected_with_candidates` behauptet bewusst keine eindeutige Ursache
für einen beliebigen zeitbegrenzten Lauf mit mehreren Optimierungszielen.

Die synthetischen Gegenproben
`test_confirmed_account_adjustments_can_explain_nonselection` belegen die
Auswahl bei isoliertem Stunden-Ziel für Gutschrift, positiven Saldo und eine
Kombination mit negativem Saldo. Weitere zwölf Fälle in
`test_account_adjustments_never_offset_elapsed_hard_limits` prüfen: Auch
sehr hohe positive Gutschriften oder negative Salden kompensieren keine
Überschreitung tatsächlicher Tages-/Wochenminuten, weder in vollständiger
noch in Teilplanung. Unabhängige Validierung und Solver lehnen dieselbe
achtstündige Einteilung bei einer Grenze von 479 Minuten ab, selbst wenn
nur 60 Minuten bezahlt werden.

Diese Nachweise autorisieren **keine** Übernahme importierter Ist-Summen,
Buchungsnachweise oder Abwesenheitsbewertungen als Gutschrift/Anfangssaldo.
Sie reproduzieren nicht den bislang fehlenden Originalstand des gemeldeten
600-Sekunden-Laufs aus 0.9.29.

Die sechs Auswahl-Gegenproben durchlaufen außerdem den öffentlichen CSV-/XLSX-
Export mit dem tatsächlich gelösten und erneut validierten Plan. Beide Exporte
geben für die nicht ausgewählte und die eingeteilte Person dieselbe Bilanz aus;
Excel trennt Planstunden, Gutschrift und Vortrag, CSV fasst Planminuten und
Gutschrift in der ausdrücklich so beschrifteten Ist-Spalte zusammen.
Absichtlich verfälschte zwischengespeicherte Ergebniskennzahlen beeinflussen
diese exportierte Bilanz nicht (`export.rows`, `workbook.planning_workbook`).
Damit ist hier keine abweichende Exportarithmetik nachgewiesen.

### Zeitabbruch und zertifizierter Initialplan

Die Bilanz bleibt auch in den gezielt kontrollierten Zeitabbruchzweigen
identisch: `test_quality_timeout_preserves_independently_validated_partial_incumbent`
prüft einen Teilplan mit acht realen, aber nur einer bezahlten Stunde. Die
harte Achtstunden-Wochengrenze erlaubt weiterhin nur einen der zwei Dienste;
Gutschrift und Saldo kompensieren keine Einsatzzeit. Nach UNKNOWN in der
Qualitätsphase bleibt das unabhängig geprüfte Ergebnis FEASIBLE. Seine
`objective_phase` bleibt `vacancies`: `objective_value = 1` bezeichnet die
offene Besetzung, **nicht** die Stundenabweichung von 60 Minuten.

`test_initial_plan_timeout_requires_certificate_and_keeps_account_balance`
aktiviert mit 40 synthetischen Personen den bestehenden Initialplanpfad der
Vollplanung (`solver.solve`). Ein echtes CP-SAT-Zertifikat für die festgelegten
Einteilungen plus unabhängige Validierung erlaubt bei anschließendem UNKNOWN
den FEASIBLE-Rückfall. Gutschrift, positiver/negativer Saldo, bezahlte Minuten
und Stunden-Zielbeitrag bleiben konsistent. Liefert bereits die Zertifizierung
UNKNOWN und die anschließende Suche ebenfalls UNKNOWN, wird der Vorschlag
nicht als gültiger Plan ausgegeben. Diese kontrollierten Statusgegenproben
sind kein realer 600-Sekunden-Lasttest und kein Optimalitätsnachweis.
