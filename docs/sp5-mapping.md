# Optionaler lesender SP5-Adapter

`sp5generator.sp5_adapter.import_snapshot(db, period_start, period_end, team_id, timezone)` erhält eine ausdrücklich ausgewählte sp5lib-Datenbankinstanz. Es werden keine Standarddatenpfade geöffnet und keine Quelldaten geschrieben. Das Kernpaket importiert sp5lib nicht; erst der Adapteraufruf benötigt die optionale Abhängigkeit.

## Übernommene Struktur

- EMPL und Gruppenmitgliedschaften liefern stabile, mit `sp5:` präfixierte IDs und Beschäftigungsgrenzen. Anzeigenamen bleiben Laufzeitdaten. NOTE1 wird nicht als Qualifikationsnachweis interpretiert.
- SHDEM wird über `get_staffing_requirements()` übernommen: Gruppe, Schicht, Arbeitsplatz, Wochentag, MIN und MAX. MAX ist eine Obergrenze, kein Ziel. Feiertage verwenden Index 7 über `calculations.day_index`.
- SHIFT-Teilintervalle werden mit `calculations.parse_startend` verarbeitet; Ende vor oder gleich Beginn liegt am Folgetag. DURATION bestimmt gesondert bezahlte Minuten. Mehrdeutige oder nicht existierende lokale Uhrzeiten sperren die betroffenen Eingaben bis zur expliziten Klärung.
- ABSEN unterscheidet ganzen Tag, erste/zweite Tageshälfte und Minutenintervalle. Halbtaggrenze ist 12:00 gemäß Library-Berechnung; stundenweise Abwesenheit kann Mitternacht überschreiten.
- RESTR 0/1/2 bleiben getrennt. Anfragefreigaben werden niemals automatisch erteilt. Der bestehende Library-Helfer `is_restricted` wird wegen abweichender Gradbehandlung nicht verwendet.
- Normale bestehende Dienste werden als fixierte Kontextzuweisungen importiert. Der gelesene Kontext beträgt zunächst 31 Tage auf beiden Seiten und bleibt unbestätigt, bis das gewählte Regelprofil ausreichenden Kontext nachweist.

## Gezielt ungeklärte Fälle

SPDEM und DADEM werden strukturell in `metadata.unresolved_native` erhalten. Der untersuchte öffentliche Library-Code belegt keine vollständige Vorrang-/Kombinationsregel; diese Bedarfe werden nicht addiert. Gruppe/Arbeitsplatz 0, fehlende Werte und MAX=0 werden ebenfalls ausdrücklich zur Klärung zurückgestellt. Fehlender Bedarf wird nicht in Nullbedarf umgedeutet.

Funktionen, Qualifikationspflicht, explizite Freigaben und Dienstartklassifikation benötigen zusätzliche bestätigte Regeln. Dienste aus SHIFT werden als `sp5:service:<ID>` abgebildet. Eine Bedarfsposition kombiniert Dienst und physischen Arbeitsplatz; diese IDs sind getrennt. Historie schlägt Dienstfreigaben vor, ohne eine Qualifikation zu behaupten. Erst die ausdrückliche Bestätigung erzeugt eine Freigabe mit `workplace_id="*"` für diesen Dienst an allen Arbeitsplätzen. Konkrete Arbeitsplatzfreigaben bleiben im allgemeinen Vertrag möglich. Alte arbeitsplatzbasierte Snapshots müssen neu importiert werden; ihre Freigaben werden nicht automatisch übertragen. Bereits vorhandene Dienste müssen ihrem tatsächlichen Bedarf zugeordnet werden, bevor die zusätzliche Kontextposition freigegeben werden kann. Sonderdienstzeitabweichungen fehlen teilweise im öffentlichen Schedule-Lesemodell und blockieren deshalb eine vollständige Freigabe.

Sollstunden verwenden die reine Library-Berechnung. Sollbuchungen, zeitanteilige Gutschriften und Anfangssalden sind noch gesondert zu ergänzen; entsprechende Diagnosen verhindern eine unberechtigte vollständige Freigabe. WORKDAYS wird nicht als Einsatzsperre verwendet. Ein Import über mehrere Library-Aufrufe ist ohne koordinierte Lesetransaktion kein garantierter konsistenter Snapshot; dieser Vorbehalt bleibt sichtbar.

## Übernahmegrenzen

Der Adapter ist ausschließlich lesend. DBF-Schreibsperren der Library sind nicht kompatibel mit Original-CodeBase-Sperren; Daten- und Journaländerung sind nicht gemeinsam atomar. Eine Gesamtübernahme wird deshalb nicht unterstützt. PostgreSQL-Einzelmethoden eröffnen jeweils eigene Transaktionen. Für sichere Batchübernahme müssen Quelldaten, externe Regel-/Verfügbarkeitsänderungen, Versionsprüfung und Idempotenzbeleg in eine gemeinsam koordinierte Transaktion überführt werden. Einzelne Tabellenlocks ohne Beteiligung aller API-Schreibpfade reichen nicht aus.

## Prüfung

`tests/test_sp5_adapter.py` erzeugt neue neutrale Python-Strukturen und prüft den Library-Vertrag, Feiertagsbedarf, mehrteilige Dienste, RESTR, Abwesenheitsfenster und erhaltene ungeklärte Werte. Das ist keine Prüfung originaler Produktivdateien und kein DBF-Roundtrip. Betreiber können später lokal eine isolierte Kopie prüfen; es werden keine Personendatensätze oder Screenshots für externe Auswertung benötigt.
