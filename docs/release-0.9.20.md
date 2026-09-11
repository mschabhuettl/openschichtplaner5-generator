# Version 0.9.20 – Folgezeitraum vorbereiten

Die Importmaske kann aus dem geöffneten Projekt den nächsten Zeitraum vorbereiten:
Beginn am unmittelbar folgenden Kalendertag, wahlweise dieselbe Tagesanzahl
oder bis zum Monatsende. Der Vorschlag zeigt Anfang, Ende und Tagesanzahl vor
seiner Übernahme. Schaltjahre, Jahreswechsel und unterschiedlich lange Monate
werden kalendarisch berücksichtigt, ohne pauschalen Wochen-/Monatsfaktor.

„Planungsdaten vorbelegen“ setzt nur die Planungsdaten, die Projektzeitzone und
den vorhandenen Vorschlag für drei vorausgehende Monate als Historie. Erneutes
Drücken bleibt am geöffneten Projekt verankert und springt nicht weiter.
Das Projekt selbst, Quellen- und Teamauswahl, Ist-/Soll-Optionen und alle
Freigabe-/Übernahmeoptionen bleiben unverändert. Noch kein Import wird gestartet.

Quelle und Teams müssen vor dem anschließenden Import geprüft werden. Der
vorhandene Einrichtungsassistent übernimmt frühere Einstellungen nur auf
weiterhin ausdrücklichen Wunsch bei identischer Quelle. Gültigkeiten werden
nicht verlängert; Quelldaten und fachliche Voraussetzungen bleiben zu prüfen.
Bei offenen JSON- oder Abwesenheitsentwürfen ist die Vorbereitung gesperrt,
bis ein vollständig übernommener Stand vorliegt.

## Prüfungen und Aktualisierung

Synthetische Kalendertests prüfen Schaltjahr, Jahreswechsel, Monatsreste,
Sommerzeitwoche, ungültige Eingaben und unveränderte Ausgangsdaten. Der
Desktop-/Mobil-Browserablauf prüft Vorschau, Übernahme, Tastaturfokus,
Wiederholung ohne Weiterspringen sowie unveränderte Projektdaten und Optionen.
Er prüft ausdrücklich, dass die Vorbereitung keine Importanfrage auslöst.

Die [Änderungen aus 0.9.19](release-0.9.19.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
