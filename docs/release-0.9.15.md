# Version 0.9.15 – Ist oder Soll als Vergleich wählen

Die Importmaske bietet eine ausdrückliche Plansicht für normale Vergleichsdienste
im Planungszeitraum. Ist bleibt Vorgabe; Soll ist eine bewusste Auswahl.
Die historische Planbasis bleibt unabhängig. Abwesenheiten, Sonderdienste und
angrenzende Dienste bleiben aus Ist, selbst innerhalb desselben Quellmonats.
Ein leerer Sollplan wird nicht durch Ist ersetzt.

Die Umsetzung nutzt die vorhandene Bibliotheks-/API-Funktion, keine neue
Interpretation der SP5-Dateiformate. Details und Quellbeleg:
[Ist, Soll und historische Planbasis](reference-plans.md).

## Prüfungen

390 Python-Tests sowie der vollständige synthetische Browserablauf auf Desktop
und Mobil erfolgreich; zusätzlich wird der Verzeichnisimport mit beiden
Referenzansichten geprüft. Die gezielten Regressionen bestätigen unveränderte
Abwesenheiten, Randdienste, Sonderdienste, Regelprofile und Freigaben.
Beide HTTP-Importwege akzeptieren Ist/Soll und weisen `both` als Referenz zurück.

Die [Änderungen aus 0.9.14](release-0.9.14.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
