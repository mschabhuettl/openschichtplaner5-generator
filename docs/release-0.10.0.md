# Version 0.10.0 – nutzbarer Ablauf vom Import bis zum geprüften Plan

Diese Freigabe baut auf 0.9.32 auf. Sie ändert keine Benutzerinstallation
automatisch und lockert keine harte Regel. Sie ändert jedoch die Auslegung
mehrfach genannter Teamanforderungen und damit die geforderte Stellenzahl;
bestehende Projekte behalten ihre gespeicherten Bedarfe unverändert, ein
erneuter Import erzeugt die neue Auslegung.

## Planung entsteht wieder aus echten Quelldaten

- Zwei unveränderliche Kontextdienste, die sich widersprechen, erreichten den
  Solver als Bedingung zwischen zwei Konstanten. Eine einzige widersprüchliche
  Quellzeile machte damit den gesamten Plan unlösbar, mit einer Meldung, die
  keine Stelle benannte. Eine Regel zwischen zwei Tatsachen ist keine
  Planungsentscheidung: Die Bedingung gilt jetzt nur, wo eine Seite eine
  Einteilung ist, die der Plan steuert.
- Widersprüche zwischen zwei bestehenden Diensten werden unter dem
  vorhandenen, nicht invalidierenden Code `context` gemeldet und benennen
  beide Dienste und den Grund.
- Für den Planungszeitraum ändert sich nichts: Eine neue Einteilung gegen
  bestehenden Kontext bleibt in Solver und Validator abgelehnt.

## Mehrfach genannte Teamanforderungen

- Fordern mehrere Teams denselben Dienst am selben Arbeitsplatz und Tag, ist
  das eine Anforderung und nicht deren Summe. Übernommen wird die höchste
  Teamanforderung; alle fordernden Teams stehen in `Demand.team_ids` und
  dürfen besetzen.
- Besetzungseignung und Auflösung bestehender Dienste verwenden dieselbe
  Teammenge. Bestehende Dienste werden dadurch häufiger eindeutig zugeordnet.
- Mehrere Zeilen innerhalb eines Teams bleiben eigenständig, damit ein
  ausdrückliches MAX=0 nicht von einer anderen Zeile aufgehoben wird.
- Jede Zusammenfassung wird als offene Importangabe gemeldet und je Bedarf
  unter `metadata.provenance` mit allen Quellzeilen belegt.

## Oberfläche

- Sammelbefehle stehen dort, wo die Anzahl steht: „Alle historischen
  Vorschläge übernehmen“ über der Matrix, die Sammelbestätigung offener
  Importangaben über deren Liste, die 11/36-Ruhevorgaben über den Profilen.
- Die Vorschlagsübernahme wirkt weiterhin projektweit, unabhängig von Suche
  und sichtbaren Zeilen.
- Offene Importangaben lassen sich nach Kategorie eingrenzen und dann
  gesammelt als geprüft markieren. Bedarfe, Freigaben und Quellwerte bleiben
  dabei unverändert.
- Die 11/36-Ruhevorgaben werden nur für Profile bestätigt, die genau diese
  Werte bereits enthalten. Abweichende Profile bleiben ausdrücklich offen.
- Sammlungen scrollen durchgehend statt zu blättern; die Teamansicht zeigt
  alle Personen.
- Sichtbare Datumsangaben lauten TT.MM.JJJJ. Gespeicherte und verglichene
  Werte sowie technische Kennungen bleiben unverändert im ISO-Format.
- Vertragliche Wochenstunden sind je Person pflegbar. Sie sind ein weiches
  Verteilungsziel je Kalenderwoche, keine harte Höchstgrenze, und bleiben vom
  Periodensoll getrennt.

## Prüfstand und Grenzen

- 1319 Tests, Ruff, Release-Provenienz und der vollständige Browserablauf
  laufen grün. Zwei bereits vorhandene Browserprüfungen wurden von keinem
  Runner ausgeführt und sind jetzt eingebunden; drei weitere kamen hinzu.
- Eine private lokale Abnahme gegen echte Quelldaten belegt den Ablauf bis zum
  geprüften Plan. Veröffentlicht werden daraus ausschließlich nicht
  identifizierende Aggregate.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
  Offene Besetzungen bleiben bestehen, wo keine freigegebene Person existiert;
  es werden keine Freigaben, Bedarfe oder Quellwerte ergänzt.
- Ein Team-CSV-Export ist nicht enthalten.
