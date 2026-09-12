# Version 0.17.0 – Strukturell unerreichbares Periodensoll benennen

Diese Freigabe baut auf 0.16.0 auf. Sie ändert keine Suche, keinen Bedarf, keine
Freigabe und keine harte Regel. Sie macht eine bisher unsichtbare Ursache
sichtbar.

## Warum viele Personen unter Soll bleiben

- Das Periodensoll einer Person stammt aus der Quelle und gilt für ihre gesamte
  Arbeit. Geplant wird aber immer nur ein Zuschnitt: ausgewählte Teams, deren
  Bedarfe, und nur Dienste, für die die Person freigegeben ist.
- Übersteigt das Soll das, was dieser Zuschnitt überhaupt hergibt, kann keine
  Einteilung den Rückstand beheben. Bisher blieb er unerklärt und ließ sich
  leicht für ein Planungsversagen halten.

## Was jetzt berichtet wird

- Der Solver führt je Person `reachable_minutes` mit: die bezahlten Minuten
  aller Bedarfe im Planungszeitraum, für die die Person ohne Ausschlussgrund
  einsetzbar ist, zuzüglich ihrer persönlichen Arbeit im Zeitraum.
- Liegt das Periodensoll darüber, meldet das Ergebnis je betroffener Person die
  Diagnose `target_unreachable`, ohne Namen.
- Die Diagnose ist rein berichtend wie die Engpassdiagnosen. Sie macht kein
  Ergebnis ungültig und ändert keine Einteilung.

## Prüfstand und Grenzen

- 1379 Tests, Ruff, Release-Provenienz und acht Browserabläufe laufen grün. Die
  neuen Tests schlagen ohne die Änderung fehl.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate: 25 von 81 Personen mit Periodensoll erreichen es im geprüften
  Zuschnitt strukturell nicht; der unvermeidbare Rückstand beträgt 1429 Stunden.
  Das Ergebnis bleibt dabei gültig.
- **Offene Grenze bei der Dienstform, unverändert seit 0.16.0:** Der erzeugte
  Plan zerfällt stärker in Einzeltage als der menschlich erstellte, im geprüften
  Zeitraum 34 bis 38 Prozent gegenüber 24 Prozent. Fünf Stellschrauben wurden
  gemessen: Parallelsuche bringt drei Prozent besseren Zielwert bei gleicher
  Schranke und kostet die Reproduzierbarkeit; veränderte Zielgewichte bewegen
  höchstens vier Prozentpunkte; eine größere Qualitätsphase kostet Besetzung,
  ohne die Blöcke zu verbessern; die importierte Grundlage zu behalten
  verschlechtert sie. Wirksam ist allein mehr Rechenzeit.
  Die Ursache ist benannt: Das unerreichbare Soll macht über die Hälfte der
  gewichteten Zielsumme aus und zieht mehr Personen in den Plan, als die Arbeit
  trägt. Diese Freigabe behebt das nicht, sie macht es sichtbar.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
