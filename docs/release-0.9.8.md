# Version 0.9.8 – Geprüfte Release-Downloads

Wheel, Python-Quellarchiv und Dockerarchiv können mit einer gemeinsamen
`SHA256SUMS` dauerhaft an einem Release bereitgestellt werden. Der neue Workflow
**Verified release assets** übernimmt dafür ohne Neubau ausschließlich die
bereits geprüften Dateien aus der vollständig erfolgreichen `main`-CI des
exakten Release-Commits. Die bisherigen 30-Tage-Workflow-Artefakte bleiben erhalten.

Vor dem Upload werden Dateiliste, Versionsnamen und sämtliche Prüfsummen
kontrolliert. Fremde Dateien, symbolische Links oder unvollständige Manifeste
führen zum Abbruch. Ein fehlender CI-Nachweis oder abgelaufene Artefakte werden
nicht durch `latest`, einen anderen Commit oder einen Neubau ersetzt. Bestehende
Release-Dateien werden niemals automatisch überschrieben. Nach dem Upload werden
die veröffentlichten Dateien erneut heruntergeladen und geprüft.

Die [Ergebniszuordnung aus 0.9.7](release-0.9.7.md) und alle bisherigen
Planungsregeln bleiben erhalten. Persönliche Freigaben und optionale
Qualifikationen werden nicht verändert. Benutzerinstallationen werden nicht
automatisch aktualisiert.

## Prüfung und Verfügbarkeit

Die Herkunftsauswahl wird separat mit Node-Tests geprüft; synthetische
Python-Tests prüfen die Dateigrenzen, Prüfsummen und unveränderte Ausgabeverzeichnisse
bei Ablehnung. Der vollständige [Release-Prüfablauf](verification.md) bleibt
Voraussetzung für die Veröffentlichung. Die Release-Dateien sind erst nach
erfolgreichem Upload und Rückprüfung verfügbar; lokale Tests allein belegen dies nicht.

## Aktualisierung

Vor einem Update Projekte sichern. Nach erfolgreicher Veröffentlichung steht
`ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.8` zur Verfügung.
Das Zustandsvolume bleibt bestehen. Für Python das Wheel derselben Version
verwenden; Details stehen in der [Installationsanleitung](../README.md).
