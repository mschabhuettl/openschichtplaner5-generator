# Version 0.13.0 – Dienste ohne Quellzeiten

Diese Freigabe baut auf 0.12.0 auf. Sie ändert keine Benutzerinstallation
automatisch und lockert keine harte Regel. Gespeicherte Projekte bleiben
unverändert; die neue Auslegung entsteht bei einem erneuten Import.

## Arbeit ohne Uhrzeiten geht nicht mehr verloren

- Manche Dienstarten – Backoffice, Homeoffice, Fortbildung, Dienstreise –
  geben im Katalog auf keinem Tagindex Uhrzeiten an, nur eine bezahlte Dauer.
  Ein solcher Dienst konnte bisher keinem Bedarf zugeordnet werden und fiel im
  Planungszeitraum ersatzlos aus: Die Person galt als verfügbar und ihre
  bezahlten Stunden zählten nicht auf das Periodensoll.
- Solche Dienste im Zeitraum werden jetzt als persönliche Arbeit ohne Zeiten
  übernommen. Sie halten ihren Tag frei von weiteren Einteilungen und zählen
  mit den bezahlten Minuten aus `SHIFT.DURATION<Tagindex>` auf das
  Periodensoll. Sie decken **keinen** Besetzungsbedarf; eine offene Stelle
  bleibt sichtbar offen.
- Uhrzeiten werden nicht erfunden. `BoundaryWork` trägt dafür `day` statt
  `segments`: ein Tag ohne Zeiten belegt keine Uhrzeit, keine Tagesminuten und
  keine Ruhezeit. Genau eines von beidem muss gesetzt sein.
- Ohne Zeiten gibt es auch keine Tag-/Nachtart zu bestätigen. Der
  Bestätigungsschritt zählt solche Dienste nicht mehr als offen; er ließ sich
  vorher für sie nicht abschließen.

## Randkontext meldet die Ursache statt eines Defekts

- Außerhalb des Planungszeitraums informiert nur eine Zeitangabe die Ruhezeit.
  Ein Dienst ohne Quellzeiten hat dort nichts zu hinterlegen. Bisher meldete
  der Import je Dienst „Zeitfenster fehlt“ und ließ offen, ob die Quelle
  beschädigt ist.
- Solche Dienste werden jetzt einmal gesammelt gemeldet, mit dem tatsächlichen
  Grund: Die Dienstart gibt keine Uhrzeiten an, deshalb kann sie keine Ruhezeit
  vor oder nach dem Planungszeitraum belegen.
- Ein einzelner fehlender Tagwert einer Dienstart, die sonst Zeiten angibt,
  bleibt unverändert eine offene Angabe zu diesem Dienst.

## Darstellung und Datenvertrag

- Der Plankalender zeigt persönliche Arbeit ohne Zeiten mit dem Dienstnamen
  und dem Hinweis „ohne Zeitangabe“ statt einer Uhrzeit, die die Quelle nicht
  hergibt. Fehlt eine Person an einem Tag als Kandidatin, nennt die
  Engpassbegründung „persönliche Arbeit ohne Zeitangabe an diesem Tag“.
- `BoundaryWork.day` ist optional und standardmäßig leer; jedes bestehende
  Projekt und die strenge Prüfung der Zeitsegmente bleiben unverändert.
- Der Import meldet die Anzahlen als `metadata.untimed_period_work` und
  `metadata.untimed_context_work`.

## Prüfstand und Grenzen

- 1337 Tests, Ruff, Release-Provenienz und acht Browserabläufe laufen grün.
- Private lokale Abnahme gegen echte Quelldaten, nur nicht identifizierende
  Aggregate: Offene Importangaben fallen von 117 auf 28, weil 91 gleichlautende
  Einzelmeldungen durch eine begründete Sammelmeldung ersetzt werden. Im
  Zeitraum werden 34 Dienste bei 13 Personen mit 270 zuvor unsichtbaren
  bezahlten Stunden modelliert; deren Rückstand auf das Periodensoll sinkt
  dadurch von 735 auf 465 Stunden. Alles Übrige bleibt gleich: gleiche
  Personen-, Dienst- und Bedarfszahlen, gleicher Plan mit 246 Einteilungen.
- In diesem Datenbestand entstand durch die Tagessperre keine Änderung am Plan:
  Die 13 betroffenen Personen hatten für die Bedarfe dieses Zeitraums keine
  Dienstfreigabe und waren dort ohnehin keine Kandidatinnen oder Kandidaten.
  Die Sperre ist die Absicherung für den Fall, dass eine Freigabe hinzukommt.
- Eine Ruhezeit zum Vortag oder Folgetag lässt sich für Arbeit ohne Zeiten
  nicht prüfen. Das bleibt eine Grenze der Quelle, keine gelockerte Regel.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.
