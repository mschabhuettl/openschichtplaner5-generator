# Version 0.9.21 – Vorprüfhinweise gezielt bearbeiten

Die automatische Vorprüfung zeigt eine beschriftete Kategorienauswahl mit
Hinweisanzahl, etwa für Regelprofile, Randkontext und offene Angaben. Die
vorhandenen Zehnerseiten werden für jede Kategorie wiederverwendet. Beim
Filterwechsel beginnt die jeweilige Liste auf Seite eins; entfällt eine
Kategorie nach einer erneuten Prüfung, werden wieder alle Hinweise angezeigt.

Direkte Prüfaktionen führen mit Tastaturfokus zu den vorhandenen Bereichen
für verbindliche Regelprofile, angrenzende Dienste und offene Importangaben.
Personenbezogene Bearbeitungswege bleiben erhalten. Die Navigation bestätigt
keine Regeln und ändert weder Freigaben noch Projektdaten.

Die Gesamtzahl und der aktuelle Prüfstatus bleiben unabhängig vom Listenfilter
sichtbar. Zwei angezeigte Profilhinweise bedeuten nicht, dass andere Hinweise
verschwunden wären. Die Auswahl speichert nichts, startet keine Berechnung und
löst keine zusätzliche Serverprüfung aus. Eine fehlerfreie Eingabevorprüfung
ist weiterhin kein Nachweis einer lösbaren oder gültigen Planung.

## Prüfungen und Aktualisierung

Der synthetische Browserablauf prüft Desktop/Mobil, unveränderte Daten und
Prüfzustände, die direkten Navigationsziele und Tastaturfokus. Ein Fall mit
1.002 synthetischen Hinweisen prüft Zehnerseiten, Kategorie- und Seitenwechsel
sowie den Rückfall auf alle Hinweise nach einem erneuten Prüfergebnis. Die
bestehenden Prüfungen gegen verspätete Antworten und fehlgeschlagene Prüfungen
bleiben enthalten.

Die [Änderungen aus 0.9.20](release-0.9.20.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
