# Version 0.9.13 – Vom Prüfhinweis zur Person

Personenbezogene Eingabediagnosen enthalten jetzt die eindeutige
Personenreferenz im bereits vorhandenen Diagnosefeld. Die Oberfläche zeigt
bei diesen Hinweisen den Namen anstelle der technischen Kennung. In der
automatischen Vorprüfung öffnet „Person bearbeiten“ die zugehörige Person,
beispielsweise bei einem fehlenden oder unbestätigten Regelprofil.

Die Zuordnung verwendet weiterhin die Kennung, nicht den Namen. Auch
Namensgleichheit darf keine falsche Person öffnen. Technische Berichte
behalten die Referenz und den ursprünglichen Diagnosetext; Hinweise ohne
eindeutige Personenreferenz werden nicht durch Textsuche zugeordnet.

Prüfbedingungen, Freigaben und Regelgrenzen bleiben unverändert. Die
[automatische Vorprüfung aus 0.9.12](release-0.9.12.md) ist enthalten.

## Prüfungen

Ein synthetischer API-Fall mit gleichen Personennamen prüft die eindeutige
Referenz und weiterhin ausbleibendes Speichern. Der Browser prüft den
lesbaren Profilhinweis und dass dessen Schaltfläche die richtige Person
öffnet; Desktop und Mobil bleiben Teil des vollständigen Ablaufs.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
