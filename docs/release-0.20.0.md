# Version 0.20.0 – Geteilte Wochenenden nachvollziehbar aufschlüsseln

Diese Freigabe baut auf 0.19.0 auf. Sie ändert keine harte Regel, keinen Bedarf,
keine Freigabe und kein Suchverhalten. Gespeicherte Projekte behalten ihre
Gewichte und liefern dieselben Pläne wie zuvor; berichtet wird mehr.

## Warum die bisherige Zahl in die Irre führte

- Der Ergebnisbericht wies unter `split_weekends` nur den Beitrag zur gewichteten
  Wertung aus. Dieses Ziel zählt ein Wochenende aber nur dann, wenn die Person an
  **beiden** Tagen überhaupt einen Dienst beginnen könnte. Wer für den Sonntag
  keine einzige einsetzbare Stelle hat, taucht darin nicht auf.
- An echten Quelldaten stand deshalb eine 2 im Bericht, während der Plan
  tatsächlich 7 geteilte Wochenenden enthielt. Wer die Zahl mit einem von Hand
  erstellten Plan verglich, verglich zwei verschiedene Dinge.
- Zugleich fehlte die wichtigste Auskunft: Ein Teil dieser Teilungen ist
  unvermeidbar. Verlangt der Bedarf am Samstag mehr Besetzungen als der Sonntag
  aufnehmen kann, muss die Differenz an genau einem der beiden Tage arbeiten –
  unabhängig von Freigaben, Gewichten und Rechenzeit.

## Was sich geändert hat

- **`split_weekends_in_plan`** zählt die geteilten Wochenenden des gewählten
  Plans, gleich ob die Wertung sie sehen konnte. Gezählt wird wie bisher nach dem
  Tag, an dem ein Dienst **beginnt**, einschließlich bekannter Randarbeit.
- **`split_weekends_forced_by_demand`** nennt die Zahl, die der Bedarf selbst
  erzwingt: je Wochenende die Differenz zwischen der Mindestbesetzung des einen
  und der Höchstbesetzung des anderen Tages. Ist die Höchstbesetzung offen, gilt
  nichts als erzwungen.
- **Befund `split_weekend_demand`** benennt je betroffenem Wochenende die
  geforderte Samstags- und Sonntagsbesetzung, die daraus folgende Zahl an
  Teilungen und den Weg dahin: Unter Bedarf lassen sich beide Tage angleichen.
- **Klartext im Ergebnis.** Statt nur einer technischen Auswertung stehen zwei
  Sätze im Bericht: die Aufschlüsselung der geteilten Wochenenden und die
  Freizeitstruktur (Blöcke, mittlere Länge, Blöcke ab drei Tagen, einzelne freie
  Tage, vollständig freie Wochenenden). Beide Kennzahlen berichten und steuern
  nicht.

## Richtigstellung zu 0.19.0

Die Releasehinweise zu 0.19.0 verglichen „vermeidbare Teilungen“ mit 2 gegen 4.
Diese Größe misst je Person, ob sie am anderen Tag einsetzbar gewesen wäre. Sie
misst **nicht**, ob die Gesamtzahl sinken könnte: Wird eine Person
zusammengelegt, rückt bei ungleichem Bedarf eine andere nach. Die belastbare
Gegenüberstellung lautet an denselben Quelldaten: Der Bedarf erzwingt 4
Teilungen, der erzeugte Plan erreicht 7, der Vergleichsplan 5 – letzterer
allerdings mit 28 Zuteilungen ohne gültige Freigabe, neun davon am Wochenende.
Die Aussage aus 0.19.0, dass 7 unter den geltenden Freigaben das bewiesene
Minimum sind, bleibt davon unberührt.

## Prüfstand und Grenzen

- Vollständige Testsuite, Ruff und der Browserdurchlauf laufen grün. Die sechs
  neuen Tests und der neue Browserablauf schlagen ohne die jeweilige Änderung
  fehl; geprüft wurde das durch Zurücknehmen der Änderung bei unverändertem Test.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate: 7 geteilte Wochenenden im Plan, davon 4 durch den Bedarf erzwungen
  (Samstag 23 gegen Sonntag 21 und Samstag 22 gegen Sonntag 20), gewichtete
  Wertung 2.
- **Grenze der Aussage:** Die erzwungene Zahl gilt, solange niemand an einem Tag
  zwei Dienste übernimmt. Sie ist eine untere Schranke aus Mindest- und
  Höchstbesetzung, keine Vorhersage des Ergebnisses; der Plan kann darüber
  liegen, nicht darunter.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
