# Version 0.24.0 – Den Fehlbetrag teilen, statt ihn einzelnen aufzuladen

Diese Freigabe baut auf 0.23.0 auf. Sie ändert keine harte Regel, keinen Bedarf
und keine Freigabe. Sie ergänzt ein weiches Ziel und eine Kennzahl.

## Warum das bisherige Stundenziel nichts verteilen konnte

`objectives.hours` bestraft je Person den Abstand zwischen geleisteter und
vertraglich geschuldeter Arbeitszeit und summiert diese Abstände.

Genau das kann die Verteilung nicht steuern: Liegt der Bedarf unter der Summe
aller Verträge — wie in jedem der geprüften Zeiträume — dann bleiben alle unter
ihrem Soll, und die Summe der Abstände ist **konstant**. Sie beträgt immer
„Summe der Sollzeiten minus vorhandene Arbeit", ganz gleich, wer arbeitet. Das
Ziel war gegen die Frage, ob eine Person 0 und eine andere 130 Prozent erreicht,
vollständig blind.

An echten Quelldaten: 5 einsetzbare Personen ohne einen einzigen Dienst,
gleichzeitig 15 Personen über 110 Prozent ihres Solls.

## Das neue Ziel

- **`objectives.hours_fairness`** bestraft den Abstand jeder Person zu einem
  **gemeinsamen Erfüllungsgrad**, den die Suche selbst wählt. Damit zählt nicht
  mehr die Summe des Fehlbetrags, sondern seine Verteilung.
- Gerechnet wird in Millionsteln des persönlichen Solls und anschließend in
  Promille bewertet, damit die Größenordnung zu den übrigen Zielen passt.
- **Wer nirgends einsetzbar ist, bleibt außen vor.** Sonst würde eine Person
  ohne jede mögliche Stelle den Maßstab für alle nach unten ziehen, ohne dass
  die Planung daran etwas ändern könnte.
- **Deckel bei 150 Prozent.** Ein einzelnes verzerrtes Periodensoll — in den
  Quelldaten gab es eines mit 14 Stunden gegen einen Median von 80 — darf nicht
  den Maßstab für alle setzen. Ein zu hoher Einsatz bleibt über `hours` bewertet.
- Neue Importe und Projektanlagen beginnen mit Gewicht 30. Gespeicherte Projekte
  ohne dieses Feld behalten 0, das Ziel bleibt dort abgeschaltet.

## Gemessen

Drei Läufe je Gewicht, je 150 Sekunden, identische echte Quelldaten, nur nicht
identifizierende Aggregate. Die 65 einsetzbaren Personen mit Periodensoll:

| Gewicht | Median | unter 50 % | Zielband 90–110 % | über 110 % |
|---|---|---|---|---|
| 0 | 75 % | 8,0 | 10,3 | 15,0 |
| 10 | 82 % | 7,3 | 9,3 | 14,3 |
| **30** | **83 %** | **5,7** | **12,0** | **9,0** |

Die Kosten bleiben im Rauschen: geteilte Wochenenden 2,3 gegen 2,7, mittlere
Freizeitblocklänge 3,04 gegen 2,99 Tage, offene Pflichtstellen unverändert 8.
Gewicht 100 war in einer Vorprüfung schlechter als 30.

## Kennzahl im Bericht

**`hours_attainment`** weist aus, wie gleichmäßig die Verträge erfüllt sind:
Median, niedrigster und höchster Wert sowie die Besetzung der Fächer „ohne
Dienst", „unter 50", „50 bis 89", „90 bis 110" und „über 110" Prozent. Im
Ergebnis steht das als Satz in Klartext. Gezählt wird nur, wer ein Soll hat und
einsetzbar ist.

## Grenzen der Aussage

- **Einzelne Läufe belegen hier nichts.** Eine erste Gegenüberstellung mit je
  zwei Läufen sprach gegen das Ziel; erst drei Läufe je Einstellung zeigten das
  Bild oben. Die parallele Suche ist nicht reproduzierbar.
- Das Ziel verteilt den Fehlbetrag, es schafft keine Arbeit. Personen ohne
  passende Freigabe bleiben ohne Dienst; dafür nennt der Bericht seit 0.21.0 die
  fehlenden Freigaben.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.

## Prüfstand

Vollständige Testsuite, Ruff und dreizehn Browserabläufe laufen grün. Sechs neue
Tests decken ab: geteilter Fehlbetrag bei gleichen Verträgen, die Wirkungslosig-
keit ohne Gewicht, die eigene Ausweisung des Beitrags, den Ausschluss nicht
einsetzbarer Personen aus Ziel und Kennzahl sowie die Kennzahl selbst. Sie
schlagen ohne die Änderung fehl.
