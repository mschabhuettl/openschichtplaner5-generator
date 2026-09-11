# Version 0.9.30 – Zusammengehörige Sicherheitskorrekturen

## Korrigierte Fehler

- **Profilzuordnungen erhalten:** Die Sammelzuordnung im Profileditor verliert
  nicht mehr bereits konfigurierte Personenprofile. Dadurch bleiben dort
  eingetragene Höchstgrenzen wirksam; Profile werden nicht automatisch bestätigt.
- **Dienstüberhang vollständig prüfen:** Solver und unabhängiger Validator
  berücksichtigen reale Dienstanteile nach dem Periodenende für Tages- und
  ISO-Wochengrenzen sowie die betroffene Kalenderwochenruhe. Maßgeblich sind
  zeitlich gültige, zugeordnete Profile und reale lokale Zeitanteile, nicht die
  bezahlten Minuten. Zeitzonenwechsel sind durch synthetische Tests abgedeckt.
- **Personenbezogene Randarbeit:** Importierte Randdienste benötigen keinen
  künstlichen Bedarf und keine nachträglich erfundene historische Freigabe,
  zählen aber weiterhin für Zeitgrenzen und Ruhe. Bestehende explizite
  Fixierungen behalten ihren strengeren Einteilungsvertrag.
- **Ist-Sonderersetzungen:** Tagbezogener Sonderersatz und ersetzter Normaldienst
  werden gemäß Library-Semantik nicht mehr doppelt gezählt. Sollreferenzen und
  echte Zusatzdienste bleiben erhalten; ungeklärte Sonderzeiten bleiben Blocker.
- **Importsemantik:** Signierte Sollbuchungen des Typs 1 werden normalisiert,
  native DADEM-Teamfelder korrekt gefiltert und nicht fixierte Vergleichsdienste
  ohne eindeutigen Bedarf als Diagnose statt alleiniger Planungsblocker geführt.
  Fehlende Bedarfe oder Freigaben werden nicht erzeugt.

Codepfade, Quelltabellen und synthetische Gegenproben stehen in der
[zusammenhängenden Quellanalyse](source-semantics.md).

## Bestehende Projekte und Ergebnisse

Ein Update rekonstruiert **keine bereits verlorenen Profilzuordnungen**.
Vor erneuter Berechnung sind Personenprofile, deren Gültigkeit und tatsächlich
konfigurierte Höchstgrenzen anhand der ursprünglichen Einrichtung zu prüfen.
Alte gespeicherte Ergebnisse werden durch das Update nicht neu berechnet;
vor einer Verwendung erneut mit dem aktuellen Validator prüfen.
Importkorrekturen benötigen einen erneuten Import; ein altes Projekt wird
nicht stillschweigend umgeschrieben. Alte explizite Randfixierungen werden
nicht automatisch in die neue personenbezogene Randarbeit umgewandelt.

Sollstunden sind kein hartes Wochenmaximum. Der Nutzerauftrag definiert
11 Stunden tägliche und 36 Stunden Kalenderwochenruhe, aber kein konkretes
Wochenmaximum. Ein 24h-Dienst ist nicht allein wegen dieser beiden Ruhewerte
verboten; tatsächliche Grenzen und benachbarte Dienste sind zu prüfen.
Eine Pflicht zur Einplanung jeder Person wird nicht neu eingeführt.

## Nachweise und offene Grenzen

- Der Runtime-Stand `b5617f9` hat die vollständige
  [Container-CI](https://github.com/mschabhuettl/openschichtplaner5-generator/actions/runs/34596933955)
  einschließlich Python-, Paket-, Browser- und Docker-Gates bestanden.
  Die Python-Gesamtsuite umfasst 663 bestandene Tests.
- Synthetische Import-bis-Solver-Gegenproben prüfen Voll-/Teilplanung sowie
  FEASIBLE und UNKNOWN unter kontrollierten Statusrückgaben. Harte Fixierungen
  und Grenzen bleiben erhalten; UNKNOWN ohne gültige Zwischenlösung ist kein
  Planerfolg. Dies ist **kein 600-Sekunden-Lasttest**.
- Die private, ausschließlich lesende API-Abnahme dieses Runtime-Stands
  bestätigt Import, Speicherung und Worker. Beide Plansichten bleiben wegen
  offener Einrichtung MODEL_INVALID, ohne generierte Einteilungen. Auch das
  autorisierte 11h/36h-Zusatzprofil beseitigt die übrigen offenen Angaben nicht.
  Es liegt **kein unabhängig gültiger realer Vergleichsplan** vor.
- Der exakte Projekt-/Jobeingang und das Ergebnis des gemeldeten 0.9.29-Laufs
  fehlen weiterhin. Die gefundenen Fehler sind nicht als dessen bewiesene
  Ursache auszugeben. Mehrdeutige Team-/Arbeitsplatzzuordnungen bleiben sichtbar.

Veröffentlichung erst nach den [Release-Gates](verification.md) für den exakten
Release-Commit. Download-Dateien werden ohne Neubau aus dessen erfolgreicher
CI übernommen und erneut per Prüfsumme kontrolliert. Ob die Veröffentlichung
abgeschlossen ist, zeigt die GitHub-Release-Seite; diese Datei allein ist kein
Veröffentlichungsnachweis. Die Benutzerinstallation bleibt unverändert.

## Bereits enthaltene Bedienung

Die feste Suche, Seitensteuerung und Besetzungsübersicht beim Scrollen des
Monatsrasters bleiben enthalten; ebenso die 11/36-Ruhevorschläge und das weiche
Blockziel aus [0.9.29](release-0.9.29.md) und die Neugestaltung aus
[0.9.28](release-0.9.28.md). Dies ist keine neue UI- oder Feature-Serie.
