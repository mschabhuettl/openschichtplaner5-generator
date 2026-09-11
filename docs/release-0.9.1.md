# Version 0.9.1 – Persönliche Freigaben als Standard

Neue SP5-Importe benötigen standardmäßig persönliche Dienstfreigaben, aber keine zusätzlichen Qualifikationsnachweise. Ausdrücklich aktivierte Qualifikationsanforderungen bleiben verbindlich.

Die Planungsbereitschaftsprüfung erklärt jetzt eine aktivierte zusätzliche Nachweispflicht ohne eingetragene Qualifikationen und nennt die Korrektur unter Regeln & Bedarf. Bestehende Projekte werden nicht stillschweigend verändert. Bei alten Importen die zusätzliche Nachweispflicht dort deaktivieren, wenn persönliche Freigaben ausreichen. Freigaben, Ruhezeiten und andere Regeln bleiben erhalten.

Enthalten sind außerdem die Funktionen aus [0.9.0](release-0.9.0.md): geführter Import und explizite Übernahme bestehender Konfigurationen.

## Aktualisieren

Vor dem Update Projekte über „Projekt sichern“ exportieren. Nach erfolgreicher Container-Veröffentlichung das Image `ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.1` verwenden. Das bestehende Zustandsvolume beibehalten.

Die unterstützte Auslieferung ist eine lokale Linux-amd64-Planungsinstanz. Direkte Rückschreibung nach SP5, getrennte Benutzerkonten und Mandanten sind nicht enthalten. Ein geprüfter Teilplan ist kein vollständig besetzter Plan.
