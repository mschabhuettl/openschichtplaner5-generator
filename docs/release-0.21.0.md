# Version 0.21.0 – Fehlende Dienstfreigaben benennen, statt sie zu zählen

Diese Freigabe baut auf 0.20.0 auf. Sie ändert keine harte Regel, keinen Bedarf,
keine Freigabe und kein Suchverhalten. Gespeicherte Projekte liefern dieselben
Pläne wie zuvor; berichtet wird mehr.

## Warum die bisherige Auskunft nicht zum Handeln reichte

- Blieb eine Stelle unbesetzbar, nannte der Befund `candidate_shortage` die
  Ausschlussgründe als Zählwerte je Bedarf: „persönliche Dienstfreigabe fehlt: 12".
  Wer daraus ableiten wollte, **welche** Freigabe einzutragen ist, musste Person
  für Person durchgehen.
- An echten Quelldaten hingen an dieser Frage 665 Pflichtstellen eines Monats.
  Die Liste, die dafür nötig war, ist bisher außerhalb des Programms entstanden.
  Damit war sie nicht wiederholbar und für keinen anderen Zeitraum verfügbar.

## Was sich geändert hat

- **`missing_approvals`** im Ergebnisbericht nennt je Person und Dienstart, wie
  viele Pflichtstellen ohne diese eine Freigabe unbesetzbar bleiben. Gezählt wird
  nur, wo die Freigabe die **einzige** Hürde ist und der Bedarf sonst keine
  geeignete Person findet. Eine Zeile mit hoher Zahl löst viele Stellen auf
  einmal; die Liste ist danach sortiert.
- **Eigener Abschnitt im Ergebnis** mit Name und Dienstbezeichnung aus dem
  Dienstkatalog, Suchfeld, Sprung in die Personenbearbeitung und Ausgabe als
  CSV-Datei mit Semikolon und BOM, die Tabellenprogramme direkt öffnen.
- Die Liste **erteilt keine Freigabe und schlägt keine vor.** Sie benennt, wo
  eine fehlt. Historische Einsätze bleiben davon unberührt: Sie sind weiterhin
  Vorschläge, die ausdrücklich bestätigt werden müssen.

## Was dabei gemessen wurde

An echten Quelldaten eines vollen Monats, nur nicht identifizierende Aggregate:

- Der Bericht nennt 132 fehlende Freigaben, verteilt auf 54 Personen und 12
  Dienstarten. Die stärksten Zeilen lösen je 31 Pflichtstellen auf einmal.
- **Die Schwelle für historische Vorschläge ist nicht die Ursache.** Von 1742
  historischen Vorschlägen verwirft die Mindestanzahl von zwei Einsatztagen 454
  Stück. Übernimmt man versuchsweise auch jeden Ein-Tages-Nachweis, kommen 396
  Freigaben hinzu – und die Zahl der besetzbaren Bedarfe ändert sich um **null**:
  738 vorher, 738 nachher, 180 ohne geeignete Person vorher wie nachher. Die
  fehlenden Freigaben betreffen Dienstarten, die diese Personen in drei Jahren
  Historie nie ausgeübt haben. Aus der Historie ist dort nichts mehr zu holen.

## Prüfstand und Grenzen

- Vollständige Testsuite, Ruff und der Browserdurchlauf laufen grün. Die neuen
  Tests und der neue Browserablauf schlagen ohne die Änderung fehl; geprüft durch
  Zurücknehmen der Änderung bei unverändertem Test.
- **Grenze der Aussage:** Die Zahl je Zeile zählt Stellen, die ohne diese
  Freigabe unbesetzbar bleiben. Sie sagt nicht, dass die Stelle mit der Freigabe
  auch tatsächlich besetzt wird – Ruhezeiten, Sollstunden und die übrigen Regeln
  entscheiden weiterhin mit. Mehrere Zeilen können dieselbe Stelle betreffen.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
