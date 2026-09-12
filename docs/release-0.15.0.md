# Version 0.15.0 – Bedarf und Vergleichsplan gegenüberstellen

Diese Freigabe baut auf 0.14.0 auf. Sie ändert keine Benutzerinstallation
automatisch, ändert keinen Bedarf, erteilt keine Freigabe und lockert keine
harte Regel. Sie stellt ausschließlich eine bisher fehlende Angabe bereit.

## Die fehlende Hälfte einer Gegenüberstellung

- Der Import liest zwei Sichten auf denselben Zeitraum: den Besetzungsbedarf aus
  der Bedarfstabelle und den Vergleichsplan mit dem tatsächlichen Dienstgeschehen.
- Laufen beide auseinander, wurde bisher nur eine Richtung gemeldet: Dienste, die
  gearbeitet werden, ohne dass ein Bedarf sie fordert. Das zeigt die Übersicht
  der importierten Vergleichsdienste.
- Die andere Richtung fehlte vollständig. Dienstarten mit Mindestbesetzung, die
  im Vergleichsplan überhaupt nicht vorkommen, blieben unbenannt. Wer den Plan
  rechnete, sah viele offene Stellen und konnte nicht erkennen, dass die Quelle
  diese Dienste im Zeitraum gar nicht fährt.
- Anzahl der Dienstarten und Summe der Pflichtplätze stehen jetzt in
  `metadata.demanded_without_reference` und werden als eine einzige Sammelangabe
  gemeldet, ohne Namen und ohne Einzelaufzählung.

## Bewusste Einschränkung

- Wurde kein Vergleichsplan gelesen, ist der Vergleich wertlos und würde jeden
  geforderten Dienst fälschlich als fehlend ausweisen. In diesem Fall bleiben
  beide Werte 0 und es wird nichts gemeldet.
- Bedarfe mit Mindestbesetzung 0 zählen nicht mit; sie fordern keine Besetzung.

## Prüfstand und Grenzen

- 1349 Tests, Ruff, Release-Provenienz und acht Browserabläufe laufen grün. Die
  neuen Tests decken übereinstimmenden, teilweise übereinstimmenden, fehlenden
  und leeren Vergleichsplan ab und schlagen ohne die Änderung fehl.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate: 13 der 22 geforderten Dienstarten kommen im Vergleichsplan nicht
  vor; sie tragen 186 der 310 Pflichtplätze. Der Wert ist unabhängig von der
  Teamauswahl identisch. Bedarfe und Personenzahl bleiben unverändert, es kommt
  genau eine Angabe hinzu.
- Diese Angabe erklärt offene Stellen, sie behebt sie nicht. Ob Bedarfstabelle
  oder Vergleichsplan der Wirklichkeit entspricht, entscheidet die Fachseite.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
