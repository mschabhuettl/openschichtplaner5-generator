# Version 0.9.2 – Verständliche Engpassdiagnosen bei Teilplänen

Wenn für einen Bedarf zu wenige Personen geeignet sind, nennt der Prüfbericht jetzt die Ausschlussgründe mit Anzahl: etwa fehlende persönliche Dienstfreigaben, Teamzugehörigkeit, zusätzliche Qualifikationsnachweise oder Abwesenheiten. Eine Person kann aus mehreren Gründen ausgeschlossen sein; die Zahlen dürfen deshalb nicht addiert werden.

Auch ein unabhängig geprüfter, gültiger Teilplan behält die Hinweise zu fehlenden geeigneten Personen und gemeinsam benötigten Kandidaten. Diese Hinweise erklären offene Stellen, ohne sie als Regelverletzungen zu behandeln. Über „Bedarf öffnen“ führt der Bericht zum betroffenen Bedarf.

Die Hinweise sind keine vollständige Ursachenanalyse aller möglichen Regelkombinationen. Eine ausreichende Zahl individuell geeigneter Personen garantiert noch keinen vollständig besetzten Plan. Nach manuellen Änderungen bewertet „Erneut prüfen“ die aktuellen Einteilungen; die Kandidatenengpässe stammen aus der Berechnung und werden dabei nicht neu berechnet.

Persönliche Freigaben, aktivierte zusätzliche Qualifikationsanforderungen und alle anderen fachlichen Regeln bleiben unverändert verbindlich. Enthalten sind außerdem die Verbesserungen aus [0.9.1](release-0.9.1.md).

## Aktualisieren

Vor dem Update Projekte über „Projekt sichern“ exportieren. Nach erfolgreicher Container-Veröffentlichung das Image `ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.2` verwenden. Das bestehende Zustandsvolume beibehalten. Eine laufende Installation wird nicht automatisch aktualisiert.

Die unterstützte Auslieferung ist eine lokale Linux-amd64-Planungsinstanz. Direkte Rückschreibung nach SP5, getrennte Benutzerkonten und Mandanten sind nicht enthalten. Ein geprüfter Teilplan ist kein vollständig besetzter Plan.

## Prüfung

Die vorhandenen [Release-Gates](verification.md) prüfen Python-Tests, saubere Paketinstallationen, Browserabläufe und Containerbetrieb mit synthetischen Daten. Neue Regressionen decken fehlende Freigaben, gemeinsame Kandidatenengpässe sowie die Anzeige und Bedarf-Navigation im Browser ab. Der tatsächliche Freigabestatus ergibt sich aus dem erfolgreichen Workflow-Lauf des veröffentlichten Commits, nicht allein aus dieser Beschreibung.
