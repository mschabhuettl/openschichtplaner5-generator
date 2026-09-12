# Version 0.14.0 – Beschäftigungszeitraum ernst nehmen

Diese Freigabe baut auf 0.13.0 auf. Sie ändert keine Benutzerinstallation
automatisch, lockert keine harte Regel und verwirft keine Person. Gespeicherte
Projekte bleiben unverändert; die neue Auslegung entsteht bei einem erneuten
Import.

## Zwei Wege, eine Regel

- Historische Dienstfreigaben lassen sich automatisch beim Import oder von Hand
  über die Sammelübernahme bestätigen. Die automatische Übernahme schneidet
  jeden Vorschlag auf die Schnittmenge aus Planungs- und Beschäftigungszeitraum
  zu und verwirft ihn bei leerer Schnittmenge.
- Die Sammelübernahme prüfte den Beschäftigungszeitraum überhaupt nicht. Sie
  legte deshalb Freigaben für Personen an, die im Planungszeitraum nicht mehr
  beschäftigt sind. Einsetzbar waren diese Personen nie – die Freigaben
  erzeugten nur Bestätigungsarbeit und einen falschen Eindruck in der Matrix.
- Beide Wege wenden jetzt dieselbe Regel an.

## Der Import benennt, was er geladen hat

- Alle Personen der gewählten Gruppen werden weiterhin geladen, auch solche,
  deren Beschäftigung den Planungszeitraum nicht berührt. Das ist beabsichtigt:
  Ihre früheren Dienste tragen den Randkontext.
- Bisher wurde das nirgends gemeldet. Wer die Teamliste sah, konnte nicht
  erkennen, dass ein Teil davon im Zeitraum gar nicht einsetzbar ist.
- Die Anzahl steht jetzt in `metadata.not_employed_in_period` und wird als eine
  einzige Sammelangabe gemeldet, ohne Namen und ohne Einzelaufzählung.

## Was ausdrücklich nicht geändert wurde

- Der Ausschluss nicht beschäftigter Personen aus der Besetzung war bereits
  korrekt und bleibt unverändert.
- Ebenso der Ausschluss über die Teamzuordnung. Eine Prüfung an echten
  Quelldaten – einschließlich aller Vor- und Nachfahren in der Gruppen-
  hierarchie – ergab keinen Zuordnungsfehler: Die betroffenen Gruppen stellen
  schlicht keinen Bedarf.

## Prüfstand und Grenzen

- 1345 Tests, Ruff, Release-Provenienz und acht Browserabläufe laufen grün.
  Beide Änderungen sind durch Tests abgesichert, die ohne sie fehlschlagen.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate: 90 der 275 geladenen Personen sind im Zeitraum nicht beschäftigt
  und werden jetzt als eine Angabe gemeldet. Die Sammelübernahme bietet statt
  829 noch 814 Vorschläge an; die 15 entfallenen betrafen ausgeschiedene
  Personen. Die Personenzahl bleibt unverändert, es wird niemand verworfen.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
