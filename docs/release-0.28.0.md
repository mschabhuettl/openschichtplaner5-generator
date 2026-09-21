# Version 0.28.0 – Freigeben heißt Tätigkeit, nicht Uhrzeit

Diese Freigabe baut auf 0.27.0 auf. Sie ändert keine gespeicherte Freigabe: die
Zusammenfassung wirkt auf die Bedienung, gespeichert bleibt weiterhin jede
Zeitlage für sich.

## Eine Spalte je Dienstart

Die Quelle führt jede Zeitlage als eigenen Dienst: „OvD TD 5:20-17:20",
„OVD ND 17:20-5:20", „N-CT 6-16", „N-CT 12-22" und so weiter. Freigegeben wurde
deshalb bisher jede Uhrzeit einzeln – obwohl niemand jemanden „für 5:20"
freigibt, sondern für den Dienst.

Unter **Team & Freigaben** steht jetzt eine Spalte je **Dienstart**:

- Ein Klick gibt alle Zeitlagen derselben Tätigkeit frei, ein zweiter nimmt sie
  zurück. Die Meldung nennt, wie viele Zeitlagen betroffen waren.
- Eine Dienstart, bei der nur einzelne Zeitlagen freigegeben sind, zeigt
  **„◐ Einzelne Zeitlagen"**. Der nächste Klick vervollständigt sie, statt sie zu
  entziehen.
- Auch ein Dienst, den es nur zu einer Zeit gibt, verliert die Uhrzeit im Namen –
  denn freigegeben wird die Tätigkeit.
- Der Schalter **„Zeitlagen zusammenfassen"** in der Werkzeugleiste schaltet die
  Einzelansicht wieder ein; Suche, Filter und Achsentausch arbeiten unverändert.

Zusammengefasst wird nur, was am Namensende eine Zeitangabe trägt. Ein Name wie
„N-10" oder „144 Trainer" bleibt ein eigener Dienst; ein Stamm ohne Buchstaben
ist kein Name und wird nicht abgetrennt.

An echten Daten: **182 Spalten werden 71**, und „N-CT" fasst allein 35 Zeitlagen
zusammen.

## Historische Vorschläge tragen die ganze Dienstart

Ein Vorschlag entstand bisher nur für genau die Zeitlage, die jemand gefahren
ist. Wer „N-CT 6-16" gefahren hatte, blieb für „N-CT 12-22" ohne Vorschlag – und
die Matrix blieb nach dem Übernehmen fast leer.

Bei zusammengefassten Zeitlagen zählt der Nachweis jetzt für die ganze
Dienstart. Die Rückfrage vor dem Übernehmen sagt das ausdrücklich. Ohne
Zusammenfassung bleibt es bei der einzelnen Zeitlage.

## Was nicht übernommen werden kann, wird genannt

Vorschläge für Personen, deren Beschäftigung nicht in den Planungszeitraum
reicht, fielen wortlos weg – an echten Daten 43 Stück. Die Sammelleiste nennt
sie jetzt samt Grund.

## Die Fläche gehört den Daten

Die Seiten waren auf 1180 Pixel begrenzt; auf breiten Bildschirmen blieb rechts
alles leer, während die Freigabematrix waagrecht scrollen musste. Die Panels
nutzen jetzt die volle Breite. Fließtext behält seine Zeilenlänge, damit er
lesbar bleibt.

## Ohne Auswirkung auf Bestehendes

Gespeicherte Projekte behalten jede einzelne Freigabe; die Zusammenfassung ist
eine Ansicht, kein Datenumbau. Der Kalender und die Bedarfsansicht arbeiten
unverändert mit den einzelnen Diensten.
