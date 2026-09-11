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
