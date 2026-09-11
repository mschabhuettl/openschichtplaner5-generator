# Version 0.9.10 – Klarer zur Berechnung

Die Planungsgrundlage in „Berechnen“ zeigt jetzt den vollständigen Zeitraum
mit beiden Jahreszahlen, ausdrücklich einschließlich Anfangs- und Enddatum,
die Kalendertage und die Zeitzone. Direkt unter dem Vorbereitungshinweis
führen zwei Schaltflächen zu Team/Freigaben und Regeln/offenen Angaben.
So lassen sich fehlende Angaben ohne Suche in der Navigation bearbeiten.

Die vorhandene Navigation setzt den Tastaturfokus auf die Zielüberschrift.
Die Schaltflächen sind mindestens 44 Pixel hoch und umbrechen auf kleinen
Bildschirmen. Die Angaben ersetzen keine fachliche Vorprüfung oder
Ergebnisvalidierung. Regeln, Freigaben und Stundenberechnung bleiben unverändert.

## Prüfungen

Der synthetische Browserablauf prüft die einschließende Fünftagesperiode,
Europe/Vienna, die Navigation per Tastatur und Klick, den Zielfokus und
fehlenden horizontalen Seitenüberlauf bei 1440 und 390 Pixeln. Der bestehende
Ablauf von Projektanlage über Berechnung bis Export bleibt Bestandteil
der [Release-Gates](verification.md). Screenshots vor und nach der Änderung
wurden lokal mit synthetischer Demo auf Desktop und Mobil geprüft.

Die Änderungen aus [0.9.9](release-0.9.9.md) bleiben enthalten.
Die Veröffentlichung setzt erfolgreiche Paket-, Browser- und Container-Gates
voraus. Benutzerinstallationen werden nicht automatisch verändert.
