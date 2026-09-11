# Ist, Soll und historische Planbasis

Die bestehende SP5-Bibliothek stellt `get_schedule(..., plan="ist"|"soll"|"both")`
bereit. Ihr [Quellvertrag für v1.32.3](https://github.com/mschabhuettl/libopenschichtplaner5/blob/v1.32.3/sp5lib/database.py#L546-L581)
unterscheidet normale Einteilungen anhand von `schedule_type`: 0 Ist, 1 Soll.
Sonderdienste und Abwesenheiten sind dort nicht zwischen Ist und Soll getrennt.
Die API-Fassade reicht dieselbe Plansicht an `/api/schedule` weiter.

## Auswahl im Generator ab 0.9.15

- **Vergleichsdienste im Planungszeitraum:** normale Dienste aus Ist (Vorgabe)
  oder Soll. Nur passende Dienste innerhalb des inklusive gewählten Zeitraums
  werden aus dieser Sicht genommen. Es gibt keine Vereinigung beider Pläne
  und keinen Rückfall auf Ist, wenn Soll leer ist.
- **Abwesenheiten, Sonderdienste und angrenzende Dienste:** weiter aus Ist.
  Auch wenn eine API hier unterschiedliche Daten liefert, ersetzt die Auswahl
  der Vergleichsdienste nicht diese Grundlage für Verfügbarkeit und Randregeln.
- **Historische Planbasis:** separate Auswahl Ist/Soll/beide für frühere
  Einsätze und Vorschläge. Sie wird nicht durch die Referenzauswahl verändert.
- **Vergleich oder Fixierung:** separate Auswahl, nur bei eindeutiger Zuordnung
  zum vorhandenen Bedarf. Fehlender Bedarf wird nicht erfunden. Freigaben und
  Regelprofile werden nicht bestätigt; der unabhängige Prüfer bleibt maßgeblich.

Nicht eindeutig zuordenbare **normale Vergleichsdienste innerhalb des
Planungszeitraums** bleiben in der Zuordnungsdiagnose erhalten, sind aber
keine verpflichtenden Einteilungen und blockieren deshalb nicht allein die
Neuplanung. Bei ausdrücklich gewählter **Fixierung** bleibt die fehlende
Zuordnung ein Planungsblocker. Das Metadatenfeld `planning_blocker` kennzeichnet
diesen Unterschied bei ungeklärten Referenzen. Es werden weder Ersatzbedarfe
noch Freigaben erzeugt. Angrenzende Ist-Dienste, Sonderdienste und sonstige
offene Einrichtungsvoraussetzungen werden dadurch nicht freigegeben.
Die Änderung gilt für neue Importe; bestehende Projekte werden nicht
automatisch umgeschrieben oder von offenen Hinweisen bereinigt.

Im Quellmonat werden bei Soll zusätzlich die normalen Soll-Dienste gelesen.
Außerhalb des Planungszeitraums bleiben auch innerhalb desselben Monats die
Ist-Dienste erhalten. Monate ohne Überschneidung benötigen keine Soll-Abfrage.
Die API-Änderungserkennung prüft auch die zusätzlich gelesenen Antworten.

Die Metadaten halten `reference_plan`, `context_plan`, `availability_plan` und
`special_shift_plan` fest. Die letzten drei stehen auf `ist`. Die
Zuordnungsübersicht zeigt einen historischen Importstand, keinen frisch
validierten Ergebnisplan. Ältere Projekte ohne Herkunft bleiben ausdrücklich
undokumentiert. Bestehende Projekte und Benutzerinstallationen werden nicht
nachträglich geändert.

## Belege

Synthetische Adaptertests liefern bewusst gegensätzliche Ist- und Soll-Dienste,
Abwesenheiten und Sonderdienste. Sie prüfen beide Referenzmodi, feste und weiche
Einteilungen, leeres Soll ohne Rückfall sowie Ist-Randdienste am Tag vor und nach
der Planung. HTTP-Tests belegen die getrennten Abfragen und unveränderte Historie;
Webtests prüfen beide Importwege und weisen `both` als Referenzwahl ab.
Der echte Browserimport wählt Soll, erhält den abweichenden Vergleichsdienst,
aber keine nur in der synthetischen Soll-Antwort stehende Abwesenheit.
Keine echten Personal- oder Projektdaten werden dafür benötigt.
