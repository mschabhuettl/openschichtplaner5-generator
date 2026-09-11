# Version 0.9.9 – Keine still gerundeten Planungsregeln

Die Projektanlage weist Stundenwerte für Ruhe- und Arbeitszeitgrenzen zurück,
wenn sie nicht ganzen Minuten entsprechen. Bisher wurden solche Werte auf die
nächste Minute gerundet: Damit konnte eine Mindestruhe kürzer oder eine zulässige
Höchstarbeitszeit länger werden als eingegeben. Die Änderung betrifft Mindestruhe,
Ruhe nach Nachtdiensten, Wochenruhe sowie tägliche und wöchentliche Höchstarbeitszeit.

Die API antwortet mit HTTP 422 und einem verständlichen Hinweis auf die betroffene
Regel. Es wird kein Projekt erzeugt und kein Wert automatisch nach unten oder
oben korrigiert. Übliche Viertelstunden und minutengenaue Angaben bleiben erhalten;
nur unvermeidbares Gleitkomma-Darstellungsrauschen wird toleriert. Individuelle
Sollstunden und ihre bisher dokumentierte Berechnung werden nicht verändert.

Die Oberfläche verwendet für diese Regeln bereits Viertelstundenschritte.
Bestehende Projekte speichern Regeln in ganzen Minuten und werden nicht verändert.
Persönliche Dienstfreigaben und optionale Qualifikationen bleiben unverändert.
Die [Release-Downloads aus 0.9.8](release-0.9.8.md) sind enthalten.

## Prüfumfang

Fünf Regressionen prüfen nicht minutengenaue Regelwerte, eine weitere prüft
HTTP-Status, verständliche Fehlermeldung und unveränderte gespeicherte Projekte.
Diese sechs Fälle wurden vor der Korrektur als fehlschlagend reproduziert.
Drei weitere Fälle belegen unveränderte Viertelstunden, Dezimalstunden und die
Gleitkommadarstellung einer einzelnen Minute. Alle bestehenden
[Release-Gates](verification.md) müssen vor Veröffentlichung erfolgreich sein.

## Aktualisierung

Vor einem Update Projekte sichern. Nach erfolgreicher Veröffentlichung steht
`ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.9` zur Verfügung.
Laufende Benutzerinstallationen werden nicht automatisch verändert.
