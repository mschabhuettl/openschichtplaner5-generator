# Version 0.9.17 – Ein gemeinsamer Eingabeprüfstand

Die Übersicht, der Navigationshinweis und die Berechnungsansicht verwenden
jetzt denselben aktuellen fachlichen Eingabeprüfstand. Der separate vereinfachte
Vorbereitungszähler entfällt. Dadurch stehen nicht mehr beispielsweise
19 Vorbereitungspunkte neben 14 fachlichen Hinweisen für denselben Stand.

Vor einer Prüfung erscheint „noch nicht geprüft“, während der Anfrage „wird
geprüft“. Fehler und nicht übernommene Bearbeitung erhalten eigene Zustände,
keine alte Hinweiszahl. Änderungen machen den bisherigen Prüfstand ungültig.
Auch die manuell gestartete Eingabeprüfung aktualisiert die Übersicht.
Null Eingabehinweise bedeuten weiterhin keinen geprüften Dienstplan:
Berechnung und unabhängige Ergebnisprüfung bleiben ausdrücklich erforderlich.

## Prüfungen

Der vollständige synthetische Desktop-/Mobil-Browserablauf prüft identische
Hinweiszahlen, manuelle und automatische Prüfung, laufende Abfragen, Fehler,
verspätete alte Antworten, offene und verworfene Bearbeitung sowie echte
Demo-Eingaben ohne Hinweise. Fachliche Regeln und Freigaben bleiben unverändert.

Die [Änderungen aus 0.9.16](release-0.9.16.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
