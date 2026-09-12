# Version 0.16.0 – Bedarf aus dem beobachteten Plan ableiten

Diese Freigabe baut auf 0.15.0 auf. Sie ändert keine Benutzerinstallation
automatisch und lockert keine harte Regel. Die Vorgabe bleibt unverändert; die
neue Auslegung entsteht nur bei ausdrücklicher Wahl und erneutem Import.

## Warum ein automatischer Plan die Wirklichkeit bisher nicht traf

- Der Generator konnte nur besetzen, was die Bedarfstabelle der Quelle fordert.
- In realen Beständen laufen Bedarfstabelle und gelebter Dienstplan auseinander.
  In der geprüften Quelle ließen sich von 385 tatsächlich gearbeiteten Diensten
  eines Zeitraums nur 101 einem Bedarf zuordnen; umgekehrt blieben 235 der 310
  geforderten Pflichtplätze auch im echten Plan unbesetzt.
- Ein automatisch erzeugter Plan konnte die tatsächliche Dienstform deshalb
  nicht erreichen, unabhängig davon, wie gut gerechnet wird.

## Die zweite Bedarfsquelle

- Im Import lässt sich der Besetzungsbedarf jetzt wahlweise aus dem beobachteten
  Vergleichsplan des Zeitraums ableiten statt aus der Bedarfstabelle.
- Je Dienst, Arbeitsplatz und Tag zählt die beobachtete Besetzung als Unter- und
  Obergrenze. Das ist eine Ableitung aus der Quelle, keine erfundene Grenze, und
  wird als Importangabe ausdrücklich gemeldet.
- Dienstarten, für die der Katalog keine Zeiten angibt, erzeugen keinen Bedarf;
  sie bleiben persönliche Arbeit ohne Zeiten wie bisher.
- Anzahl, Pflichtplätze und übersprungene Zellen stehen in
  `metadata.observed_demand`.
- Freigaben, Qualifikationen, Regelprofile, Abwesenheiten und Randkontext werden
  davon nicht berührt. Es wird nichts erfunden und nichts bestätigt.

## Vorgabe unverändert

- Ohne ausdrückliche Wahl bleibt die Bedarfstabelle der Quelle maßgeblich.
- Gegen echte Quelldaten geprüft: derselbe Import liefert im Standardweg
  unverändert dieselben Personen, Positionen, Dienste, Bedarfe, Einteilungen,
  Randarbeiten und dieselbe Summe der Pflichtplätze wie vor dieser Freigabe.

## Prüfstand und Grenzen

- 1371 Tests, Ruff, Release-Provenienz und acht Browserabläufe laufen grün.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate: Mit abgeleitetem Bedarf entstehen 357 Bedarfszellen mit 385
  Pflichtplätzen, keine übersprungen. Der erzeugte Plan erreicht 376 der 385
  Personentage des echten Plans, also 98 Prozent; zuvor waren es 247, also
  64 Prozent.
- **Offene Grenze bei der Dienstform:** Der erzeugte Plan zerfällt stärker in
  Einzeltage als der menschlich erstellte. Im geprüften Zeitraum sind 38 Prozent
  der Blöcke Einzeltage gegenüber 24 Prozent im echten Plan. Ursachen sind die
  Skalierung der Ziele – die Stundenabweichung zählt je Minute, ein Blockwechsel
  je Wechsel – und die begrenzte Suchtiefe. Das ist noch nicht behoben.
- Ob der beobachtete Plan der gewünschte Bedarf ist, entscheidet die Fachseite.
  Die Ableitung bildet ab, was war, nicht was sein soll.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
