# Version 0.9.0 – Einrichtungsassistent

## Importieren, Änderungen prüfen, berechnen

Beim Import lassen sich historische Dienstfreigaben und die Tag-/Nacht-Zeitregel gemeinsam aktivieren. Die Zeitregel bleibt explizit wählbar und veränderbar.

Für wiederverwendbare Einstellungen zuerst das bisherige Projekt öffnen (bei temporärem Betrieb die JSON-Projektsicherung laden). Anschließend beim neuen Import die Übernahme aus der identischen SP5-Datenquelle aktivieren. IDs können in unterschiedlichen Datenbeständen gleich sein; die identische Quelle muss deshalb vom Benutzer sichergestellt werden. Unterschiedliche Adapter oder Zeitzonen werden abgelehnt.

Für übereinstimmende Personen werden Freigaben, Qualifikationen, Verfügbarkeitsfenster, Tag-/Nachtgrenzen, Präferenzen, Wochenend-/Feiertagserlaubnis, Betreuungskapazität und vollständig zuordenbare bestätigte Profile übernommen. Bestehende leere Freigaben bleiben leer; Historienfreigaben wirken dann nur auf neue Personen. Gültigkeiten werden niemals verlängert. Passende Zeitmuster übernehmen bestehende eindeutige Dienstarten. Neue Sollstunden, Beschäftigungsdaten und Teams stammen aus dem aktuellen Import.

Datierte Abwesenheiten, Dienstsperren und Wünsche aus dem bisherigen Projekt werden nicht automatisch übertragen. Ihr Vorhandensein erzeugt offene Prüfpunkte. Widersprüche und Gültigkeitslücken müssen vor der Berechnung geklärt werden. Nicht jede individuelle Projektkonfiguration wird automatisch übernommen.

Die Änderungsübersicht zeigt neue Personen, neue Dienste und offene Übernahmehinweise. „Planungsbereitschaft prüfen“ verwendet dieselbe Eingabeprüfung wie der Solver, ohne einen Rechenlauf zu starten oder Daten zu speichern. Eine erfolgreiche Eingabeprüfung ist kein Beweis für vollständige Besetzbarkeit oder einen gültigen fertigen Plan.

Die bisherigen Größenlimits bleiben unverändert. Änderungen und neue Projekte anschließend speichern oder als JSON sichern. Reale Daten sind kein Bestandteil von Tests oder Auslieferungsdateien.
