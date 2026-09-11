# Version 0.9.14 – Vergleichsdienste verständlich einrichten

Nach einem SP5-Import zeigt „Regeln & Bedarf“ den ursprünglichen Zuordnungsstand:
eindeutig zugeordnet, ohne Zuordnung und mehrdeutig. Einzelne Vergleichsdienste
lassen sich in Zehnerseiten mit Datum, Person und Dienst ansehen. Direkte Aktionen
führen zum Bedarf oder zu Team & Freigaben. Die Übersicht ist keine aktuelle
Planprüfung und erteilt weder Freigaben noch ergänzt sie Bedarf.

Die Importmaske erklärt die bisher feste Ist-Referenz im Planungszeitraum. Die
historische Ist-/Soll-Auswahl betrifft dagegen frühere Einsätze. Neue Importe
halten die Referenzplansicht ausdrücklich fest und fragen Ist explizit ab;
die Quellsemantik bleibt unverändert. Ältere Projekte ohne diese Herkunft zeigen
„Plansicht nicht dokumentiert“, keine erfundene Quelle. Eine auswählbare
Soll-Referenz ist in dieser Version noch nicht enthalten.

## Prüfungen

382 Python-Tests sowie Ruff und Diffprüfung erfolgreich. Der synthetische
Browserablauf prüft Zählung, Namenszuordnung, Zehnerseiten, ältere Metadaten,
Tastatur-Zielfokus und unveränderte Regeln/Freigaben/Einteilungen bei Navigation.
Desktop (1440 px) und Mobil (390 px) werden auf Seitenüberlauf geprüft.
Eine falsche Dienstkatalog-Verknüpfung wurde dabei vor dem Commit gefunden
und korrigiert. Keine echten Personal- oder Projektdaten enthalten.

Die [Änderungen aus 0.9.13](release-0.9.13.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
