# Release 0.6.0

Eigenständiger, lokal rechnender Planungseditor mit SP5-Datei- und API-Import.

## Änderungen

- Bestehende Einteilungen als veränderbare Vergleichsbasis oder ausdrücklich fixiert importieren; kein zusätzlicher Pflichtbedarf im Planungszeitraum.
- Tagesbezogener Sonderbedarf ersetzt Regelbedarf.
- Einsatzbereiche ausgewählter Elternteams mit gesonderter Bestätigung; direkte Mitgliedschaften bleiben erhalten.
- Sonderdienst-Details lesend laden und vollständig identische Dienste zuordnen.
- Mehrteilige Dienstzeiten mit Leerzeichen oder Semikolon vollständig prüfen.

## Installation

Docker-Image: `ghcr.io/mschabhuettl/openschichtplaner5-generator:0.6.0`.
Die bestehende Compose-Konfiguration bleibt kompatibel. Image neu ziehen, Container neu erstellen und Daten neu importieren. Bestehende Snapshots werden nicht automatisch umgedeutet. Im temporären Stack gehen Daten bei Neustart verloren.

## Grenzen

Dieser Release ist kein Nachweis eines vollständig abgenommenen produktiven Dienstplans. Abweichende Sonderdienstzeiten, mehrdeutige Bedarfszuordnungen und ungeklärte DADEM-Semantik bleiben ausdrücklich offene Importangaben. Freigaben, Ruheprofile und Einsatzbereiche müssen fachlich bestätigt werden. Der Generator schreibt nicht in originale SP5-Daten zurück. Keine automatischen Freigaben aus vergangenen Einteilungen.

Entwicklungs- und CI-Tests verwenden ausschließlich synthetische Daten.
