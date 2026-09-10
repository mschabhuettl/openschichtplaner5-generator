# Teamauswahl, Freigabematrix und Monatsplan

## Daten auswählen

1. SP5-Verzeichnis oder konfigurierte API als Quelle wählen und **Teams laden** drücken.
2. Die gewünschten Teams im Baum ankreuzen. Ein Elternknoten schaltet seinen Unterbaum gemeinsam um; einzelne Unterteams können anschließend abgewählt werden. Nur tatsächlich angekreuzte Teams werden importiert.
3. Zeitraum und Zeitzone festlegen. Für die historische Basis werden automatisch die vorherigen drei Monate vorgeschlagen; der Zeitraum und die Ist-/Soll-Sicht bleiben änderbar.
4. **Daten importieren** lädt Personal, Stammdaten, Bedarf und Historie gemeinsam. Eine Person erscheint nur einmal. Hat sie mehrere Teammitgliedschaften, bleibt sie enthalten, solange mindestens eines dieser Teams ausgewählt ist.

Die Teamauswahl ersetzt keine Einsatzfreigabe. Gruppen außerhalb der Auswahl werden nicht durch eine versteckte erneute Unterbaum-Erweiterung ergänzt. Der bisherige JSON-Import mit einem einzelnen `team_id` bleibt aus Kompatibilitätsgründen rekursiv; `team_ids` ist eine ausdrückliche Liste exakter Gruppen-IDs.

## Excel-artige Matrix

Bei SP5-Importen stehen Personen in den Zeilen und Dienste aus den Schichtstammdaten in den Spalten. Physische Arbeitsplätze sind keine Dienstspalten. **Achsen tauschen** dreht die Ansicht um; es werden dieselben Freigaben bearbeitet, keine zweite Matrix. Derselbe Dienst an mehreren Arbeitsplätzen erhält eine gemeinsame Dienstspalte. Die ausdrücklich bestätigte Dienstfreigabe gilt arbeitsplatzübergreifend; zusätzliche Qualifikationsanforderungen bleiben wirksam. Allgemeine JSON-Snapshots können weiterhin gesonderte Funktions-/Arbeitsplatzfreigaben verwenden.

- **Vorschlag**: Ein früherer Einsatz wurde beobachtet, ist aber noch keine bestätigte Freigabe.
- **Frei**: Eine ausdrückliche Freigabe deckt den angezeigten Planungszeitraum.
- **Betreut / Teils betreut**: Eine Betreuungspflicht ist ganz oder teilweise wirksam.
- **Teilzeitraum**: Die bestehende Freigabe gilt nicht für den gesamten Planungszeitraum.
- **Keine Freigabe**: Es liegt keine entsprechende Freigabe für den ganzen Zeitraum vor. Das ist kein automatisch abgeleitetes Berufs- oder Qualifikationsurteil.

Ein Klick setzt beziehungsweise entfernt die Freigabe für den Planungszeitraum. Bereits vorhandene Freigaben außerhalb dieses Zeitraums bleiben erhalten. Eine Verlängerung einer betreuten Teilfreigabe hebt die Betreuungspflicht nicht stillschweigend auf. Die Detailansicht erlaubt die Bearbeitung einzelner Gültigkeitszeiträume. Qualifikationsnachweise werden durch die Matrix nicht erzeugt.

Historische Vorschläge lassen sich einzeln oder nach ausdrücklicher Bestätigung für die aktuell sichtbare Auswahl übernehmen. Funktionen aus der Historie werden auch ohne aktuellen Besetzungsbedarf angezeigt; daraus entsteht kein erfundener Bedarf. Suche und Pfeiltasten unterstützen die Bearbeitung großer Tabellen. Die Personen-Detailansicht enthält weiterhin Tag-/Nachtgrenzen, Zeitfenster und Profile.

**Änderungen speichern** sichert den Snapshot im konfigurierten Zustandsverzeichnis. Beim temporären Portainer-Stack liegt dieses ausschließlich auf `tmpfs` und wird beim Container-Neustart verworfen.

## Monatsplan und Einsatzplan

Das Ergebnis wird nach dem Darstellungsprinzip des Hauptprojekts als Tagesraster angezeigt: feste erste Spalte, Wochentage, Wochenendmarkierung und Dienstblöcke mit Zeitangaben.

- **Personenansicht**: Personen in den Zeilen, Kalendertage in den Spalten.
- **Dienstansicht bei SP5-Importen**: Dienste in den Zeilen, eingeteilte Personen in den Tageszellen.

Mehrere Einteilungen pro Tag und mehrteilige Dienste bleiben sichtbar. Die Datumszuordnung verwendet die Zeitzone des Snapshots; Dienste über Mitternacht erscheinen an den betroffenen Tagen, ein Ende genau um Mitternacht belegt nicht den Folgetag. Fixierte Dienste sind gekennzeichnet. Bei längeren Zeiträumen kann zwischen Monaten gewechselt werden.

Ein Klick auf einen Dienstblock öffnet die Einteilungsdetails. Dort können Personen geändert, Dienste entfernt oder fixiert werden. Anschließend erneut prüfen oder mit Fixierungen neu berechnen. Der Monatsplan ist eine Entwurfsansicht; eine native Gesamtübernahme in Original-SP5-Daten ist weiterhin nicht implementiert.

## Reproduzierbare Browserprüfung

Nach Installation von `.[dev,web,sp5]`:

```sh
npm ci --prefix tests/browser
cd tests/browser
npx playwright install chromium
cd ../..
WEB_TEST_PYTHON=python npm test --prefix tests/browser
```

Der Test startet selbst einen lokalen Webdienst samt Worker und eine ausschließlich synthetische HTTP-Quelle. Er prüft Teilauswahl, Historienmatrix, Achsentausch, zeitliche Freigaben, Speichern, Berechnung, Monatsansichten, Fixierung, Mitternachtsgrenzen sowie breite und schmale Ansichten. Andere Browser-Netzwerkziele werden gesperrt. Es wird keine konfigurierte produktive API verwendet.

## Bestehende Importe

Snapshots mit der früheren arbeitsplatzbasierten Matrix werden nicht automatisch umgedeutet. Daten erneut importieren und die dienstbezogenen Vorschläge prüfen. Die neuen Dienst-IDs verwenden einen eigenen Namensraum, sodass alte Freigaben nicht versehentlich als Dienstfreigaben gelten.

## Bestehender Plan und tagesbezogener Bedarf

Beim Import ist **Als Vergleich verwenden · neu planen** vorausgewählt. Vorhandene Einteilungen innerhalb des Planungszeitraums werden einem eindeutig passenden Bedarf zugeordnet und bleiben veränderbar. **Bestehende Einteilungen fixieren** schützt dieselben Einteilungen ausdrücklich vor einer Neuberechnung. Vorhandene Einteilungen erzeugen in diesem Zeitraum keinen zusätzlichen Pflichtbedarf. Nicht eindeutig zuordenbare Einteilungen bleiben als offene Angaben erhalten. Außerhalb des Zeitraums bleibt der feste Randkontext erhalten; seine Regeln werden weiterhin geprüft.

Tagesbezogene Sonderbedarfe ersetzen den regelmäßigen Bedarf derselben Gruppe und desselben Diensts am betreffenden Datum. Sie werden nicht addiert. Auch eine Obergrenze null ersetzt einen positiven Regelbedarf. Mehrdeutige Sonderbedarfe blockieren die Freigabe, statt auf Regelbedarf zurückzufallen. Die Wochentags-/Feiertagszeitfenster des Diensts bleiben maßgeblich. Die separate DADEM-Bedeutung und individuelle Sonderdienstzeiten sind damit nicht automatisch geklärt.

Grundlage für die Vorrangregel: [Originalhandbuch, Abschnitte 3.6 und 4.3](https://www.schichtplaner.de/manual/de/sp5/Schichtplaner5.pdf).

Geladene Unterteammitglieder erhalten zusätzlich den Einsatzbereich ihrer ebenfalls ausgewählten übergeordneten Teams. Diese Importinterpretation muss bestätigt werden; direkte Mitgliedschaften bleiben separat in den Metadaten erhalten. Nicht ausgewählte Unterteams liefern weiterhin keine zusätzlichen Personen.
