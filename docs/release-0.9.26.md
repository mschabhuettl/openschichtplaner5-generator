# Version 0.9.26 – Vergleichsdienste gezielt finden

Importierte Vergleichsdienste lassen sich jetzt nach sichtbarem Personnamen,
Dienstnamen, Datum oder ursprünglicher Kennung durchsuchen. Die Suche verwendet
die vorhandene paginierte Liste und lässt sich mit dem Zuordnungsfilter
kombinieren. Technische Kennungen bleiben zusätzlich auffindbar.

Die Übersicht behält ihre Summen für den gesamten Import. Eine leere
Trefferliste erklärt, dass Suchbegriff oder Filter angepasst werden können;
sie bedeutet nicht, dass Vergleichsdienste entfernt wurden. Suche und Filter
verändern weder Projektdaten noch Freigaben, Regeln oder Prüfstatus.

## Prüfungen

Der synthetische Browserfall belegt zunächst die fehlende Suchfunktion auf
dem vorherigen Stand. Auf Desktop und Mobil werden Namen, Dienst, Datum,
Kennung, Nulltreffer, die Kombination mit dem Zuordnungsfilter und unveränderte
Import-Gesamtsummen geprüft. Der vollständige Projekt- und Änderungsstand
muss vor und nach der Suche identisch bleiben.

Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Die Benutzerinstallation wird nicht automatisch aktualisiert.
