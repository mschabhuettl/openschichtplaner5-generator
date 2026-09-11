# Version 0.9.12 – Automatische Vorprüfung

Beim Öffnen von „Berechnen“ prüft die Anwendung automatisch die aktuellen
Eingaben über den bereits vorhandenen fachlichen Prüfer. Konkrete Hinweise
stehen direkt in dieser Ansicht, seitenweise statt in einer unbegrenzten Liste.
Der zusätzliche manuelle Prüfklick unter „Einrichtung prüfen“ bleibt möglich,
ist für diesen Ablauf aber nicht mehr erforderlich.

Die Automatik speichert nichts und startet weder Solver noch Freigabe oder
Übernahme. Ein unauffälliger Eingabecheck beweist keine lösbare Planung oder
vollständige Besetzung; die Berechnung und unabhängige Ergebnisprüfung bleiben
notwendig. Freigaben und fachliche Regeln bleiben unverändert.

Unveränderte Projektstände verwenden ihren vorhandenen Prüfstand. Änderungen
lösen beim nächsten Öffnen der Ansicht eine neue Prüfung aus. Verspätete
Antworten zu früheren Ständen werden verworfen. Nicht übernommene JSON- oder
Abwesenheitsbearbeitung wird ausdrücklich angezeigt, nicht als geprüft
behandelt. Bei einem Anfragefehler erscheint ein erneuter Versuch statt eines
Erfolgshinweises. Auch ein während Bearbeitung verworfener Wiederholungsversuch
verhindert keine spätere Prüfung.

## Prüfungen

Der reale synthetische Browserablauf prüft automatische Hinweise ohne
Speicher-/Jobanfragen, einen gültigen Eingabezustand, Navigation ohne
Doppelanfragen, HTTP-Fehler und Wiederholung, verspätete alte Erfolge,
offene JSON-Bearbeitung und erneute Prüfung nach deren Verwerfen.
Der zuletzt genannte Übergang wurde vor der Korrektur rot reproduziert.
Desktop und Mobil prüfen die Darstellung ohne horizontalen Seitenüberlauf.

Die [Änderungen aus 0.9.11](release-0.9.11.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
