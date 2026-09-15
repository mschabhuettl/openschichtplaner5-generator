# Version 0.22.0 – Der Freitagnachtdienst greift ins Wochenende ein

Diese Freigabe baut auf 0.21.0 auf. Sie ändert keine harte Regel, keinen Bedarf
und keine Freigabe. Sie ändert aber die **Zählweise** des weichen Ziels
`split_weekends` und damit die erzeugten Pläne. Gespeicherte Projekte behalten
ihre Gewichte; das Ziel wirkt ab jetzt anders.

## Die Frage, die dahinter stand

Ein Dienst von Freitagabend bis Samstagfrüh: Ist das ein Wochenenddienst? Bis
0.21.0 lautete die Antwort nein. Gezählt wurde nach dem Tag, an dem ein Dienst
**beginnt** – der Freitagnachtdienst begann am Freitag und machte den Samstag
nicht zum Wochenenddienst.

Das war innerhalb des Modells widerspruchsfrei, aber es widersprach dem Bericht
desselben Programms: Die Freizeitkennzahlen zählen einen Tag als belegt, sobald
ein Dienst ihn **berührt**. Ein Freitagnachtdienst zerstörte dort das freie
Wochenende, während das Kopplungsziel ihn gar nicht sah. Die Optimierung war für
genau das blind, was der Bericht anschließend maß.

## Was sich geändert hat

- **`objectives.split_weekends` zählt nach berührten Tagen.** Ein Wochenende
  gilt als geteilt, wenn genau einer der beiden Tage von einem Dienst berührt
  wird. Ein Freitagnachtdienst belegt damit den Samstag, ein Samstagnachtdienst
  belegt Samstag und Sonntag und ist für sich genommen kein geteiltes Wochenende.
- **Befund, gezählte Gesamtzahl und Bedarfs-Untergrenze folgen derselben
  Zählweise.** Für die Untergrenze belegt ein Dienst jeden Tag, den er berührt:
  ein Freitagnachtdienst zählt zur Samstagsbesetzung.
- Damit sind Ziel, Befund und Bericht zum ersten Mal auf derselben Zählweise.

## Gemessen an echten Quelldaten

Drei Läufe je Variante, je 600 Sekunden, identische Eingaben, nur nicht
identifizierende Aggregate. „Geteilt" und „ganz frei" sind nach berührten Tagen
gezählt, für alle Pläne gleich:

| Plan | geteilte Wochenenden | vollständig freie Wochenenden |
|---|---|---|
| Vergleichsplan von Hand | 5 | 71 |
| bisher (Zählung nach Dienstbeginn) | 9 / 7 / 8 | 66 / 68 / 67 |
| neu (Zählung nach berührten Tagen) | **3 / 2 / 2** | **69 / 74 / 69** |

Der erzeugte Plan liegt damit bei den geteilten Wochenenden **unter** dem
Vergleichsplan und bei den vollständig freien Wochenenden gleichauf. Die
Besetzung bleibt unverändert (375 bis 377 Einteilungen gegenüber 376 bis 377),
die Ausgeglichenheit verbessert sich (Gini 0,058 bis 0,119 gegenüber 0,071 bis
0,097), die Dienstblöcke werden länger (Schnitt 4,16 gegenüber 3,90 Tage).

Die Abnahme am Produktstand bestätigt das: 2 geteilte Wochenenden, davon 2 vom
Bedarf erzwungen – **keine vermeidbare Teilung mehr**, und die gewichtete Wertung
weist 0 als bewiesenes Optimum aus. 70 vollständig freie Wochenenden.

## Zur Einordnung des alten Ergebnisses

Die in 0.19.0 und 0.20.0 genannte bewiesene Untergrenze von 7 geteilten
Wochenenden galt für die alte Zählweise nach Dienstbeginn. Sie war für jenes
Modell korrekt und ist jetzt gegenstandslos: Nach berührten Tagen sind es 2, und
beide erzwingt der Bedarf.

## Prüfstand und Grenzen

- Vollständige Testsuite, Ruff und der Browserdurchlauf laufen grün. Vier Tests,
  die die alte Zählweise festschrieben, wurden auf die neue Absicht umgeschrieben
  – sie prüfen jetzt, dass ein Freitagnachtdienst den Sonntag an dieselbe Person
  zieht und ein Samstagnachtdienst keinen zusätzlichen Sonntagsdienst braucht.
  Ein neuer Test deckt die Untergrenze mit Nachtdiensten ab.
- **Auswirkung auf gespeicherte Projekte:** Wer `split_weekends` gesetzt hat,
  bekommt ab jetzt andere Pläne. Das ist beabsichtigt; die alte Zählweise bleibt
  nicht als Einstellung erhalten, weil zwei Zählweisen nebeneinander genau den
  Widerspruch erzeugen würden, den diese Freigabe auflöst.
- **Grenze der Messung:** Die Kennzahlen streuen zwischen Läufen; die Aussagen
  hier beruhen auf drei Läufen je Einstellung mit verschiedenen Zufallsstartwerten.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
