# Version 0.12.0 – persönliche Arbeit im Planungszeitraum

Diese Freigabe baut auf 0.11.0 auf. Sie ändert keine Benutzerinstallation
automatisch und lockert keine harte Regel. Gespeicherte Projekte bleiben
unverändert; die neue Auslegung entsteht bei einem erneuten Import.

## Sonderdienste im Zeitraum werden nicht mehr verworfen

- Ein SPSHI-Sonderdienst im Planungszeitraum, dessen Zeiten oder bezahlte Dauer
  von der Katalogschicht abweichen, hatte bisher keine Darstellung. Er wurde
  als offene Angabe gemeldet und dann verworfen. Wer die Angabe als geprüft
  markierte, verlor die Stunden vollständig – und die Planung durfte die Person
  in einen Dienst einteilen, der mit ihrer tatsächlichen Arbeit kollidiert.
- Solche Dienste werden jetzt als persönliche Arbeit im Zeitraum übernommen.
  Sie tragen die Zeiten und bezahlten Minuten der Quelle, sperren die Person
  wie jeder andere Dienst und zählen auf das Periodensoll.
- Sie decken **keinen** Besetzungsbedarf und erzeugen keine Einteilung. Eine
  offene Stelle bleibt sichtbar offen.
- Nur ein mit der Katalogschicht identischer Dienst wird weiterhin einem Bedarf
  zugeordnet. Fehlen Zeiten oder ist die Detailzuordnung mehrdeutig, bleibt die
  Angabe unverändert offen.
- Der Import meldet die Anzahl der so übernommenen Dienste als Importangabe und
  hinterlegt sie in `metadata.personal_period_work`.

## Darstellung und Datenvertrag

- Der Plankalender zeigt persönliche Arbeit als eigenes Feld mit Name und
  Uhrzeit. Ein nicht verfügbarer Tag ist damit erklärbar, ohne ihn mit einer
  Einteilung zu verwechseln.
- `BoundaryWork` erhält `in_period`, `paid_minutes` und `holiday`. Die Standard-
  werte erhalten jedes bestehende Projekt und die strenge Regel, dass Randarbeit
  außerhalb des Planungszeitraums beginnen muss, unverändert.

## Prüfstand und Grenzen

- 1328 Tests, Ruff, Release-Provenienz und acht Browserabläufe laufen grün.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate: offene „Sonderdienst“-Angaben fallen von 42 auf 15; 28 Dienste bei
  22 Personen werden mit 265 zuvor unsichtbaren bezahlten Stunden modelliert.
  Ein Plan ohne diese Modellierung teilte 7 Personen in Dienste ein, die mit
  ihrer tatsächlichen Arbeit kollidieren – mit ihr sind es 0.
- Die Dienstart persönlicher Arbeit ist kein Quellnachweis für Tag oder Nacht
  und muss wie bisher bestätigt werden.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
