# Belegte Quellsemantik für Import und Planung

Lesestand der drei unveränderten Checkouts am 11.09.2026:
Library `0dac4438c0be02c1ad612f54d4aba75a3e4d6335`, API
`d578f212d635b672ab277d7d29a37387145506f5`, OSP5
`addf5c2d1e40b4f266bacf1cd41f40ef70edbeb8`.
Dies ist eine eingegrenzte Datenflussanalyse, keine vollständige fachliche
Abnahme aller Originaltabellen. Keine realen Datensätze sind enthalten.

## Zusammenhängender Abgleich: Ursachen und Korrekturfolge

Vertiefter Lesestand: Generator `267ad4e71e4cff70f28709a5cc83983ea3fe6973`.
Die folgenden Aussagen unterscheiden Quellvertrag, bewiesenen Mappingfehler
und noch fehlende fachliche Entscheidungen. Die genannten Quellcheckouts
wurden nicht verändert. Die aktuelle Generator-Implementierung unterstützt
bereits Ist/Soll-Auswahl; der ältere Befund „Referenz immer Ist“ beschreibt
nicht mehr diesen Stand.

### Datenflussübersicht

| Gegenstand | Original → Library | API → OSP5 | Generator und Grenze |
| --- | --- | --- | --- |
| Persönliche Einschränkungen | `RESTR.EMPLOYEEID/SHIFTID/WEEKDAY/RESTRICT` → `Database.get_restrictions` (`database.py:6022`), Stufen 0 keine, 1 auf Anfrage, 2 nie (`set_restriction`) | `routers/schedule.py:get_restrictions` → `Employees.tsx:1080` zeigt Einschränkungen; Darstellung unterscheidet dort die drei Stufen nicht | `sp5_adapter.import_snapshot` erhält Stufen; Anfrage bleibt `approved=False`. `domain.eligibility` verlangt zusätzlich positive, zeitlich gültige Dienst-/Arbeitsplatzfreigaben. Keine Einschränkung ist kein Nachweis einer solchen Freigabe. |
| Teams | `GRASG`, `Database.get_employee_groups` und `get_group_members` | `get_schedule` filtert nach Personenmitgliedschaft, nicht nach Einsatzteam einer Einteilung; API schränkt zusätzlich auf sichtbare Personen ein | `hierarchy.resolve_group_selection`, direkte und geerbte Mitgliedschaften; bei mehreren möglichen Teams keine willkürliche Auswahl |
| Regelbedarf | `SHDEM.GROUPID/SHIFTID/WORKPLACID/WEEKDAY/MIN/MAX` → `Database.get_staffing_requirements` (`database.py:3590`) | `master_data.get_staffing_requirements` → `Personalbedarf.tsx:379` | je Quellzeile/Datum ein Bedarf; Feiertagsindex 7, Dienstzeit aus `SHIFT.STARTEND{idx}`, bezahlte Minuten aus `DURATION{idx}` |
| Tagesbedarf | `SPDEM.DATE` plus Gruppe/Dienst/Arbeitsplatz/MIN/MAX → `Database.get_special_staffing` (`database.py:6376`) | `/api/staffing-requirements/special` | ersetzt Regelbedarf in der Gruppe/Datum/Dienst-Zelle; mehrere Tageszeilen werden nicht automatisch addiert oder ausgewählt |
| Tagesgesamtbedarf | `DADEM` → **unveränderte Großbuchstabenfelder** in `daily_requirements` | API reicht sie durch | fachliche Relation zu Schichtbedarf ungeklärt; zusätzlich nachgewiesener Feldnamenfehler im Teamfilter, siehe unten |
| Referenzdienste | `MASHI.TYPE` → `Database.get_schedule`, reguläre Ist-/Solldienste; `CYASS`-Expansion und `SPSHI`-Abweichungen separat | `schedule.get_schedule` validiert Sicht, filtert Sichtbarkeit → `Schedule.tsx` | `_reference_schedule` wählt Referenzsicht; Abwesenheiten, Sonderdetails und Randkontext bleiben Ist. Bedarf wird nicht aus Einteilungen erzeugt. |
| Sollstunden | `EMPL.CALCBASE` und Stundenfelder, zusätzlich `BOOK.TYPE=1` → `calculations.get_nominal_hours` | `reports.get_bookings` → `Kontobuchungen.tsx:289–303` lädt Buchungen und trennt Typ 0/1 | CALCBASE und verfügbare Typ-1-Buchungen genutzt; `bookings_included` beschreibt Quellenabruf, keine globale Vollständigkeitsbestätigung |
| Ruhe/Regelkontext | API-Prüfung `routers/work_time_rules.py`, kein importiertes bestätigtes Generatorprofil | Warn-/Prüffunktion, nicht identischer Planungsvertrag | 660/2160 Minuten aus Nutzerauftrag; ±31 Tage geladener Ist-Kontext, aber `context_complete=False`; wirksame Profile und benötigte Randabdeckung gesondert prüfen |

### Warum MODEL_INVALID hier kein OR-Tools-Modellfehler beweist

`solver.solve` ruft **vor** `cp_model.CpModel()` die Funktion
`domain.input_diagnostics` auf. Jeder Eintrag in `snapshot.unresolved` und
jedes fehlende oder unbestätigte wirksame Personenprofil führt bereits dort
zu `MODEL_INVALID` (`solver.py:88–95`, `domain.py:340–366`).

Ein frischer Import erzeugt solche offenen Punkte absichtlich: Importkonsistenz,
Regel-/Freigabeneinrichtung, Randkontext, fehlende Buchungen sowie gegebenenfalls
nicht zugeordnete Vergleichsdienste. Im oben genannten untersuchten Stand
wurden Letztere **auch im nicht fixierten Referenzmodus** in `unresolved`
geschrieben. Seit `e02a05a` bleiben normale, nicht fixierte Vergleichsdienste
innerhalb der Planungsperiode ausschließlich Zuordnungsdiagnosen; sie
blockieren nicht mehr allein die Modellbildung. Ungeklärter fixer Randkontext
ist davon ausdrücklich ausgenommen (`tests/test_reference_blockers.py`).

Eine fehlende positive Freigabe ist genauer zu unterscheiden: Sie ergibt
`approval` in `domain.eligibility` und verhindert Kandidaten. Die leere
Freigabenliste selbst ist nicht die direkte `profile`-Diagnose und nicht
zwangsläufig allein ein `MODEL_INVALID`. Profilbestätigung, Auflösen von
Importfragen und persönliche Freigaben sind drei verschiedene Aufgaben.
Ein zusätzlich bestätigtes Profil beseitigt außerdem kein weiterhin wirksames
unbestätigtes Profil (`any(not p.confirmed for p in ps)`).

Synthetischer Nachweis: Bei importierter Testperson `CpModel` durch eine
Funktion ersetzt, die bei Aufruf abbricht; `solve` liefert trotzdem
`MODEL_INVALID` mit `profile/unresolved`, ohne Modellkonstruktion aufzurufen.
Bestehende Tests: `tests/test_input_boundaries.py`,
`test_import_uses_personal_approval_without_implicit_qualification_gate`.

### Warum eine Referenz nicht eindeutig einem Bedarf entspricht

`MASHI` wird in `Database.get_schedule` (`database.py:580–593`) als
Person/Datum/Dienst/Arbeitsplatz/Sicht ausgegeben, **ohne GROUPID oder SHDEM-ID**.
Der angefragte `group_id` ist ein Mitgliedschaftsfilter (`database.py:715`),
keine nachträgliche Einsatzteamzuordnung. Bei Mehrfachmitgliedschaft fehlt
somit reale Information für eine eindeutige Verbindung zur Bedarfszeile.

`sp5_adapter.import_snapshot` (`sp5_adapter.py:453–501`) filtert schrittweise:
Datum/Dienst → mögliche Teams → Arbeitsplatz (einschließlich ungebundenem 0)
→ Maximum ungleich 0. Genau ein Kandidat wird zugeordnet, keiner bleibt
unmatched, mehrere bleiben ambiguous. Die erste fehlgeschlagene Stufe erklärt
die Diagnose; sie beweist nicht, dass alle späteren Stufen korrekt wären.

Die OSP5-Bedarfsansicht liefert hier **keinen Eindeutigkeitsbeweis**:
`Personalbedarf.tsx:384–391` verwendet `reqMap[shift_id][weekday] = r`.
Nach optionalem Teamfilter überschreibt eine spätere Zeile eine frühere mit
demselben Dienst/Wochentag; Arbeitsplatz ist kein Schlüssel. Synthetisch
führen zwei Arbeitsplatzbedarfe dadurch zu einer sichtbaren Zelle, während
der Generator beide Quellbedarfe behält. Dieses Darstellungsverhalten darf
nicht als fachliche Erlaubnis zum Zusammenlegen dienen.

Bestehende Generatorregressionen:
`test_reference_reason_explains_first_failed_filter_without_creating_demand`,
`test_multigroup_reference_requires_unique_group_mapping`,
`test_unmatched_or_ambiguous_reference_never_fabricates_demand`,
`test_date_specific_demand_replaces_holiday_requirement`,
`test_ambiguous_special_demand_never_falls_back_to_regular`.
Library: `tests/test_database_calculations.py:test_utilization_against_demand`
belegt insbesondere SPDEM-Vorrang und „kein Bedarf“ als eigene Kategorie.

### Konkrete Mappinglücken und priorisierte Korrekturen

1. **Nachgewiesener Fehler: DADEM-Teamfilter.** Die Library liefert rohe
   `GROUPID`-Felder, Generator `sp5_adapter.py:196–200` prüft `group_id`.
   Dadurch wird jede solche Zeile als `None` behandelt und zugelassen.
   Synthetische Quelle: Auswahl Team 1, einzige DADEM-Zeile `GROUPID=99`;
   eine fremde Zeile bleibt in `unresolved_native.daily_requirements`.
   Korrektur: Quellfeld korrekt lesen, ausgewählte und globale/ungeklärte
   Werte erhalten, fremde Teams ausschließen; kein DADEM-Soll erfinden.
   Bestehender Test `test_special_and_zero_preserved_not_summed` deckt nur
   das Erhalten einer ausgewählten Zeile ab, nicht den Fremdteamfall.
2. **Nachgewiesene und inzwischen korrigierte Lücke: Sollbuchungen.** `get_bookings` liefert
   `employee_id/date/type/value`; `booking_sum` erwartet `DATE/TYPE/VALUE`.
   Ein bloßes Durchreichen wäre wirkungslos. Der Generator rief im untersuchten Stand
   keine Buchungsquelle auf. Synthetisch: Tagesbasis am arbeitsfreien Feiertag
   plus +2 Stunden Typ 1 ergibt Library-Soll 120 Minuten, Generator 0 Minuten.
   Korrektur: explizite Personen-/Periodenfilterung und Feldnormalisierung,
   negative Werte respektieren, Typ 0 nicht als Soll zählen, Fehler/fehlende
   Quelle niemals als bestätigte leere Liste behandeln. Library zählt
   Buchungen vor Beschäftigungsbegrenzung; vorhandener Test
   `test_nominal_bookings_count_before_clamping` belegt das. Nicht pauschal
   alle offenen Gutschrift-/Saldofragen damit als gelöst markieren.
   Umsetzung: `_nominal_bookings` normalisiert die vorhandene Facade,
   `_Database.get_bookings` liest GET `/api/bookings`;
   `tests/test_nominal_bookings.py` prüft die unten beschriebenen Grenzen.
3. **Korrigiert: Vergleich versus Pflichtdaten.**
   Nicht fixierte, nicht zuordenbare normale Referenzen im Planungszeitraum
   bleiben Diagnose, sind aber keine Pflicht-Einteilungen. Regressionen für
   `reference` und `fixed` prüfen dies einschließlich unabhängiger Validierung. Fixierte ungeklärte
   Einteilungen, Bedarfsunklarheiten und fehlende Freigaben bleiben blockierend.
4. **Fehlende Fachangaben: positive persönliche Freigaben und Profile.**
   In den durchverfolgten RESTR-/Schedule-/Mitgliedschaftspfaden ist keine
   gleichwertige positive, gültigkeitsbezogene Freigabequelle nachgewiesen.
   Dies ist keine Behauptung, sämtliche Originaltabellen seien abschließend
   ausgeschlossen. Historienvorschläge und Ersatzpersonenfilter sind keine
   persönliche Bestätigung. Die vorhandene explizite Einrichtung weiter
   nutzen, aber unbestätigte Platzhalter nicht durch ein zusätzliches Profil
   vermeintlich „überstimmen“. Keine Werte oder Freigaben erfinden.

### Vertiefung: eine direkte Mitgliedschaft, mehrere mögliche Randteams

Synthetischer Nachweis vom 11.09.2026, ohne Originaldatensätze:
`tests/test_hierarchy.py:test_single_direct_membership_does_not_prove_context_assignment_team`
verwendet eine Person ausschließlich in Unterteam 2, dessen Elternteam 1
mit ausgewählt wird. `sp5_adapter.import_snapshot` bewahrt die direkte
Mitgliedschaft `[2]` in `metadata.direct_group_memberships`, erweitert jedoch
die wirksamen `employee.team_ids` auf `[1, 2]` (Vorfahrenexpansion).
Die spätere Randdienstverarbeitung prüft diese **wirksamen**, nicht nur die
direkten Mitgliedschaften: Ohne explizites `row.group_id` ist die Zuordnung
mehrdeutig. Das beweist nicht zwei direkte Mitgliedschaften und auch nicht,
dass die Person tatsächlich im Elternteam gearbeitet hat.

Der Quellpfad erklärt die Informationslücke: Library
`Database.get_schedule` gibt bei MASHI Person/Datum/Dienst/Arbeitsplatz aus,
aber keine Einsatzgruppe; der abschließende `group_id`-Filter verwendet
`get_group_members`. API `sp5api/routers/schedule.py:get_schedule` reicht
den Filter weiter und beschränkt die Personensicht. OSP5
`frontend/src/pages/Schedule.tsx` bildet die Anzeigegruppen über
`groupMembersMap`/`intersectGroupMembers` im `rows`-Aufbau, nicht über eine
nachgewiesene Einsatzgruppe pro Dienst. Keine dieser Stufen ergänzt den
fehlenden Einsatzteambeleg.

Beide Testvarianten erhalten denselben festen Randdienst mit 240 realen
Minuten. Eine nur synthetisch ergänzte explizite Quellgruppe 2 beseitigt
die Gruppenmehrdeutigkeit, **nicht** die weiterhin offene Dienstklassifikation,
Bedarfszuordnung oder Freigabe. Es werden keine Freigaben erzeugt.
Damit ist der nächste Korrekturschritt eingegrenzt: bekannte personenbezogene
Randzeiten für Ruhe-/Stundenprüfungen von einer eventuell unbekannten
Besetzungszuordnung trennen. Vor einer Änderung müssen Teamregeln, fixe
Bedarfe und Kandidatenprüfung erhalten bleiben; einfach alle Kontextfragen
zu ignorieren oder die direkte Gruppe zu wählen wäre keine belegte Lösung.

Gezielte Prüfung: 60 Tests aus `test_hierarchy.py`, `test_partial_limits.py`,
`test_calendar_limits.py` und `test_reference_blockers.py` bestanden. Kein
Laufzeitverhalten geändert; kein neuer Nachweis des fehlenden privaten
600-Sekunden-Jobs und keine erfolgreiche Echtdatenplanung behauptet.

### Tatsächlich vorhandene positive Freigabequelle: Generator-Entwürfe

Die OSP5-Seite `frontend/src/pages/Generator.tsx:48` hat bereits eine
**explizite persönliche Funktions-/Arbeitsplatzfreigabe**: Ein Checkboxklick
ergänzt `employee.approvals` mit Funktion, Arbeitsplatz, Planungszeitraum und
`supervised:false`. `save` (Zeile 31) sendet den gesamten Entwurf an
`POST /api/generator/snapshots`. In der API persistiert
`routers/generator.py:save_snapshot` über `sp5generator.jobs.Store` in
`state_path("generator.sqlite")`, benutzerbezogen; `get_snapshot` liest ihn
wieder. Das ist keine RESTR-/EMPL-Originaltabelle.

`routers/generator.py:import_source` ruft dagegen ausschließlich
`sp5_adapter.import_snapshot` auf, ohne ältere gespeicherte Entwürfe
zusammenzuführen. Auch der eigenständige API-Import liest keine solche
Snapshot-ID. **Ein Neuimport übernimmt daher keine früher in einem
OSP5-Generatorentwurf gesetzten Freigaben.** Falls solche Entwürfe tatsächlich
vorliegen, ist Wiederöffnen/gezielte Wiederverwendung der nachgewiesenen
Freigaben eine andere Datenstrecke als ein frischer Original-SP5-Import.
Ob passende private Entwürfe existieren, wurde hier nicht vorausgesetzt oder
aus fremden Benutzerkonten ermittelt. Übernahme über Personen-, Dienst-,
Arbeitsplatz- und Gültigkeitsgrenzen hinweg ist nicht autorisiert.

Die API-Kompetenzmatrix ist wiederum eine dritte Quelle:
`master_data.py:_skills_path/_load_skills` lädt `state_path("skills.json")`;
`SkillAssignment` enthält Person, Skill, Stufe und `certified_until`, aber
keine Dienst-/Arbeitsplatzfreigabe. Eine Skillzuordnung darf somit ohne
explizites fachliches Mapping nicht als persönliche Dienstfreigabe gelten.
Die Ruheprüfkonfiguration `work_time_rules.py:_load_rules` liegt separat in
`backend_dir()/data/work_time_rules.json`; deren Defaults 10h/48h/6 Tage
sind **keine** zusätzlich vom Nutzer bestätigten Generatorgrenzen.

Randkontext bleibt ebenfalls differenziert: `validator.validate` meldet
`context_complete=False` als `context`, macht damit `complete=False`, aber
nicht allein `valid=False` (`validator.py:421–428`). Der Import hält darüber
hinaus ausdrücklich zu klärende Kontextfragen in `unresolved`; diese blockieren
schon den Eingabevorcheck. Nicht beide Ebenen als denselben Fehler ausgeben.

### Prüfstand dieses Analyseschritts

Generator: **165 Tests bestanden** (`test_sp5_adapter.py`,
`test_api_adapter.py`, `test_input_boundaries.py`, `test_core_rules.py`).
Library: **84 Tests bestanden** (`test_calculations.py`,
`test_database_calculations.py`, `test_eligible_replacements.py`), ausgeführt
mit der bestehenden Generator-Testumgebung, da die Library keine eigene
`.venv` besitzt. API/OSP5-Pfade wurden gelesen, nicht als vollständige
API-/Browser-Testabnahme ausgegeben. Die zusätzlichen Minimalreproduktionen
oben verwenden ausschließlich neu erzeugte synthetische Strukturen.

Anschließende gezielte Quellprüfung: **11 API-Generator-Routentests**
(`tests/generator/test_routes.py`, `test_demo.py`) und **3 OSP5-Generator-
Komponententests** (`frontend/src/generator/generator.test.tsx`) bestanden.
API-Tests mit isoliertem temporärem Backend und ohne übergeordnete
Originaldaten-Fixtures ausgeführt. Die Routentests decken insbesondere
Eigentümerisolation, Snapshotversionen und Sichtbarkeitsgrenzen ab; die
Komponententests Speichern tatsächlicher Änderungen und Ergebnisfehler.
Kein vollständiger Browser-End-to-End-Nachweis für persönliche Freigaben.

### Erste abgeleitete Korrektur: DADEM-Scope

Der oben am Ausgangsstand reproduzierte DADEM-Feldnamenfehler ist korrigiert:
`GROUPID` wird als originales Quellfeld gelesen; `group_id` bleibt für bereits
normalisierte Quellen kompatibel. Globale und fehlende Gruppenzuordnungen
bleiben sichtbar ungeklärt. Aus DADEM entstehen weiterhin keine erfundenen
Schichtbedarfe, Freigaben oder bestätigten Profile.

`test_daily_requirement_team_scope_preserves_unresolved_semantics` prüft
beide Feldformen jeweils für ausgewähltes Team, fremdes Team, 0 und None.
Vor Änderung: **1 fehlgeschlagen, 7 bestanden**; nach Änderung:
**gesamte Generator-Pythonsuite 411 bestanden**. Das behebt einen echten
Scopefehler, aber weder fehlende Sollbuchungen noch fehlende Freigaben oder
sämtliche Ursachen uneindeutiger Referenzen.

Kein neuer Echtdatenlauf für unveränderte Version 0.9.29: dessen unmittelbar
vorheriger privater Ist/Soll-Prüfnachweis bleibt im Automation-Scratch.
Keine erfolgreiche Neuplanung oder Freigabe wird aus diesen Quell- und
Regressionstests abgeleitet. Keine Änderung produktiver Originaldaten.

## Gezielte Untersuchung des gemeldeten 0.9.29-Teilplans

Der Nutzer meldet nach 600 Sekunden einen Teilplan mit nicht eingeplanten
Personen, 24h-Diensten und überschrittenen Wochenstunden. Die folgenden
Minimalfälle sind **keine Reproduktion dieses konkreten Plans**. In den
bereits vorhandenen privaten Audit-JSONs wurden rekursiv 32 Ergebnisobjekte
gefunden: ausschließlich MODEL_INVALID bei 30/60 Sekunden, kein
600-Sekunden-Ergebnis. Erforderlich bleiben zusammengehöriger Projektstand,
Jobparameter und Ergebnis inklusive Snapshot-Hash, wirksamer Profile und
Randdienste. Diese Daten gehören ausschließlich in die private lokale Prüfung.

### Stundenbegriffe über alle vier Komponenten

| Datenfluss | Nachgewiesene Bedeutung | Folge für die Fehlersuche |
| --- | --- | --- |
| `SHIFT.STARTEND{idx}` → Library `parse_startend` → API `_collect_day_data` → OSP5-Dienstanzeige → Generator `Shift.segments` | Zeitfenster eines Diensts; gleiches Anfangs-/Ende außer dem leeren 00:00-Slot bedeutet Tageswechsel | `08:00-08:00` wird als 24h-Spanne importiert; nicht aus Sollstunden berechnet |
| `SHIFT.DURATION{idx}` → Library `shift_hours_on_day` → API `_collect_day_data.day_hours` → Generator `paid_minutes` | angerechnete Stunden; können von den Zeitfenstern abweichen | Ein 24h-Zeitfenster kann 8h bezahlt sein; Stundenanzeige allein beweist keine Dauergrenze |
| `EMPL.CALCBASE/HRS*` → Library `get_nominal_hours` → Generator `target_minutes` | Sollwert für den angefragten Zeitraum | `HRSWEEK=40` ist keine automatisch importierte harte 40h-Grenze |
| API `work_time_rules.py:_load_rules/_check_employee` → OSP5-Arbeitszeitprüfung | separates Zusatzwerkzeug; Tages-/Wochenprüfung summiert DURATION am Startdatum; wahlweise feste Grenze oder Sollmodell × Faktor | Kein gleichwertiger Ersatz für die unabhängige Generatorprüfung, keine automatische Übernahme dieser Konfiguration |
| OSP5 `Generator.tsx` Profilformular → Snapshot → Generator `RuleProfile.max_daily_minutes/max_weekly_minutes` | explizite Höchstgrenzen in Minuten, wirksam über Personenprofil-ID und Gültigkeit | Nur tatsächlich zugeordnete Grenzen gelten; ein zusätzliches unzugeordnetes Profil ändert nichts |

Quellbelege: Library `calculations.py:parse_startend/shift_hours_on_day`, API
`routers/work_time_rules.py:_collect_day_data/_check_employee`, OSP5
`frontend/src/pages/Generator.tsx:53`, Generator
`sp5_adapter.py:import_snapshot`, `timeutils.py:day_minutes`,
`solver.py:solve`, `validator.py:_validate`. API-Adapter `_Database` importiert
keine `/api/work-time-rules`-Konfiguration. Das Importprofil enthält 660/2160
Minuten Ruhe, aber **keine** Tages-/Wochenhöchstzeit. Diese nicht gesetzten
Grenzen wurden weder heimlich ergänzt noch aus API-Defaults oder Sollwerten
abgeleitet.

Zusätzlicher isolierter Test der tatsächlichen API-Funktionen (per AST geladen,
synthetische `_read`-Tabellen, keine Originaldaten und kein Live-POST):
`08:00-08:00`, DURATION=8 ergibt einen 24h-Block und 8 Tagesstunden.
Die API-Prüfung mit Tagesgrenze 10h und Wochengrenze 40h meldet dafür keinen
Stundenverstoß. Der Generator prüft demgegenüber die aufsummierten tatsächlichen
Segmentminuten je lokalem Tag und Montag–Sonntag. Diese unterschiedliche
Prüfsemantik muss bei einem Ergebnisvergleich ausdrücklich berücksichtigt werden.
Sie belegt nicht, welche Grenze im gemeldeten Nutzerprojekt konfiguriert war.

### Was die synthetischen Gegenproben belegen

`tests/test_partial_limits.py` prüft unabhängig ausgerechnete Erwartungen:

- Zwei 8h-Dienste mit je 1h Bezahlung überschreiten ein gemeinsames 8h-Tageslimit.
  Im Teilmodus wird nur einer gewählt; im strikten Modus ist das Modell unlösbar.
- Ein fixierter 8h-Randdienst in derselben Woche verhindert einen weiteren
  8h-Dienst bei 15h-Wochenmaximum, auch mit hohem Soll und geringer Bezahlung.
- Drei 24h-Dienste können 11h tägliche und 36h wöchentliche Ruhe erfüllen.
  Ohne Wochenmaximum sind sie zulässig; mit ausdrücklich gesetzten 40h wird
  im synthetischen Beispiel nur einer gewählt. Es wird kein allgemeines
  Verbot von 24h-Diensten oder ein Nutzer-Wochenmaximum behauptet.
- Das bestehende Tagesmaximum ist eine **Kalendertagssumme**, keine
  Einzel-Dienstlängengrenze. 12:00–12:00 am Folgetag erfüllt ein konfiguriertes
  12h-Tagesmaximum mit je 720 Minuten auf beiden Tagen; 719 Minuten lehnt
  denselben Dienst ab. Ein zusätzliches Maximum je Dienst existiert im
  derzeitigen `RuleProfile` nicht und wurde nicht erfunden.
- Überschneidung, fehlende 11h-Ruhe und zwei Positionen im selben Dienst
  bleiben auch im Teilmodus ausgeschlossen. Strengere zugeordnete Profile
  werden nicht durch weniger strenge Profile überstimmt.
- Herbst-Zeitumstellung: lokal 00–04 Uhr sind 300 tatsächliche Minuten.
  Ein Dienst über Sonntag/Montag wird auf lokale Tage und ISO-Wochen aufgeteilt;
  der Jahreswechsel verwechselt nicht Kalenderjahr und ISO-Wochenjahr.
- UNKNOWN in der Qualitätsphase erhält einen zuvor unabhängig geprüften
  Teilplan als FEASIBLE; UNKNOWN ohne geprüfte Lösung liefert keine Einteilungen.
  Teilmodus lockert Mindestbesetzung, nicht persönliche harte Regeln.
- FEASIBLE kann bereits aus der ersten Teilplanphase `vacancies` stammen.
  Dann wurde die Optimierung von Sollabweichung/Blockkosten noch nicht begonnen:
  Erst nach OPTIMAL für die offenen Mindeststellen fixiert `solve` deren Zahl
  und startet die gewichtete Qualitätsphase. `metrics.objective_phase` muss
  deshalb mitgelesen werden; 600 Sekunden Suchzeit garantieren keine optimierte
  Stundenverteilung. Der Statuszweig ist deterministisch regressionsgeprüft.
- Drei geeignete Personen bei Höchstbesetzung eins führen rechtmäßig zu zwei
  nicht eingeplanten Personen. Alle einzuplanen wäre eine neue, falsche Pflicht.

19 dieser Import-/Regel-/Statusprüfungen wurden zusätzlich in einem separaten
synthetischen Checkout des dokumentierten 0.9.29-Releasecommits
`714b9f7284364263ae1be03e3a21a9a552f25525` ausgeführt und bestanden; der geladene
Solverpfad wurde geprüft. Damit ist in diesen Fällen **kein** Umgehen gesetzter
Grenzen durch 0.9.29 reproduziert. Ein Zeitablauf wurde deterministisch über den
Solverstatus simuliert, nicht als 600-Sekunden-Lasttest ausgegeben.

### Behobene Diagnoselücke: nicht eingeplante Personen

Die bisherigen Engpasshinweise waren bedarfsbezogen. `solve` ergänzt jetzt
`metrics.planning_diagnostics` mit tatsächlichen Kandidatenzahlen und
Ausschlussgründen je Person, ohne zusätzliche Kandidatenprüfung oder Änderung
der Zielfunktion. Die Zahlen zählen **Bedarfszeilen**, nicht Personen oder
garantiert gemeinsam machbare Dienste; mehrere Ausschlussgründe können für
dieselbe Zeile gelten. Fixierter Kontext zählt nicht als neuer Einsatz.

Die Gründe unterscheiden `assigned`, `no_positive_capacity_demand`,
`individually_ineligible`, `not_selected_with_candidates` und `no_valid_plan`.
Freigabe, Beschäftigungszeitraum, Team und Verfügbarkeit kommen direkt aus
`domain.eligibility`; Maximum 0 wird gesondert erfasst. Optionale Bedarfe und
Mindestbedarfe bleiben unterscheidbar. Die konfigurierten Zielgewichte werden
mitgeliefert. „Kandidaten vorhanden, nicht ausgewählt“ behauptet weder, dass
eine gemeinsame Lösung möglich wäre, noch welches Gewicht kausal entscheidend
war. Harte Regeln und globale Konkurrenz müssen weiterhin mitgeprüft werden.
Bei abgebrochener Kandidatensuche oder ungültiger Eingabe werden keine
unvollständigen Kandidatenzahlen als abschließende Diagnose veröffentlicht.

33 neue Regressionen, gesamte Generator-Pythonsuite: **444 bestanden**.
Die Diagnose liegt im strukturierten Ergebnis/JSON und damit auch in der
bestehenden „Technischen Auswertung“; keine neue UI, keine
automatische Profilbestätigung, keine Freigabenübernahme und keine Veröffentlichung
realer Planungsdaten. Priorisiert offen bleiben die genaue private Reproduktion,
Sollbuchungen und die Trennung von Vergleichsreferenzen und Planungsblockern.

### Zusätzliche belegte Zielwirkung: lineares Sollziel garantiert keine Verteilung

`test_linear_hours_target_can_tie_while_block_goal_concentrates_work`
reproduziert eine bislang nicht ausdrücklich belegte Konstellation: drei
geeignete Personen mit jeweils 40h Soll, drei aufeinanderfolgende 8h-Dienste,
11/36-Ruhe, höchstens eine Person je Dienst. Sowohl Verteilung auf alle drei
als auch Konzentration auf eine Person sind vollständig gültig.

`solver.solve` bewertet Stunden mit `add_abs_equality`: Solange alle Personen
unter Soll bleiben, ist die Summe der absoluten Abweichungen in beiden
Varianten **5760 Minuten**. Ein höheres Gewicht dieses unveränderten linearen
Stundenziels allein löst diesen Gleichstand nicht. Das Blockziel bevorzugt
bei Gewicht 100 zwei statt sechs Arbeits-/Freizeitwechsel. Die synthetische
OPTIMAL-Lösung plant deshalb nur eine Person ein (Wertung 5760 + 200).
Andere Zielgewichte sind im Minimalfall explizit null, um den Effekt isoliert
nachzuweisen. Keine Aussage über die unbekannten Gewichte des Nutzerprojekts.

Das ist eine bewiesene Wirkung der bestehenden Zielfunktion, **kein Beleg
einer Verletzung harter Regeln**. Eine automatische Mindestzahl von Diensten
pro Person wäre keine korrekte Reparatur. Ein künftiges weiches Verteilungsziel
müsste Unterdeckung, individuelle Sollwerte und zulässige Einsatzmöglichkeiten
berücksichtigen und seinen Zielkonflikt mit möglichst langen Freizeitblöcken
offenlegen. In diesem Schritt bleiben alle Gewichte und Regeln unverändert.

## Sollstunden: Einheit folgt der Berechnungsbasis

1. Originalfelder `EMPL.CALCBASE`, `HRSDAY`, `HRSWEEK`, `HRSMONTH`,
   `HRSTOTAL`, Beschäftigungsdaten und Arbeitstage werden in
   [`EmployeeContext.from_record`](https://github.com/mschabhuettl/libopenschichtplaner5/blob/0dac4438c0be02c1ad612f54d4aba75a3e4d6335/sp5lib/calculations.py#L150)
   übernommen.
2. [`get_nominal_hours`](https://github.com/mschabhuettl/libopenschichtplaner5/blob/0dac4438c0be02c1ad612f54d4aba75a3e4d6335/sp5lib/calculations.py#L398)
   addiert Sollbuchungen vom Typ 1 und dispatcht nach CALCBASE:
   0/Tagesbasis, 1/Kalenderwochen, 2/Kalendermonate, 3/Gesamtzeitraum.
   Teilwochen und Teilmonate verwenden nicht einfach einen pauschalen
   Monats-/Wochenfaktor, sondern die implementierte Arbeitstagszerlegung.
3. Die API verwendet dieselbe Library beispielsweise in der
   [modellbezogenen Wochenprüfung](https://github.com/mschabhuettl/openschichtplaner5-api/blob/d578f212d635b672ab277d7d29a37387145506f5/sp5api/routers/work_time_rules.py#L247).
   Das ist eine ausdrücklich gewählte Prüfart, keine Erlaubnis,
   Generator-Höchststunden aus Sollstunden abzuleiten.
4. Die Originaloberfläche bietet im
   [Personenformular](https://github.com/mschabhuettl/openschichtplaner5/blob/addf5c2d1e40b4f266bacf1cd41f40ef70edbeb8/frontend/src/pages/Employees.tsx#L1054)
   genau diese vier Berechnungsbasen an.
5. Der Generator ruft in `sp5_adapter.import_snapshot` die Library auf und
   speichert Quellenwerte, Zeitraum und Ergebnis in `provenance.nominal_hours`.
   Verfügbare Sollbuchungen werden über `_nominal_bookings` nach Person,
   angefragtem Monat und exaktem Zeitraum gefiltert und von
   `date/type/value` auf `DATE/TYPE/VALUE` normalisiert.
   `bookings_included=false` bleibt bei fehlender Facade erhalten;
   Fehler einer vorhandenen Quelle brechen den Import ab.

Die vorhandene Library-Regression `test_nominal_month_base_full_months`
prüft zwei volle Monate gegen zweimal das Monatsbudget. Die Generator-
Regressionen prüfen CALCBASE und die Quellenprovenienz synthetisch.
Eine pauschale Umstellung aller Personen auf Monats- oder Wochenstunden
wäre mit diesem Codefluss nicht vereinbar. Zeitgutschriften und
Anfangssalden bleiben ein eigenständiger offener Mapping-Prüfpunkt.

### Sollbuchungs-Korrektur und Grenzen

- Vorhandene API/Library werden verwendet, keine zusätzliche Stundenformel.
- Typ 1 wird vor der Beschäftigungsbegrenzung addiert; signierte Werte
  bleiben erhalten. Typ 0 wird weder als Soll noch automatisch als
  Zeitgutschrift oder Anfangssaldo übernommen.
- Mehrere identische Buchungswerte können legitime getrennte Buchungen
  sein: keine wertbasierte Deduplizierung. Monatsfilter verhindert ein
  erneutes Zählen derselben Monatszeilen bei Jahreswechsel.
- Herkunft enthält Anzahl und Summe der Sollbuchungen sowie das
  ungekappte `source_target_minutes`. Negative Gesamtwerte passen nicht
  in den bestehenden nichtnegativen Zielstundenvertrag; der Import
  behält den Quellwert und einen ausdrücklichen Planungsblocker.
- Lokale DBF-Quellen: `SP5Database._read` liefert bei Dateifehlern und
  `read_dbf_buffer` bei zu kurzem Header ebenfalls eine leere Liste.
  Deshalb werden Dateizugriff und BOOK-Pflichtfelder vor dem Abruf
  geprüft. Fehlende Tabelle bleibt unbekannt; abgeschnittene Header,
  fehlende Pflichtfelder oder fehlender Zugriff brechen den Import ab.
  Die API kann dagegen eine serverseitig fehlende Datei hinter `[]`
  verbergen: `bookings_included=true` bestätigt nur den Abruf, nicht
  die Existenz/Vollständigkeit der entfernten Datenbank.
- HTTP 403/404, fehlerhafte Listen und unvollständige relevante Buchungen
  werden nicht als bestätigte Null behandelt. API-Antworten nehmen an
  der bestehenden wiederholten Konsistenzprüfung teil. Deren Grenzen
  hinsichtlich Sichtbarkeit und fehlender Quelltransaktion bleiben.
- Synthetische Regressionen: signierte Werte, Typtrennung, Personen-/
  Periodenfilter, Beschäftigungsrand, Monats-/Jahreswechsel, bekannte
  leere versus fehlende Quelle, fehlerhafte Werte und API-Zugriffsfehler.
- Weder harte Tages-/Wochenlimits noch Freigaben oder Solverziele ändern
  sich. Die Korrektur erklärt nicht ohne Originaleingabe den gemeldeten
  600-Sekunden-Plan; sie entfernt eine belegte Ursache falscher Sollwerte.

## Ist/Soll, Sonderdienste und Teamfilter

- [`Database.get_schedule`](https://github.com/mschabhuettl/libopenschichtplaner5/blob/0dac4438c0be02c1ad612f54d4aba75a3e4d6335/sp5lib/database.py#L546)
  übernimmt `MASHI.TYPE` als `schedule_type`. Der tatsächlich ausgeführte
  Filter ab Zeile 703 unterscheidet reguläre Ist-/Solldienste; Sonderdienste
  und Abwesenheiten bleiben planartneutral. Danach wird über die Mitglieder
  der angefragten Gruppe gefiltert. Sonderdienst-TYPE darf nicht als
  Ist-/Soll-Kennung interpretiert werden.
- Der [API-Endpunkt](https://github.com/mschabhuettl/openschichtplaner5-api/blob/d578f212d635b672ab277d7d29a37387145506f5/sp5api/routers/schedule.py#L29)
  validiert `ist/soll/both`, übergibt die Sicht und berücksichtigt anschließend
  sichtbare Personen und Abwesenheitsrechte. Der Generator darf diesen Scope
  nicht als Vollständigkeitsnachweis außerhalb der sichtbaren Personen werten.
- Die OSP5-Anzeige bietet dieselben drei Sichten in
  `frontend/src/pages/Schedule.tsx` (Soll-/Istplan-Auswahl). Der Generator
  übergibt in `api_adapter._Database.get_schedule` die ausgewählte Sicht;
  normale Vergleichsdienste, Historie und Ist-Randkontext bleiben getrennt.
- Generator-Bedarfe entstehen aus den Bedarfsdaten, nicht aus der Anzahl
  historischer oder aktueller Einteilungen. Arbeitsplatz, Team und Datum
  müssen passen; MAX=0, fehlende Bedarfe und mehrdeutige Zuordnungen dürfen
  nicht durch erfundene Bedarfe verschwinden.

## Persönliche Freigaben und Regeln

Der Generator legt beim Import leere persönliche Freigaben und einen
unbestätigten Importprofilplatzhalter an. `history_approvals.py` ist eine
separate, ausdrücklich ausgelöste Historienübernahme; individuelle oder
betreute Freigaben werden dort geschützt. Historie ist kein Qualifikations-
oder genereller Freigabenachweis. Bestehende Dienstzuordnungen allein
berechtigen nicht zur zukünftigen Einteilung.

Die API besitzt eine eigene 11-Stunden-Ruheprüfung (`work_time_rules.py`),
deren Warnungs-/Fehlereinstufung nicht mit dem harten Generator-Vertrag
verwechselt werden darf. Die neuen Generator-Startwerte **11 Stunden täglich,
36 Stunden je Kalenderwoche einschließlich täglicher Ruhe** stammen aus dem
ausdrücklichen Nutzerauftrag, nicht aus einer behaupteten gesetzlichen oder
universellen Original-SP5-Regel. Importprofile bleiben unbestätigt. Andere
Grenzen, Gültigkeiten, Kontextbestätigungen und Freigaben bleiben unverändert.

## Weiche Blockplanung

Der bestehende Solver hat bereits lokale Arbeitstagsvariablen aus den
konkreten Dienstsegmenten, einschließlich über Mitternacht reichender Dienste
und fixierter Randdienste. Das neue Ziel nutzt diese Variablen mit
`add_abs_equality` für Arbeits-/Freizeitwechsel an beiden Periodenrändern und
zwischen den Planungstagen. Es führt keine maximale Blocklänge ein.

Neue Importe/Projektanlagen starten mit Gewicht 100. Alte gespeicherte
Projekte erhalten für das neue optionale Ziel Gewicht 0; Aktivierung bleibt
ausdrücklich. Weniger Wechsel fördern zusammenhängende Blöcke und freie Tage,
maximieren aber nicht mathematisch die längste minutengenaue Freizeit.
OPTIMAL bezieht sich auf die gewichtete Gesamtwertung; FEASIBLE besitzt keinen
Optimalitätsnachweis. Die unabhängige Regelprüfung bleibt maßgeblich.


## Referenzdiagnose ist keine Pflicht-Einteilung

Isolierter synthetischer Gegenbeweis in `tests/test_reference_blockers.py`:
Eine vollständig eingerichtete Quelle enthält genau einen zu besetzenden
Bedarf für Dienst A und einen ausdrücklich nicht fixierten Vergleichsdienst B
ohne Bedarf. B erzeugte über `sp5_adapter.import_snapshot` dennoch einen
Eintrag in `Snapshot.unresolved`; `domain.input_diagnostics` machte deshalb
den gesamten neuen Plan `MODEL_INVALID`. Nach Entfernen ausschließlich
dieses Vergleichsblockers löst derselbe Bedarf unabhängig vollständig geprüft.

Der Import setzt bei ungeklärten normalen In-Perioden-Referenzen jetzt
`planning_blocker` gemäß `existing_plan_mode == "fixed"`. Diagnose,
Quellreferenz, Kandidatenliste und Ablehnungsgrund bleiben erhalten. Nur
explizit verlangte, nicht auflösbare Fixierungen werden weiterhin zu
`unresolved`. Bedarf, Freigaben, Profile, Abwesenheiten, Rand-Einteilungen
und Sonderdienste werden nicht ergänzt oder bestätigt. Es gibt keine
automatische Bereinigung bereits gespeicherter Projekte.

Die Regressionen prüfen Ist/Soll jeweils in Vergleichs- und Fixierungsmodus
sowie fehlende Freigaben, unbestätigte Profile, sonstige Pflichtangaben
und unbestätigten Randkontext. Letzterer hat bereits im bestehenden Vertrag
eine eigene Bedeutung: vorläufige Einteilungen sind möglich, die unabhängige
Validierung bleibt aber `complete=false` mit `context`-Diagnose. Ein
`OPTIMAL`-Solverstatus ersetzt diesen Vollständigkeitsnachweis nicht.

## Reproduzierter Verlust einer Höchstgrenzen-Zuordnung in 0.9.29

`static/profile-groups.js:ProfileGroups.apply` erkannte ersetzbare Platzhalter
bisher ausschließlich an ID `sp5:unconfirmed`, `confirmed=false` und
`source=unresolved`. Dieser Code ist bytegleich mit dem untersuchten
0.9.29-Stand `714b9f7`. Im Profileditor eingetragene Grenzen ändern diese
Kennzeichen nicht.

Synthetischer Ablauf: In dieses noch unbestätigte Importprofil werden
2400 Wochenminuten eingetragen. Die Sammelaktion ordnet anschließend ein
bestätigtes Profil ohne Wochenmaximum zu. Die ursprüngliche Profildefinition
bleibt zwar gespeichert, ihre Zuordnung zur Person wird aber entfernt;
der Solver erhält für diese Person kein entsprechendes Wochenmaximum mehr.
Das ist ein belegter Fehlerpfad, **kein Beweis**, dass der nicht vorliegende
600-Sekunden-Nutzerlauf genau so entstanden ist. 2400 Minuten sind ein
synthetischer Testwert, kein angenommenes Nutzermaximum.

Die Sammelzuordnung schützt jetzt auch unter der ursprünglichen Import-ID
bereits eingetragene Tages-, Wochen-, Perioden-, Arbeitstage-, Nacht-,
Wochenend- und Serienhöchstgrenzen, einschließlich einer Grenze von null.
Das alte Profil bleibt zugeordnet und unbestätigt, bis es gezielt geprüft
wird. Ruheminima werden nicht durch niedrigere Werte ersetzt; unterschiedliche
aktive Wochenruhe- oder Nachtblock-Bezüge werden nicht pauschal verglichen.
Unveränderte Platzhalter ohne solche Grenzen und Personen ohne Profil bleiben
über die bestehende Sammelaktion zuordenbar. Es gibt keine automatische
Bestätigung, neue Höchstgrenze oder Rekonstruktion schon verlorener Zuordnungen.

Belege: `tests/browser/profile-groups.cjs` prüft alle acht Höchstgrenzenfelder
mit null und positiven Werten sowie Ruhe-/Bezugsänderungen. Der komplette
Browserablauf trägt das Wochenmaximum im echten Formular ein, betätigt die
Sammelaktion, speichert und lädt neu; die Person behält ihr unbestätigtes
Profil samt 2400-Minuten-Grenze, während eine Person ohne Profil das
gewählte bestätigte Profil erhält. Tages-/Wochenfelder speichern bereits
Minuten unverändert; die vorhandenen Browserchecks belegen 720/2400 Minuten.
Nur das separate Perioden-Soll wird von Stunden in Minuten umgerechnet.

## Randzeit ist derzeit an Besetzungszulässigkeit gekoppelt

`sp5_adapter.import_snapshot` legt bekannte Randzeiten als `Shift` mit
`source=sp5:existing`, `kind=unconfirmed`, künstlichem `Position` und einem
`Demand(minimum=1, maximum=1)` samt fixer `Assignment` an. Das erhält die
Zeitintervalle, ist aber kein unabhängiges personenbezogenes Arbeitszeitkonto.
Die Gruppen-/Bedarfsdiagnosen sind deshalb nicht der einzige Blocker.

`domain.eligibility` prüft auch diese Einteilungen auf Team, Diensttyp,
persönliche Freigabe, Beschäftigung, Abwesenheit und Verfügbarkeit.
`solver.solve` beendet sich bei einer unzulässigen Fixierung mit
`INFEASIBLE/fixed_conflict`; `validator._validate` prüft dieselbe Zulässigkeit
vor der Summierung der Arbeitszeiten. `profiles_for` ist hingegen bereits
personen- und datumsbezogen, nicht teambezogen.

Sechs synthetische Regressionen in
`test_partial_limits.test_fixed_boundary_time_still_requires_assignment_eligibility`
belegen für Voll- und Teilplanung: Selbst ohne Eingabediagnosen blockiert ein
Randdienst wegen fehlender damaliger Freigabe, ungeklärtem Team oder Diensttyp.
Im Freigabefall ist der neue Dienst ausdrücklich weiterhin freigegeben; nur
der historische Tag liegt außerhalb der Freigabegültigkeit. Der unabhängige
Validator benennt den Randbedarf, der Solver liefert keine Einteilungen.

**Priorisierte Korrekturrichtung, noch nicht implementiert:** bestätigte
personenbezogene Randintervalle getrennt von zu besetzenden Bedarfen abbilden.
Sie müssen weiterhin zwingend in Überlappung, tägliche/wöchentliche reale
Minuten, Ruhe und Serien eingehen. Unbekannte Nachtart darf nicht verschwinden;
Quellvollständigkeit und tatsächliche Zeitabweichungen bleiben eigene
Bestätigungsfragen. Historie darf keine zukünftige Freigabe erzeugen. Das
pauschale Löschen von `unresolved`, Umbenennen von `unconfirmed` oder Umgehen
von `eligibility` für beliebige Fixierungen ist kein geeigneter Fix.

### Durchgängiger Importbeleg statt nur handgebauter Solver-Eingabe

`tests/test_hierarchy.py:test_single_direct_membership_does_not_prove_context_assignment_team`
prüft jetzt beide Teamvarianten jeweils als Voll- und Teilplanung bis zum
Solver und unabhängigen Validator. Der unveränderte synthetische Import
ergibt `MODEL_INVALID` mit `profile` und `unresolved`, also vor dem CP-SAT-Lauf.
Nach ausschließlich **synthetischer** Auflösung dieser Eingangsvoraussetzungen
und einer Freigabe ab dem Planungstag bleibt der Vortagsdienst unzulässig:
Validator `approval`, Solver `INFEASIBLE/fixed_conflict`. Es wird kein Plan
ausgegeben. Eine eindeutige Quellgruppe allein behebt diese Kopplung nicht.
Das bewusste Entfernen von Diagnosen im Test isoliert den Fehlerpfad und ist
ausdrücklich keine Anleitung zur Behandlung echter Importe.

## Zeit-Slots: OSP5-Hover ist keine verlässliche Vergleichsreferenz

Lesestand: Library `0dac443`, API `d578f21`, OSP5 `addf5c2` (jeweils sauberer
Checkout). Der folgende Befund betrifft den **Hovertext**, nicht pauschal
alle OSP5-Zeitberechnungen oder die unbekannte Nutzerinstallation:

- `sp5lib/calculations.py:day_index` verwendet Montag=0 bis Sonntag=6,
  Feiertag=7 für `STARTEND`, `DURATION` und Bedarfs-Lookups.
- `sp5lib/database.py:SP5Database.get_shifts` gibt diese Originalfelder weiter
  und baut `TIMES_BY_WEEKDAY` ausdrücklich mit `range(7)` auf, ebenfalls
  Montag=0 bis Sonntag=6; ein Feiertagsslot wird dort nicht ergänzt.
- `sp5api/routers/master_data.py:get_shifts` reicht die Library-Daten durch.
  `schemas.py:ShiftResponse` erbt `extra=allow`, also keine Umnummerierung
  der weiteren `STARTEND`-Felder. Der Generator liest diese Felder über
  `api_adapter._Database.get_shifts` und `sp5_adapter.import_snapshot`.
- OSP5 `frontend/src/pages/Schedule.tsx` lädt mit
  `api.getShifts().then(setShifts)` unveränderte Typdaten. Im Hoverbereich
  (um Zeile 1633) liefert `jsWdToDbWd` korrekt Montag=0, danach werden aber
  **`STARTEND${dbWd + 1}` und `TIMES_BY_WEEKDAY[String(dbWd + 1)]`** gelesen.
  `STARTEND0` dient dort als Fallback. Die erste Auswahl verschiebt Montag
  auf Dienstag und Sonntag auf den Feiertagsslot; der abweichende
  `TIMES_BY_WEEKDAY`-Override korrigiert das für Montag bis Samstag nicht.
  Die Auswahl enthält auch keine datumsspezifische Feiertagsprüfung.

Damit kann dieser Tooltip bei unterschiedlichen Tagesfenstern eine andere
Zeit als die Library/Generator-Planung anzeigen. Identische Fenster an allen
Wochentagen verdecken den Fehler. Kein Browsernachweis für die echte
Installation und **kein Beleg**, dass dies die gemeldeten 24h-Dienste oder
Wochenüberschreitungen verursacht. Eine Generator-Umnummerierung wäre falsch.
Die bestehende allgemeine Tabellenbezeichnung „OSP5-Dienstanzeige“ oben darf
nicht als Nachweis identischer Zeitdarstellung in allen Komponenten gelten.

16 neue synthetische HTTP-Regressionen in
`test_api_adapter.test_http_time_slots_match_library_for_demand_and_boundary`
prüfen alle acht Slots jeweils für neue Bedarfsdienste und feste Randdienste.
Jeder Slot hat ein anderes Zeitfenster und andere bezahlte Stunden.
Nach Import stimmen Fenster und Feiertagsauswahl mit Library `day_index` und
`parse_startend` überein: jeweils 90 reale Minuten, davon unabhängige bezahlte
Minuten. Der Test erhält fehlende persönliche Freigaben und den Fixierungsstatus;
er behauptet keine Planbarkeit des unbestätigten Imports.

Priorität bleibt die unabhängige Darstellung personenbezogener Randarbeit
und ihre vollständige Einbeziehung in harte Grenzen. Den OSP5-Hoverfehler
separat korrigieren, nicht als Solverfix verkaufen. Produktiven API-/OSP5-Code
hat diese Untersuchung nicht verändert; keine neue Laufzeitlogik oder Release.

## Neuer Grenzbefund: Dienstüberhang nach dem letzten Planungstag

Im Stand `a910623` begrenzten `solver.solve` und `validator._validate` die
Tages-/Wochenhöchstprüfungen auf Profiltage innerhalb der Planungsperiode.
`timeutils.day_minutes` zerlegte überhängende Intervalle korrekt; die Minuten
des Folgetags bzw. der nächsten ISO-Woche wurden aber nicht gegen deren Grenze
geprüft, wenn diese Kalenderzelle außerhalb der Periode lag.

Synthetisch nachgewiesen (kein Original-Nutzerjob):

- Ein-Tages-Plan Montag, Dienst 20:00 bis Dienstag 16:00, gültiges Tagesmaximum
  720 Minuten: 240 Minuten am Montag, **960 am Dienstag**. Bisher akzeptiert.
- Ein-Tages-Plan Sonntag, Dienst 23:00 bis Montag 08:00, gültiges Wochenmaximum
  420 Minuten: 60 Minuten in der alten, **480 in der nächsten ISO-Woche**.
  Bisher ebenfalls akzeptiert.

Beide Fälle lieferten vor der Korrektur in Voll- und Teilplanung `OPTIMAL`,
eine Einteilung und `validation.valid=true`. Vier neue Regressionen schlugen
zunächst am unabhängig aufgerufenen Validator fehl. Das ist ein gemeinsamer
Prüfbereichsfehler, keine Lockerung durch Teilplanung oder Zeitbudget.

Die Korrektur lässt eine gewählte In-Perioden-Einteilung die zusätzlichen
Tages-/Wochenprüfungen ihres Überhangs aktivieren. Solverbedingungen sind an
die jeweilige Auswahlvariable gebunden; der Validator erweitert seinen
Prüfbereich aus den tatsächlich gewählten Einteilungen. Beide summieren
vorhandene fixe Folgezeiten mit. Nur zugeordnete, am Überhangtag gültige
Profile gelten; es wird weder ein Wochenmaximum erfunden noch ein
abgelaufenes Profil verlängert. Periodenmaximum und bezahlte Sollbewertung
werden nicht auf den Folgezeitraum ausgeweitet.

18 Regressionen in `tests/test_partial_limits.py` prüfen die beiden Fehler,
exakte Grenzwerte einschließlich fixer Folgezeiten, nicht gewählte Kandidaten,
Profilzuordnung/-gültigkeit und unveränderte Perioden-/Bezahlminuten.
Unabhängige Gegenprobe: Ein nur möglicher Überhang darf nicht sämtliche
Teilpläne wegen eines sonst nicht betroffenen zukünftigen Kontextverstoßes
unzulässig machen.
Bei langen Überhängen muss außerdem der bestätigte Randkontext bis zum Ende
der letzten zusätzlich geprüften ISO-Woche reichen. Andernfalls bleibt die
Validierung ausdrücklich unvollständig, auch bei `OPTIMAL`.

Quellabgrenzung bleibt wichtig: Library `Database.get_schedule` liefert die
Einteilung am Dienstanfang; Generator `sp5_adapter.import_snapshot` baut die
Intervalle aus `SHIFT.STARTEND{idx}`, während `DURATION{idx}` die bezahlten
Minuten liefert. API `work_time_rules._collect_day_data/_check_employee`
summiert dagegen `shift_hours_on_day`/DURATION auf dem Quelldatum; OSP5
`WorkTimeRules.tsx` zeigt diese API-Prüfung. Sie ist deshalb kein unabhängiger
Nachweis für die realminutenbasierte Generator-Grenze. Die genauen Eingaben
und das Ergebnis des gemeldeten 600-Sekunden-Laufs fehlen weiterhin; dieser
Grenzfehler allein erklärt noch nicht den konkreten Nutzerplan.

## Anschlussbefund: 36h-Kalenderwochenruhe im Dienstüberhang

Die gezielte Folgeprüfung wies denselben zu engen Prüfbereich auch bei
`weekly_rest_frame=calendar_week` nach: `validator.weekly_windows` erzeugte
nur Kalenderwochen der Planungsperiode, `solver.solve` ebenso nur deren
Wochenruhe-Zeugen. Ein sonntags beginnender Dienst konnte daher die einzige
ausreichende Ruhe der nächsten Woche verkürzen, ohne beanstandet zu werden.

Rein synthetische Reproduktion mit den ausdrücklich beauftragten 11h/36h:
Sonntag 23:00–Montag 08:00, fixe Folgedienste Dienstag 16:00–24:00,
Donnerstag 08:00–16:00, Samstag 00:00–08:00 und Sonntag 16:00–24:00.
Ohne neuen Dienst sind am Wochenanfang 40h frei, mit ihm bleibt als längste
Pause nur 32h. Alle täglichen Abstände erfüllen weiterhin 11h. Dennoch
lieferten Voll- und Teilplanung vor dieser Korrektur fünf Einteilungen mit
`OPTIMAL`, `valid=true` und `complete=true`.

Die Kalenderwochenprüfung umfasst jetzt zusätzlich die tatsächlich durch
gewählte In-Perioden-Dienste belegten Überhangwochen. Im Solver aktivieren
nur die entsprechenden Auswahlvariablen die zusätzliche Wochenbedingung;
im unabhängigen Validator stammen die Wochen aus gewählten Diensten. Es
wird keine Freigabe geändert und keine Pflicht erzeugt, einen ansonsten
nicht betroffenen zukünftigen Kontext neu zu planen. Ein fehlender
vollständiger Wochenkontext bleibt eine Unvollständigkeitsdiagnose.

`tests/test_spill_rest.py` enthält 17 Regressionen: Voll-/Teilplanung,
exakt 35/36/37h freie Zeit, fixe Folgezeiten, nicht gewählter Überhang,
Profilzuordnung/-gültigkeit, beide Wiener Zeitumstellungssonntage und
explizite additive Ruhe. Der Default bleibt **36h einschließlich täglicher
Ruhe**, nicht 47h. Die beiden rollierenden Bezugsrahmen erkannten genau
diese Reproduktion bereits vorher; ihre Algorithmen wurden hier nicht
verändert. Daraus folgt keine vollständige Abnahme beliebig langer
Überhänge bei rollierenden Regeln.

### Gegenprobe mit dem unveränderten Release 0.9.29

Die drei oben beschriebenen Gegenbeispiele (Tagesmaximum, Wochenmaximum,
Kalenderwochenruhe) wurden zusätzlich mit den aus Tag `v0.9.29`, Commit
`714b9f7284364263ae1be03e3a21a9a552f25525`, unverändert exportierten
Python-Modulen ausgeführt. Alle sechs Voll-/Teilprüfungen lieferten dort
`OPTIMAL`, `valid=true`, `complete=true`; die Stundenfälle jeweils eine,
der Wochenruhefall fünf Einteilungen. Damit sind die Codefehler auch in
der gemeldeten Version reproduziert, weiterhin **nicht** im unbekannten
Original-Nutzerjob.

Die erweiterte Kalenderprüfung besitzt außerdem eine technische
Datumsbereichsvorprüfung: Ein außergewöhnlich langer Überhang am Ende des
darstellbaren Jahresbereichs darf keine Kalenderwoche jenseits Jahr 9999
berechnen. Ein synthetischer Gegenfall löste zunächst `OverflowError` aus.
`domain.input_diagnostics` meldet dafür jetzt `date_range`, bevor Solver oder
Validator Kalenderarithmetik ausführen. Fünf Regressionen in
`tests/test_input_boundaries.py` prüfen Wochenhöchstzeit und Kalenderwochenruhe
in Voll-/Teilplanung sowie einen weiterhin zulässigen Fall ohne Wochenregel.
Diese technische Grenze ist keine fachliche Dienstlängen- oder Wochenregel.
