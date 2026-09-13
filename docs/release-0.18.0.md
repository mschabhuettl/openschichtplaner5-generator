# Version 0.18.0 – Einzeln liegende Arbeitstage vermeiden

Diese Freigabe baut auf 0.17.0 auf. Sie ändert keine harte Regel, keinen Bedarf
und keine Freigabe. Gespeicherte Projekte bleiben unverändert.

## Warum ein automatischer Plan zersplitterte

- Das bisherige weiche Blockziel `workday_transitions` zählt Wechsel zwischen
  Arbeits- und freien Kalendertagen. Ein Block kostet dabei immer zwei Wechsel,
  unabhängig von seiner Länge. Ein einzelner Arbeitstag und ein Zweierblock sind
  damit gleich teuer; gegen isoliert liegende Arbeitstage gab es keinen
  gezielten Anreiz.
- An echten Quelldaten geprüft war das kein Zwang, sondern eine Lücke im Modell:
  Von 70 einzeln liegenden Arbeitstagen war nur bei fünf die eingeteilte Person
  der einzig mögliche Kandidat. 56 waren frei wählbar.

## Das neue Ziel

- `objectives.isolated_days` bestraft genau einen Arbeitstag, dessen Vor- und
  Folgetag beide frei sind. Randtage werden wie beim vorhandenen Blockziel
  behandelt, einschließlich bekannter Dienste unmittelbar vor und nach dem
  Zeitraum.
- Neue Importe und Projektanlagen beginnen mit Gewicht 1000. Beim Laden älterer
  Projekte ohne dieses Feld gilt 0, das Ziel bleibt dort also abgeschaltet.
- Der Ergebnisbericht weist den ungewichteten und gewichteten Beitrag unter
  `isolated_days` aus. Das Ziel bleibt weich: Es garantiert keine
  Mindestblocklänge.

## Prüfstand und Grenzen

- 1397 Tests, Ruff, Release-Provenienz und acht Browserabläufe laufen grün. Die
  neuen Tests schlagen ohne die Änderung fehl, darunter ein Fall, in dem
  dieselbe Stundenzahl entweder als zwei Einzeltage oder als zusammenhängender
  Block erfüllbar ist.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate: Mit vollständiger historischer Freigabebasis sinkt der Anteil
  einzeln liegender Arbeitstage von 43 auf 34 Prozent, ohne dass die Besetzung
  leidet; sie liegt mit 371 statt 370 Einteilungen minimal höher.
- **Wichtig für die Auslegung:** Eine breitere Freigabebasis allein verschlechtert
  die Dienstform. Mehr Freigaben geben der Optimierung mehr Wege, das
  Periodensoll durch dünnes Verteilen auf mehr Personen zu bedienen. Erst
  zusammen mit diesem Ziel entsteht der Gewinn.
- **Offene Grenze:** Der erzeugte Plan bleibt kleinteiliger als ein von Hand
  erstellter. Im geprüften Zeitraum stehen 34 Prozent einzeln liegende
  Arbeitstage gegen 23 Prozent und eine mittlere Blocklänge von 2,22 gegen 2,48
  Tagen. Es fehlen vor allem Blöcke von drei und vier Tagen. Die Arbeit daran
  ist nicht abgeschlossen.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
