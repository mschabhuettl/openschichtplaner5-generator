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
  anhand eines Kostenprofils. Das Profil ist am Zweck geeicht, nicht an der
  Vorlage: zusammenhängende Freizeit entsteht aus wenigen, längeren Dienstblöcken,
  weil beide sich denselben Zeitraum teilen. Vier bis fünf Tage kosten daher
  nichts, einzelne Arbeitstage sind teuer, ab sieben Tagen steigen die Kosten
  wieder. Umgesetzt als Zustandsautomat über Tabellenbedingungen, der bis neun
  Tage unterscheidet; der Startzustand kommt aus der persönlichen Randarbeit vor
  dem Zeitraum. Eine harte Obergrenze für Blocklängen entsteht dadurch nicht und
  wird auch nicht angenommen. Die harte Wochenruhe allein genügt als Bremse
  nicht: sie lässt rechnerisch bis zu zwölf Tage am Stück zu.
- **Geeichte Vorbelegungen.** Die Gewichte neuer Importe und Projektanlagen waren
  nie aufeinander abgestimmt; an echten Quelldaten trug ein Ziel 286.000 Punkte
  zur Gesamtwertung bei, ein anderes 6.400. Sie sind nun so gesetzt, dass die
  Ziele vergleichbare Beiträge leisten. Gespeicherte Projekte behalten ihre
  gespeicherten Gewichte.
- **Reparaturphase.** Nach den beiden bisherigen Suchphasen wird abwechselnd ein
  Wochenende samt Freitag und Montag oder werden die Pläne von bis zu sechs
  Personen wieder freigegeben und dieser Ausschnitt neu gelöst. Übernommen wird
  nur, was zuerst weniger fehlende Mindeststellen und danach eine geringere
  gewichtete Bewertung erreicht. Damit dafür Zeit bleibt, erhalten die beiden
  Suchphasen ab 120 Sekunden Teilplanung zusammen 40 Prozent der Frist.
- **Vertragswochenstunden bei Tagesbasis.** Das Feld wurde bisher nur gesetzt,
  wenn die Quelle die Woche als Bemessungsgrundlage führt. An echten Quelldaten
  traf das auf 15 von 88 Personen zu; das weiche Ziel zur Verteilung über die
  Kalenderwochen wirkte damit für ein Sechstel der Belegschaft. Bei Tagesbasis
  wird nun dieselbe Formel verwendet wie in der Quellenbibliothek: Tagessoll je
  Arbeitstag laut Wochentagsmaske, gezählt von Montag bis Sonntag. Die
  Wochenstunden der Quelle bleiben dort ungenutzt, weil sie bei 19 von 88
  Personen um bis zu 35 Stunden von dieser Rechnung abweichen. Monats- und
  Gesamtbasis bleiben ohne Wert; dort wird nichts heruntergerechnet. Die
  Abdeckung steigt damit von 15 auf 87 von 88 Personen.
- **Freizeitstruktur im Bericht.** Der Ergebnisbericht maß bisher nur die
  Dienstseite. Ob ein Plan zusammenhängende Freizeit lässt, war daran nicht
  abzulesen. Ausgewiesen werden nun Anzahl und mittlere Länge der
  Freizeitblöcke, einzeln liegende freie Tage, Blöcke ab drei Tagen, der längste
  Block und die Zahl vollständig freier Wochenenden. Die Kennzahlen berichten
  und steuern nicht.
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
  Aggregate, gemessen gegen einen von Hand erstellten Plan desselben Zeitraums:
  einzeln liegende Arbeitstage 8 gegen 17 Prozent, mittlere Länge der
  zusammenhängenden Freizeit 3,13 gegen 2,50 Tage, Erholungsblöcke ab drei freien
  Tagen 46 gegen 31 Prozent, vollständig freie Wochenenden je Person 1,23 gegen
  1,20, Ausgeglichenheit der Wochenendlast 0,021 gegen 0,109, Regelbefunde keine
  gegen 39. Die Reparaturphase senkt bei 300 Sekunden die fehlenden
  Mindeststellen von 51 auf 10.
- **Wichtig für die Auslegung:** Die Messgrößen streuen zwischen Läufen erheblich,
  weil die Abbruchgrenze eine Wanduhr ist. Derselbe Code liefert für den Anteil
  einzeln liegender Arbeitstage Werte zwischen 17 und 33 Prozent. Einzelne Läufe
  taugen nicht als Beleg; die hier genannten Aussagen beruhen auf mehreren Läufen
  je Einstellung.
- **Zur Einordnung:** Der Vergleichsplan ist eine Referenz, kein Zielbild. Gemessen
  am Zweck des Programms steht der erzeugte Plan bei der zusammenhängenden
  Freizeit besser da: mittlere Freizeitblocklänge 3,0 bis 3,2 gegen 2,5 Tage,
  Anteil der Blöcke ab drei freien Tagen 41 gegen 31 Prozent, vollständig freie
  Wochenenden je Person 1,25 gegen 1,20. Auch die Ausgeglichenheit ist besser
  (Gini 0,04 gegen 0,11), und es bleiben keine Regelbefunde gegen 39.
- **Wochenendkopplung als Rangstufe.** Die Regel, dass ein Wochenende ganz oder
  gar nicht gearbeitet wird, ist kein gewichtetes Ziel mehr, sondern eine eigene
  Stufe zwischen Abdeckung und Qualität. Ein höheres Gewicht hatte zuvor nicht
  geholfen: 30000 schnitt schlechter ab als 10000, der Unterschied lag in der
  Laufstreuung. An echten Quelldaten sinkt die Zahl geteilter Wochenenden damit
  von 13 bis 17 auf 7 von 45, und zwei Läufe liefern zeichengleiche Ergebnisse —
  die Stufe macht diese Größe reproduzierbar.
- **Erreichbare Grenze:** 7 geteilte Wochenenden sind unter den geltenden
  Freigaben das Minimum. Bei fünf davon ist die eingeteilte Person am jeweils
  anderen Tag nicht einsetzbar. Eine Variante, die auch solche Fälle bestraft,
  kommt auf dieselben 7 und verschlechtert dabei die Ausgeglichenheit; sie wurde
  verworfen. Der Vergleichsplan liegt mit 5 darunter, nimmt dafür aber 28
  Zuteilungen ohne gültige Freigabe vor, neun davon am Wochenende. Gemessen an
  den vermeidbaren Teilungen liegt der erzeugte Plan mit 2 besser als der
  Vergleichsplan mit 4.
- **Zweite offene Grenze:** Der Vergleichsplan ist unter den harten Regeln dieses
  Programms nicht zulässig. 28 seiner 385 Einteilungen setzen Personen auf
  Dienste, für die keine Freigabe vorliegt und die auch in drei Jahren Historie
  nicht vorkommen. Eine vollständige Nachbildung ist damit ausgeschlossen; neun
  dieser Abweichungen liegen am Wochenende.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
