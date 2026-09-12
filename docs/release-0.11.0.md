# Version 0.11.0 – Team als Tabelle pflegen und Engpässe je Dienst sehen

Diese Freigabe baut auf 0.10.0 auf. Sie ändert keine Benutzerinstallation
automatisch, lockert keine harte Regel und ergänzt keine Freigaben, Bedarfe
oder Quellwerte.

## Team als Tabelle bearbeiten

- Das geladene Team lässt sich als CSV herunterladen: Semikolon und BOM, damit
  Excel die Datei in der eigenen Spracheinstellung öffnet. Enthalten sind
  Kennung, Name, Team- und Profilkennungen, Sollminuten im Planungszeitraum
  und vertragliche Wochenminuten.
- Eine bearbeitete Datei wird zuerst geprüft und als Vorschau gezeigt: wie
  viele Zeilen gelesen wurden, welche Personen sich ändern, was unverändert
  bleibt und welche Zeilen zu korrigieren sind.
- Bearbeitet werden ausschließlich vorhandene Personen. Eine unbekannte
  Kennung legt niemanden an und blockiert die Übernahme. Eine fehlende Zeile
  löscht niemanden. Dienstfreigaben, Qualifikationen, Verfügbarkeiten,
  Abwesenheiten und Einteilungen bleiben unverändert.
- Unbekannte Team- oder Profilkennungen, leere Pflichtfelder und nicht ganze
  Minutenzahlen werden je Zeile gemeldet; jede Meldung blockiert die Übernahme.
- Eine Vorschau, die vor einer anderen Änderung erstellt wurde, kann nicht
  übernommen werden. Die Übernahme ersetzt kein Speichern.

## Besetzungsengpässe je Dienst

- Über den einzelnen Engpassmeldungen steht jetzt eine Zusammenfassung je
  Dienst: betroffene Bedarfe, offene Stellen und wie viele Personen überhaupt
  eine Freigabe für diesen Dienst besitzen.
- Die Zahl der Freigegebenen trennt zwei Ursachen, die in der Liste gleich
  aussehen: Ohne freigegebene Person fehlt eine Entscheidung in der
  Teammatrix; mit freigegebenen Personen und trotzdem offenen Bedarfen liegt
  ein Kapazitäts-, Ruhe- oder Verfügbarkeitskonflikt vor.
- Ein Schaltknopf öffnet die Freigabematrix gefiltert auf den Dienst. Die
  Zusammenfassung erteilt keine Freigabe und ändert keinen Bedarf.

## Prüfstand und Grenzen

- 1319 Tests, Ruff, Release-Provenienz und sieben Browserabläufe laufen grün.
- Auf einer privaten lokalen Abnahme gegen echte Quelldaten fassen sich 153
  Engpassmeldungen zu 15 Dienstzeilen zusammen; acht davon haben keine einzige
  freigegebene Person. Veröffentlicht werden nur nicht identifizierende
  Aggregate.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
