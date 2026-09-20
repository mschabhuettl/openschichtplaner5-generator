# Version 0.25.0 – Mehrere Schichtvarianten für denselben Posten, größere Häuser, weniger im Weg

Diese Freigabe baut auf 0.24.0 auf. Sie ändert keine bestehende Regel und keine
Freigabe. Gespeicherte Projekte behalten ihr Verhalten: das neue Bedarfsfeld ist
leer, und solange es leer ist, zählt jeder Bedarf wie bisher für sich.

## Mehrere Schichtvarianten decken denselben Posten

Ein Nachtdienst wird als 18–06 für Zwölfstundenkräfte und als 20–06 für
Zehnstundenkräfte geführt, besetzt werden muss aber nur **einer** davon. Bisher
ließ sich das nicht ausdrücken: Beide Bedarfe forderten ihre Mindestbesetzung
einzeln, der Plan stellte zwei Personen auf einen Posten für eine.

- **`demand.alternative_group`** fasst Bedarfe zu einem Posten zusammen. Erfüllt
  ist er, sobald die Mitglieder zusammen die höchste geforderte
  Mindestbesetzung erreichen. Eine zweite Person auf der anderen Variante bleibt
  erlaubt; die Höchstbesetzung gilt weiter je Bedarf einzeln.
- Eingetragen wird die Kennung unter **Regeln → Einzelne Bedarfe**, Spalte
  „Selber Posten".
- **Ein leerer Posten wird einmal gemeldet, nicht je Variante.** Der Fehlbestand
  wurde an drei Stellen getrennt gerechnet — Suche, unabhängige Prüfung und
  Export. Diese drei Rechnungen sind jetzt eine gemeinsame Regel
  (`domain.staffing_gaps`); vorher wäre derselbe Posten dreifach als unbesetzt
  erschienen.

Offen bleibt die zweite Hälfte des Falls: Wer welche Variante übernehmen darf,
entscheidet heute die Freigabe, nicht die vertragliche Tagesdauer. Die Quelle
führt diesen Wert, der Import verrechnet ihn bisher nur in die Wochenstunden.

## Größere Häuser

Die Grenze von 1000 Positionen wies eine Organisation mit 1112 Positionen ab,
obwohl die eigentlich bindenden Grenzen weit entfernt waren: Personen mal
Bedarfe (2 000 000, im gemessenen Fall 358 000) und Einteilungen (5000).

Gemessen an echten Quelldaten, nur nicht identifizierende Aggregate: 275
Personen, 1112 Positionen, 1303 Bedarfe rechnen in 886 Sekunden zu 1083
Einteilungen; die unabhängige Prüfung bestätigt den Plan als **gültig**. Die
Grenze steht daher auf 2000, der gemessene Fall ist als Test festgehalten.

## Fehlermeldungen, die den Grund nennen

`team_id` und `team_ids` gleichzeitig anzugeben erzeugte die Meldung
„API-Daten sind mit dem Importvertrag nicht kompatibel; Felder und Zeitangaben
lokal prüfen" — und schickte die Suche damit an die falsche Stelle. Der
Widerspruch wird jetzt vorab benannt. Bleibt eine Ausnahme unerwartet, nennt die
Meldung zusätzlich die **Stufe**: Zugang, Gruppenauswahl, Planungsdaten oder
Historie. Quellwerte stehen bewusst nicht darin; sie könnten personenbezogen sein.

## Weniger im Weg

- **Bedarfsseite.** Die Anleitung (153 Wörter) steht hinter „Wie das Eintragen
  funktioniert", die Sammelbearbeitung je Zeile hinter „Ganze Zeile setzen".
  Eine Bedarfszeile war dadurch rund 230 Pixel hoch; die Seite ist von 1163 auf
  580 Pixel geschrumpft und passt in ein Bild.
- **Freigabematrix.** Die Zellen zeigen das Zeichen statt des Wortlauts; der
  volle Text bleibt als zugänglicher Name und als Kurzhinweis. Je Person steht
  die Bilanz „3/12", und ein Filter zeigt wahlweise nur Personen mit fehlender
  Freigabe, mit offenem Vorschlag oder von der Planung ausgenommene. Mit zwölf
  Dienstarten gemessen: Zeilenhöhe 71 auf 33 Pixel, sichtbare Personen 8 auf 17.
- **Tabellenköpfe.** Bezeichnung und Zusatz liefen zusammen („Dienst A08:00–13:00",
  „Mo05.01.2026") und stehen jetzt untereinander.
- **Kopfleiste ohne Projekt.** Sie zeigte „Projekt benennen · 0 Tage ·" und
  „0 Personen · 0 % belegt" und bleibt nun leer.

## Prüfstand und Grenzen

- Vollständige Testsuite, Ruff und dreizehn Browserabläufe laufen grün. Die
  neuen Tests schlagen ohne die jeweilige Änderung fehl, geprüft durch
  Zurücknehmen bei unverändertem Test.
- **Grenze der Aussage zur Größe:** Gemessen wurde ein Fall mit 1112 Positionen.
  Für größere Häuser bleiben die Paar- und Einteilungsgrenzen maßgeblich; sie
  melden sich mit eigenen Hinweisen.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
