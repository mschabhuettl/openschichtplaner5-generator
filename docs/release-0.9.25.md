# Version 0.9.25 – Erst die Übernahme ändert den Projektstand

Die Auswahl einer noch nicht übernommenen Aktion wird nicht mehr als
Projektänderung behandelt. Das betrifft die Dienstart eines Dienstmusters,
Profil und Team für eine Sammelzuordnung sowie Person und Bedarf beim
Vorbereiten einer zusätzlichen Einteilung.

Vorher konnten solche reinen Auswahlhandlungen den Prüfbericht veralten
lassen und „Ungespeicherte Änderungen“ auslösen, obwohl die Projektdaten
unverändert waren. Jetzt bleiben Projektstand und Ergebnisanzeige erhalten.
Die ausdrückliche Übernahme oder eine tatsächliche Bearbeitung verändert den
Projektstand weiterhin und erfordert eine erneute Prüfung.

Diese Veröffentlichung enthält die [Zeitregel-Vorschau aus 0.9.24](release-0.9.24.md).
Der Kandidat 0.9.24 wurde nicht separat veröffentlicht: Eine neue synthetische
Browserprüfung erwartete Nachtminuten in einer nicht ausdrücklich festgelegten
Projektzeitzone. Die Testdaten legen ihre Zeitzone jetzt unabhängig vom
ausführenden Rechner fest. Die fachliche Zeitregel bleibt unverändert.

## Prüfungen

Der Browserfall reproduziert auf dem vorherigen Stand einen veränderten
Prüfstatus bei identischen Projektdaten. Desktop und Mobil prüfen gespeicherte
Projekte, alle betroffenen Auswahlen, unveränderte Ergebnisanzeigen sowie die
weiterhin notwendige Änderungserkennung nach tatsächlicher Übernahme.
Die Zeitregel-Vorschau wird mit ausdrücklich festgelegter Projektzeitzone
auch auf einem UTC-Prüfrechner ausgeführt.

Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Keine automatischen Freigaben und keine Änderung der Benutzerinstallation.
