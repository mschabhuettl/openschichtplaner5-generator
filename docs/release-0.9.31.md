# Version 0.9.31 – Profilabdeckung und nachvollziehbare Stundenprüfung

Diese gemeinsame Freigabe ergänzt die [Sicherheitskorrekturen aus 0.9.30](release-0.9.30.md).
Sie enthält keine neue UI-Serie und verändert keine Benutzerinstallation automatisch.

## Belegte Korrekturen und Analyse

- **Profilabdeckung bei Dienstüberhang:** Für tatsächlich gearbeitete lokale
  Folgetage nach dem Planungsende müssen gültige zugeordnete Profile bestätigt
  sein. Zuvor konnten Solver und Validator einen solchen Dienst ohne bestätigtes
  Folgeprofil akzeptieren. Vollplanung wird dann unlösbar; Teilplanung lässt den
  betroffenen Dienst offen. Ein Ende exakt um Mitternacht benötigt kein Profil
  für einen nicht gearbeiteten Folgetag. Historische Randarbeit bleibt unverändert.
- **Vollständige unabhängige Limitdiagnose:** Der Validator meldet jede verletzte
  Tages- und ISO-Wochengrenze, nicht nur die jeweils erste. Harte Grenzen beziehen
  sich weiterhin auf reale Arbeit, nicht auf bezahlte Minuten oder Sollstunden.
- **Datierte Stundenherkunft:** Signierte Istbuchungen sowie Abwesenheitsarten und
  deren datumsscharfe Bewertung bleiben als Herkunft erhalten. Die Bewertung nutzt
  die vorhandene Library-Berechnung und trennt Anrechnung, Istabzug und
  Überstundenabzug. Diese Werte erzeugen **keine automatischen Gutschriften**,
  Anfangssalden oder Änderungen von Planungszielen. Fehlende Definitionen und
  mehrdeutige Zeitintervalle bleiben ungeklärt. Die deduplizierte Schedule-Quelle
  ohne ABSEN-ID ist keine zertifizierte vollständige Kontensumme.
- **Zusammenhängende Quellanalyse:** Library, API und OSP5 sind bis zum
  Generator-Mapping verfolgt. Die API-Ruheprüfung übersieht in der untersuchten
  Funktion Nullabstand und Überlappung; der Generator lehnt diese synthetischen
  Fälle unabhängig ab. Die produktive API wurde nicht verändert.

Konkrete Funktionen und Regressionen stehen in [source-semantics.md](source-semantics.md).
Zusätzliche synthetische Gegenproben sichern Voll-/Teilplanung, datierte
Profilwechsel innerhalb einer ISO-Woche, Soll-/Kontenanpassungen, Exporte sowie
FEASIBLE-/UNKNOWN-Fallback und phasenspezifische Zielfunktionsschranken ab.
Ein gültiger FEASIBLE-Plan ist kein Beweis optimaler Freizeitverteilung.

## Vorhandene Projekte und offene fachliche Angaben

Alte Ergebnisse werden nicht automatisch neu berechnet. Vor Verwendung mit dem
aktuellen Validator prüfen; für neue Importherkunft erneut importieren.
Verlorene Profilzuordnungen werden nicht rekonstruiert, Profile nicht verlängert
oder automatisch bestätigt. Persönliche Freigaben und Bedarfe bleiben unverändert.

11h tägliche Ruhe und 36h Kalenderwochenruhe sind die ausdrücklich vorgegebenen
Werte; daraus folgt kein konkretes Wochenmaximum und kein pauschales 24h-Verbot.
Die Einplanung aller Personen ist keine neue Pflicht. Die genaue Ursache des
originalen 0.9.29-Laufs nach 600 Sekunden bleibt ohne seinen Projekt-/Job- und
Ergebnisstand offen.

## Prüfstand und Veröffentlichungsgrenze

Der Runtime-Stand `9581f28` bestand die vollständige
[CI](https://github.com/mschabhuettl/openschichtplaner5-generator/actions/runs/34603999074)
und lokal 753 Python-Tests. Die private lesende API-Abnahme dieses Stands mit
Paketoverlay belegte Import, Speicherung und Worker für Ist und Soll. Beide
Plansichten blieben wegen fehlender Einrichtung MODEL_INVALID, ohne generierte
Einteilungen. Das ist **kein gültiger realer Dienstplan** und noch kein Test eines
veröffentlichten 0.9.31-Images.

Der exakte Release-Commit benötigt eigene Paket-, Browser- und Container-Gates.
Download-Dateien werden danach ohne Neubau aus seiner erfolgreichen CI übernommen
und nach Upload per Prüfsumme kontrolliert. Das veröffentlichte Image erhält
zusätzlich die private lokale API-Abnahme. Der tatsächliche Veröffentlichungsstand
steht auf der GitHub-Release-Seite; diese Notiz allein behauptet keinen Abschluss.
