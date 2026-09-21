# Version 0.27.0 – Freigaben durchspielen, statt sie zu erraten

Diese Freigabe baut auf 0.26.0 auf. Sie ändert keine bestehende Regel, keine
Freigabe und kein gespeichertes Projekt.

## Was würde eine zusätzliche Freigabe bringen?

0.26.0 hat sichtbar gemacht, dass ein Rückstand beim Soll meist an der
Freigabedecke hängt. Die naheliegende Frage danach – *welche* Freigabe hilft? –
war nur durch Ausprobieren zu beantworten: Freigabe setzen, neu rechnen,
vergleichen. Bei einem großen Haus sind das pro Versuch zehn bis vierzig Minuten.

Im Ergebnisbereich beantwortet das jetzt eine Vorschau ohne Rechenlauf. Für jede
noch fehlende Freigabe, bei der die Freigabe die **einzige** Hürde wäre, nennt
sie:

- wie viele derzeit **für niemanden besetzbare** Stellen dadurch besetzbar würden,
- wie viel Arbeitszeit der Person damit überhaupt erreichbar wäre,
- und wie viel davon auf ihren **eigenen Rückstand** entfällt.

Zuerst steht die Zusammenfassung **je Dienstart** – dieselbe fehlende Freigabe
trifft meist dutzende Personen, und eine Liste je Person wäre dann keine
Arbeitsliste. Die Personenzeilen bleiben als Detail aufklappbar.

Sortiert wird nach dem, was zählt: eine Freigabe, die eine unbesetzbare Stelle
schließt, steht vor jeder, die nur Last verschiebt – auch wenn die zweite mehr
Stunden bewegen würde.

**Die Vorschau erteilt keine Freigabe und schlägt keine vor.** Eine Freigabe ist
eine fachliche Entscheidung und bleibt es; das Werkzeug leitet keine
Qualifikation ab. Sie beschreibt Möglichkeit, nicht Plan: ob die Suche die Arbeit
dann wirklich verschiebt, entscheiden alle übrigen Regeln mit.

An echten Daten: 9252 Freigaben kämen in Frage, und **13 Dienstarten decken alle
14 unbesetzbaren Stellen** ab – für jede davon kommen 73 bis 102 Personen in
Frage. Aus einer Liste von tausenden Zeilen wird damit eine Entscheidung über
dreizehn Dienstarten.

## Fehlende Freigaben nach Ertrag geordnet

Die Liste der fehlenden Freigaben nannte je Person und Dienstart die Zahl der
blockierten Stellen und ordnete danach. Zwei kurze Stellen wogen damit schwerer
als eine lange. Jede Zeile nennt jetzt zusätzlich die **Arbeitszeit**, die eine
einzelne Freigabe zugänglich machen würde, die Liste ist danach geordnet, die
Überschrift nennt die Summe und die CSV führt die Spalte mit.

## Ohne Auswirkung auf Bestehendes

Gespeicherte Projekte, laufende Aufträge und Exporte verhalten sich unverändert.
Die Vorschau wird nur berechnet, wenn sie jemand ausdrücklich anfordert.
