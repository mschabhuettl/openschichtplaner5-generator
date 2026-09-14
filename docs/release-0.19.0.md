# Version 0.19.0 – Dienstpläne, die der Form handgemachter Pläne entsprechen

Diese Freigabe baut auf 0.18.0 auf. Sie ändert keine harte Regel, keinen Bedarf
und keine Freigabe. Gespeicherte Projekte behalten ihre Gewichte und damit ihr
Verhalten.

## Woran ein automatischer Plan noch zu erkennen war

Gegen einen von Hand erstellten Vergleichsplan gemessen, blieben drei Unterschiede:

- **Blockform.** Im Vergleichsplan haben 78 Prozent der Blöcke die Länge zwei bis
  vier, die mittlere Länge beträgt 2,66 Tage, der längste Block sieben Tage. Der
  erzeugte Plan kam auf 58 Prozent, 3,06 Tage und Blöcke bis elf Tage. Ursache
  war das Zusammenspiel zweier Ersatzgrößen: `workday_transitions` bestraft jeden
  Wechsel und belohnt damit monoton immer längere Blöcke, `isolated_days`
  bestraft allein die Länge eins. Nach oben bremste nichts.
- **Wochenenden.** Im Vergleichsplan liegen Samstag und Sonntag fast immer
  zusammen; geteilt wird nur so oft, wie der unterschiedliche Bedarf beider Tage
  es erzwingt. Das Modell kannte diese Kopplung nicht: es zählte je Woche nur, ob
  überhaupt ein Wochenenddienst anfiel. Ein einzelner Samstag war damit der
  billigste Weg, eine Wochenendlast zu verteilen.
- **Ausschöpfung.** Die eingebaute Suche kam an Wochenendpaaren nicht weiter,
  weil dafür viele Einteilungen gleichzeitig zu tauschen wären.

## Was sich geändert hat

- **`objectives.split_weekends`** bestraft ein Wochenende, an dem eine Person
  genau einen der beiden Tage arbeitet, obwohl an beiden Tagen Arbeitsmöglichkeit
  besteht und beide Tage im Zeitraum liegen. Gezählt wird nach dem Tag, an dem
  ein Dienst **beginnt**: ein Dienst von Freitagabend bis Samstagfrüh ist kein
  Samstagsdienst.
- **`objectives.block_shape`** bewertet je abgeschlossenem Block dessen Länge
  anhand eines Kostenprofils. Das Profil stammt aus der beobachteten Verteilung
  des Vergleichsplans: die häufigste Länge kostet nichts, seltenere Längen kosten
  nach ihrer negativen Log-Wahrscheinlichkeit. Umgesetzt als Zustandsautomat über
  Tabellenbedingungen; der Startzustand kommt aus der persönlichen Randarbeit vor
  dem Zeitraum. Eine harte Obergrenze für Blocklängen entsteht dadurch nicht und
  wird auch nicht angenommen.
- **Reparaturphase.** Nach den beiden bisherigen Suchphasen wird abwechselnd ein
  Wochenende samt Freitag und Montag oder werden die Pläne von bis zu sechs
  Personen wieder freigegeben und dieser Ausschnitt neu gelöst. Übernommen wird
  nur, was zuerst weniger fehlende Mindeststellen und danach eine geringere
  gewichtete Bewertung erreicht. Damit dafür Zeit bleibt, erhalten die beiden
  Suchphasen ab 120 Sekunden Teilplanung zusammen 40 Prozent der Frist.
- **Berichte.** Fehlende Vertragswochenstunden werden im Importbericht benannt,
  samt der Klarstellung, dass daraus keine Obergrenze abgeleitet wird. Die
  Vorabprüfung auf private Daten weist übersprungene Pfade aus, damit eine
  vertippte Option die Prüfung nicht stillschweigend verkürzt.

## Prüfstand und Grenzen

- Vollständige Testsuite und Ruff laufen grün. Die neuen Tests schlagen ohne die
  jeweilige Änderung fehl; bei der Wochenendkopplung fällt ohne sie genau der
  Test, der die Kopplung nachweist, bei der Zählweise fallen beide Tests zur
  Nachtdienstabgrenzung.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate. Die Blockform entspricht dem Vergleichsplan: mittlere Blocklänge
  2,66 gegen 2,66 Tage, Anteil der Längen zwei bis vier 82 gegen 78 Prozent,
  keine Blöcke ab sechs Tagen gegen einen. Die Reparaturphase senkt bei 300
  Sekunden die fehlenden Mindeststellen von 51 auf 10.
- **Wichtig für die Auslegung:** Die Messgrößen streuen zwischen Läufen erheblich,
  weil die Abbruchgrenze eine Wanduhr ist. Derselbe Code liefert für den Anteil
  einzeln liegender Arbeitstage Werte zwischen 17 und 33 Prozent. Einzelne Läufe
  taugen nicht als Beleg; die hier genannten Aussagen beruhen auf mehreren Läufen
  je Einstellung.
- **Offene Grenze:** Die Wochenendkopplung erreicht den Vergleichsplan nicht. Dort
  sind 10 Prozent der Wochenenden geteilt, im erzeugten Plan 23 bis 30 Prozent.
  Ein höheres Gewicht auf der Kopplung verschlechtert zugleich die Blockform. Die
  Arbeit daran ist nicht abgeschlossen.
- **Zweite offene Grenze:** Der Vergleichsplan ist unter den harten Regeln dieses
  Programms nicht zulässig. 28 seiner 385 Einteilungen setzen Personen auf
  Dienste, für die keine Freigabe vorliegt und die auch in drei Jahren Historie
  nicht vorkommen. Eine vollständige Nachbildung ist damit ausgeschlossen; neun
  dieser Abweichungen liegen am Wochenende.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
