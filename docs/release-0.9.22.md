# Version 0.9.22 – Einteilungen bei erfolgloser Berechnung erhalten

Ein erfolgloser Berechnungslauf darf vorhandene Einteilungen nicht durch eine
leere Ergebnisliste ersetzen. Die Oberfläche übernimmt jetzt nur eine
unabhängig gültige Lösung mit Solverstatus `FEASIBLE` oder `OPTIMAL`.
Gültige Teilpläne bleiben möglich. Bei `MODEL_INVALID`, `UNKNOWN`,
`INFEASIBLE`, fehlendem Ergebnis oder fehlgeschlagener Ergebnisprüfung bleiben
die bisherigen Einteilungen unverändert. Ein erfundener Vergleich „alle entfernt“
wird für diese Fälle nicht mehr angezeigt.

Die Ergebnisüberschrift benennt `MODEL_INVALID`, `UNKNOWN` und `INFEASIBLE`
unmittelbar. Eine Suche ohne Lösung wird ausdrücklich nicht als bewiesene
Unlösbarkeit bezeichnet. Ein fehlendes Ergebnis wird separat gemeldet.
Prüfhinweise bleiben sichtbar; erhaltene alte Einteilungen sind kein neuer Plan.

Die Liste vergangener Aufträge zeigt einen technisch abgeschlossenen Auftrag
neutral als „Beendet · Ergebnis prüfen“, nicht als grünen Planungserfolg.
Dafür werden weiterhin keine großen Ergebnisdateien in die kompakte
Joblistenabfrage geladen. Regeln, Freigaben, Solver und Datenbankschema bleiben
unverändert.

## Prüfungen und Aktualisierung

Die synthetische Browserregression reproduziert auf dem vorherigen Stand den
Verlust einer vorhandenen Einteilung nach `MODEL_INVALID`. Auf dem korrigierten
Stand bleiben die Einteilungen bei allen oben genannten erfolglosen Zuständen
erhalten; nach dem Speichern entsteht dadurch keine neue Projektänderung.
Desktop/Mobil, Joblistenbeschriftung, fehlendes Ergebnis und ausbleibender
Entfernungsvergleich werden geprüft. Die vollständigen positiven Planungs- und
Teilplanabläufe bleiben Teil des Browser-Gates.

Die [Änderungen aus 0.9.21](release-0.9.21.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
