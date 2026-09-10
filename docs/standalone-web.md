# Eigenständige Webanwendung

Die Weboberfläche gehört direkt zu OpenSchichtplaner5 Generator. Die separate API und das bisherige Frontend sind dafür nicht erforderlich. Alle Daten und Berechnungen bleiben beim lokal gestarteten Dienst.

## Start

```sh
python -m pip install '.[web,sp5]'
sp5-generator serve --host 127.0.0.1 --port 8080 --state-dir ./generator-state
```

Im Browser `http://127.0.0.1:8080` öffnen. Der lokale Dienst ist für eine Person auf einem kontrollierten Rechner vorgesehen; er startet seinen Hintergrundworker selbst. Er ist kein öffentlich erreichbarer Mehrbenutzerdienst mit Anmeldung. Keine Originalverzeichnisse in das Zustandsverzeichnis legen.

## Stammverzeichnis laden

Im Feld **SP5-Verzeichnis** den Pfad eingeben, der für den Dienst lesbar ist. Im normalen lokalen Betrieb ist dies ein Pfad auf demselben Rechner. Im Container ist es der schreibgeschützt eingebundene Containerpfad, beispielsweise `/source`.

Das Stammverzeichnis darf direkt die DBF-Dateien oder genau ein passendes direktes Unterverzeichnis enthalten. Die Erkennung benötigt die Tabellen `5EMPL`, `5GROUP`, `5GRASG`, `5SHIFT` und `5WOPL`; Groß-/Kleinschreibung wird berücksichtigt. Bei mehreren Datenbeständen muss das konkrete Verzeichnis ausgewählt werden. Verknüpfte Quelldateien und Pfade außerhalb eines ausdrücklich gesetzten `SP5_SOURCE_ROOT` werden abgelehnt.

Nach **Quelle prüfen** das Team, den neuen Planungszeitraum, die ausdrücklich gewählte Zeitzone und den historischen Bezugszeitraum auswählen. Als Historienbasis stehen Ist, Soll oder beide zur Auswahl; Standard ist Ist. Die Historie muss vor dem neuen Planungszeitraum liegen. Der Import schreibt keine Originaltabellen. Fingerprints vor und nach dem Lesen erkennen zwischenzeitliche Änderungen; sie behaupten keine atomare Datenbanktransaktion. Fehlende Tabellen und ungeklärte Originalsemantik bleiben sichtbar.

Ein Browser kann den freien Zugriff auf lokale Verzeichnisse nicht stellvertretend für einen entfernten Server gewähren. Deshalb wird der Quellpfad am Rechner des Dienstes bzw. als Docker-Bind-Mount bereitgestellt; es gibt keine Übertragung an einen externen Dienst.

## Matrix aus bisherigen Diensten

Die Anwendung übernimmt Personal und Stammdaten über `sp5lib` und zählt die bisherigen Einteilungen je Person, Dienstart und Arbeitsplatz im gewählten Historienzeitraum. Die Matrix zeigt Häufigkeit sowie erstes und letztes beobachtetes Einsatzdatum. Abwesenheiten und doppelte identische Einträge werden nicht als zusätzliche Einsätze gezählt.

Die daraus vorgeschlagenen Einsatzfreigaben sind zunächst **unbestätigt**. Historische Einteilung, tatsächliche Qualifikation und künftige Verfügbarkeit bleiben unterschiedliche Aussagen. Aus früheren Einsätzen entstehen weder automatisch Qualifikationsnachweise noch harte Verfügbarkeitsmodelle. Bestätigte Vorschläge können in die zeitlich gültigen Freigaben übernommen und danach ergänzt oder entfernt werden. Dienstartklassifikation, erforderliche Qualifikationen, Profile, Grenzen und persönliche Wünsche bleiben ausdrücklich bearbeitbar.

Entwürfe und individuelle Ergänzungen werden im separaten Zustandsverzeichnis gespeichert, nicht in den Original-DBF-Dateien. Nach dem Speichern kann ein Vorschlag berechnet, unabhängig geprüft, verändert, fixiert und neu berechnet werden. Die Exporte enthalten den aktuellen Snapshot bzw. Plan.

Die native Gesamtübernahme zurück in einen Originalbestand bleibt derzeit gesperrt. Ungeklärte Bedarfskombinationen sind weiterhin keine automatisch bestätigten Planungsgrundlagen.
