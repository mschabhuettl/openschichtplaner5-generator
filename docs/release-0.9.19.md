# Version 0.9.19 – Vergleichsdienste gezielt prüfen

Einzelne importierte Vergleichsdienste führen direkt zur betroffenen Person,
zum im aktuellen Projekt noch vorhandenen zugeordneten Bedarf oder zur
Bedarfssuche am Datum. Die vorhandenen Editoren und die vorhandene Suche werden
wiederverwendet. Der Tastaturfokus folgt zum Personenformular beziehungsweise
zum Suchfeld. Desktop und schmale Mobilansicht werden geprüft.

Die Datumssuche zeigt alle passenden Bedarfe, keine automatisch ausgewählte
Lösung einer Mehrdeutigkeit. Fehlende Personen erhalten keinen Bearbeitungslink.
Ein inzwischen entfernter Bedarf wird ausdrücklich benannt, nicht neu angelegt.
Die alte Importzuordnung bleibt ein Importstand und ist kein aktueller
Gültigkeitsnachweis. Navigation ändert keine Projektdaten, Freigaben oder Regeln.

## Gebündelte Verbesserungen

Diese Veröffentlichung enthält auch die zuvor vorbereiteten Änderungen:

- [0.9.16: nachvollziehbare Zuordnungsursachen und Filter](release-0.9.16.md).
- [0.9.17: ein gemeinsamer aktueller Eingabeprüfstand](release-0.9.17.md).
- [0.9.18: Suche und Seiten für offene Importangaben](release-0.9.18.md).

Die Ist-/Soll-Auswahl aus [0.9.15](release-0.9.15.md) bleibt unverändert.
Es werden keine persönlichen Freigaben aus Referenzdiensten abgeleitet und
keine Profile automatisch bestätigt.

## Prüfungen und Aktualisierung

Synthetische Browserregressionen prüfen direkte Personen- und Bedarfsnavigation,
Tastaturfokus, Datumssuche, entfernte Referenzziele und unveränderte Projektdaten.
Die vollständigen Paket-, Browser- und Containerprüfungen bleiben Release-Gates.

Ein lokaler Quelltest bleibt von synthetischen CI-Gates getrennt. Ein technisch
abgeschlossener Job mit `MODEL_INVALID`, `UNKNOWN` oder ohne gültiges Ergebnis
belegt keine erfolgreiche Planung. Fehlende fachliche Bestätigungen dürfen
für eine Abnahme nicht erfunden werden. Siehe [Prüfumfang](verification.md).

Benutzerinstallationen werden nicht automatisch aktualisiert.
