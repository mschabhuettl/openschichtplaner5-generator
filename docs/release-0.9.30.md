# Version 0.9.30 – Feste Bedienleiste im Dienstplan

Suche, Seitensteuerung und Besetzungsübersicht bleiben an ihrem Platz,
während ausschließlich das Monatsraster horizontal und vertikal scrollt.
So können auch am Mobilgerät andere Personen gesucht oder Planseiten
gewechselt werden, ohne zunächst an den Monatsanfang zurückzuscrollen.
Die fixierten Personen- und Datumsüberschriften bleiben im Kalender erhalten.

Die Änderung verwendet die bestehenden Kalender- und Tabellenkomponenten.
Browserregression: 1440 und 390 Pixel, tatsächlich gescrolltes Monatsraster,
unveränderte Position der Suche und kein horizontales Seitenüberlaufen.
Keine fachliche Regel, Freigabe oder Einteilung wird verändert.

Enthält die 11/36-Ruhevorgaben und das weiche Blockziel aus
[Version 0.9.29](release-0.9.29.md) sowie die zusammenhängende Neugestaltung
von [Version 0.9.28](release-0.9.28.md).
Veröffentlichung nach den [Release-Gates](verification.md) und separater
privater API-Prüfung. Die Benutzerinstallation bleibt unverändert.
