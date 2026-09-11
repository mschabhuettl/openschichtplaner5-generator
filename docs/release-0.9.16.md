# Version 0.9.16 – Zuordnungsursachen gezielt prüfen

Die Einzelansicht importierter Vergleichsdienste erklärt jetzt die konkrete
Zuordnungsstufe: kein Datum-/Dienstbedarf, kein passendes Team, kein passender
Arbeitsplatz, Maximum 0 oder mehrere passende Bedarfsgruppen. Die Meldung
benennt die erste scheiternde Filterstufe, keine vollständige Prüfung aller
Planungsregeln. Die Kandidatenbedingungen selbst bleiben unverändert.

Ein beschrifteter Filter zeigt alle Dienste oder gezielt nicht zugeordnete,
mehrdeutige beziehungsweise eindeutig zugeordnete Dienste. Zehnerseiten bleiben
bestehen; beim Filterwechsel beginnt die Liste wieder auf Seite eins.
Alte Projekte ohne gespeicherte Ursache erhalten keine erfundene Diagnose.

## Prüfungen

396 Python-Tests, Ruff und Diffprüfung erfolgreich. Die synthetischen Fälle
prüfen alle fünf Ursachen, unveränderten Bedarf und fehlende automatische
Freigaben. Der vollständige Desktop-/Mobil-Browserablauf prüft die Meldungen,
Filter, leere Trefferlisten, Seitenwechsel und unveränderte Projektversion,
Dirty-Status sowie Projektdaten. Der Filter verwendet ausdrücklich keine
Bearbeitungsaktion, die Ergebnisse ungültig machen würde.

Die [Änderungen aus 0.9.15](release-0.9.15.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
