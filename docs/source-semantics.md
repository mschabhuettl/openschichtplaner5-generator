# Belegte Quellsemantik für Import und Planung

Lesestand der drei unveränderten Checkouts am 11.09.2026:
Library `0dac4438c0be02c1ad612f54d4aba75a3e4d6335`, API
`d578f212d635b672ab277d7d29a37387145506f5`, OSP5
`addf5c2d1e40b4f266bacf1cd41f40ef70edbeb8`.
Dies ist eine eingegrenzte Datenflussanalyse, keine vollständige fachliche
Abnahme aller Originaltabellen. Keine realen Datensätze sind enthalten.

## Aktueller Korrekturstand gegenüber 0.9.29

Veröffentlichter konsolidierter Runtime-Stand: `bbcd2e2` (0.9.31, 11.09.2026).
Die nachfolgenden
Detailabschnitte dokumentieren auch **historische** Fehlerzustände; offene
Formulierungen dort sind nicht automatisch offene Fehler im aktuellen Code.
Diese Übersicht ist keine Release- oder Echtdatenfreigabe.

| Fehler oder Beobachtung | Aktueller Zustand und Codepfad | Synthetischer Nachweis |
| --- | --- | --- |
| Eingetragenes Wochenmaximum verliert durch Sammelzuordnung seine Wirkung | **Behoben** (`fbe2c1a`): `ProfileGroups.apply` erhält bereits konfigurierte Profilzuordnungen, ohne sie zu bestätigen. Bereits früher verlorene Zuordnungen werden nicht rekonstruiert. | `tests/browser/profile-groups.cjs`; Formular/Speichern/Neuladen in `tests/browser/check.cjs` |
| Dienst läuft über das Periodenende: Tages-/Wochenzeit und folgende Kalenderwochenruhe ungeprüft | **Behoben** (`4d3d645`, `6ca9271`, `3a29b25`): `solver.solve` und `validator.validate` prüfen ausgewählten Überhang mit gültigen zugeordneten Profilen; reale lokale Tages-/ISO-Wochenteile statt bezahlter Minuten. | `tests/test_partial_limits.py:test_hard_limits_cover_spill_after_period_end`; `tests/test_spill_rest.py` einschließlich 36h-Grenze, DST und Profilgültigkeit |
| Historische Randzeit benötigt künstlichen Bedarf und damalige Freigabe | **Behoben für importierte personenbezogene Randarbeit** (`47ebff2`, `0580aa9`): `import_snapshot` → `Snapshot.boundary_work` → Solver/Validator; keine Besetzung und kein Periodensoll aus Randzeit. Explizite alte Fixierungen behalten ihren strengeren Einteilungsvertrag. | `tests/test_boundary_work.py`; `tests/test_hierarchy.py:test_imported_boundary_counts_real_weekly_time_without_historical_approval` |
| Normaldienst und tagbezogener Sonderersatz doppelt gezählt | **Behoben** (`dd8c7b3`, `d2748ab`): `import_snapshot` normalisiert Ist-Randarbeit und Ist-Referenzen gemäß Library-Personentagsersetzung. Sollreferenzen sowie echte Zusatzdienste werden nicht pauschal gelöscht. Ungeklärte Ersatzzeiten bleiben Blocker. | `tests/test_api_adapter.py:test_special_replacement_boundary_matches_library_person_day`, `test_in_period_replacement_reference_respects_selected_plan`, `test_in_period_unresolved_special_never_becomes_free_time` |
| Teilplan oder Zeitbudget lockert harte Fixierung/Wochengrenze | **In den geprüften Fällen nicht bestätigt**: Solver-Fixierung und unabhängige Validierung bleiben erhalten. FEASIBLE ist kein Optimalitätsbeweis; UNKNOWN ohne Incumbent liefert keinen gültigen Plan. | `test_replacement_fixed_import_enforces_hard_limits_through_solver` und `test_imported_fixed_replacement_timeout_preserves_only_valid_incumbent` in `tests/test_api_adapter.py`; kontrollierte Statuszweige, **kein** 600s-Lasttest |
| Nicht alle geeigneten Personen eingeplant | **Kein pauschaler Regelverstoß**: `solver.solve` diagnostiziert individuelle Kandidaten/Ausschlüsse. Lineare Sollabweichung kann bei verschiedenen Verteilungen gleich sein; das weiche Blockziel kann Arbeit konzentrieren. Keine erfundene Pflicht zur Einteilung jeder Person. | `tests/test_partial_limits.py:test_linear_hours_target_can_tie_while_block_goal_concentrates_work` und Ausschlussdiagnosen derselben Datei |
| 24h-Dienst trotz 11h/36h-Ruhe | **Nicht allein daraus verboten**: tägliche Höchstzeit gilt für aufsummierte reale Zeit je Kalendertag, nicht automatisch für die Länge eines einzelnen Dienstes. Tatsächlich zugeordnete Grenzen und angrenzende Ruhe sind entscheidend. | `tests/test_partial_limits.py:test_24_hour_duties_are_not_forbidden_by_11_36_rest_alone`, `test_daily_limit_is_not_a_single_duty_length_limit` |
| Sollbuchungen / DADEM-Teamfilter / optionale Vergleichsblocker | **Behoben** (`f945180`, `889909b`, `e02a05a`): `_nominal_bookings` normalisiert signierte Typ-1-Buchungen; `import_snapshot` respektiert native DADEM-Teamfelder und trennt nicht fixierte Vergleichsdiagnosen von Pflichtdaten. Keine Umdeutung von Sollstunden zum Wochenmaximum. | `tests/test_nominal_bookings.py`, DADEM-Scope in `tests/test_sp5_adapter.py`, `tests/test_reference_blockers.py` |
| Ungültiger RESTR-Wochentag wird bei zugehörigem erzeugtem Dienst verworfen | **Im Arbeitszweig behoben** (`49db058`, nicht veröffentlicht): `import_snapshot` blockiert ungültige zugehörige Wochentage/Stufen und zählt verworfene Quellsätze. `outside_shift_scope` bleibt eine Sammelkategorie, kein Nachweis fehlenden Bedarfs oder ungültiger Quelle. | `tests/test_api_adapter.py:test_invalid_imported_restriction_blocks_otherwise_valid_planning`, `test_http_restriction_shift_scope_does_not_identify_root_cause` |

### Noch offen: Originalreproduktion und fachliche Abnahme

- Der exakte gespeicherte Projekt-/Jobeingang und das Ergebnis des gemeldeten
  0.9.29-Laufs mit 600 Sekunden liegen für diese Analyse weiterhin nicht vor.
  Die gefundenen synthetischen Fehlerpfade beweisen nicht dessen Ursache.
- Positive persönliche Freigaben, tatsächlich wirksame Höchstgrenzen und
  bestätigter Randkontext dürfen nicht aus Historie oder Sollstunden geraten
  werden. Der Nutzer hat 11h tägliche und 36h wöchentliche Ruhe vorgegeben,
  aber kein konkretes hartes Wochenmaximum.
- Mehrdeutige Team-/Arbeitsplatzzuordnung echter Referenzen bleibt sichtbar:
  Quellmitgliedschaft ist kein eindeutiger Einsatzteamnachweis. Die Korrekturen
  erfinden keine Bedarfe, Freigaben oder Zuordnungen.
- Die private Abnahme des veröffentlichten Stands 0.9.31 (`bbcd2e2`, ohne
  Runtime-Overlay) am 11.09.2026, 13:43–13:47 UTC, belegt
  Import/Speicherung, nicht erfolgreiche Neuplanung: beide Plansichten bleiben
  wegen fehlender Einrichtung MODEL_INVALID, ohne generierte Einteilungen.
  Auch der zusätzliche Versuch mit ausdrücklich gesetzter 11h-/36h-Ruhe
  ersetzt fehlende Freigaben und Profileinrichtung nicht. Kein unabhängig gültiger realer
  Vergleichsplan liegt vor.

### Geschlossener Korrekturumfang und verbleibende Gates

Die drei zusammengehörigen Sicherheitsbereiche sind Profilzuordnung,
Zeitgrenzen einschließlich Randarbeit sowie Ist-Sonderersetzung. Die obigen
Tests decken ihre Einzelverträge und den HTTP-Import bis Teilplan/Validator ab.
Die vollständige [CI für `9581f28`](https://github.com/mschabhuettl/openschichtplaner5-generator/actions/runs/34603999074)
ist erfolgreich abgeschlossen. Die vollständige lokale Suite am selben
Runtime-Stand besteht mit 753 Tests (zwei bekannte Deprecation-Warnungen).
Ein lokaler Python-Test ersetzt Paket-,
Browser- und Container-Gates nicht. Seit 0.9.30 sind zusätzlich datierte
Istbuchungs-/Abwesenheitsnachweise (ohne automatische Anrechnung), vollständige
Tages-/Wochendiagnosen und bestätigte Profilabdeckung für tatsächlichen
Dienstüberhang umgesetzt; die Detailabschnitte unten belegen diese Änderungen.

Vor einer Freigabe dieses gesamten Umfangs: abschließende CI des ausgewählten
Commits prüfen, erforderliche veröffentlichte Docker-Abnahme privat und lesend
nachweisen und verbleibende echte Einrichtungsblocker ausdrücklich erhalten.
Ein neuer Tag ist weder Originalreproduktion noch Migration bereits verlorener
Projektangaben. Die nächste fachliche Gegenprüfung benötigt den exakten
Originaleingang, sobald er privat verfügbar ist; bis dahin bleiben weitere
unabhängige Gegenproben möglich. Keine neue UI-/Feature-Serie daraus ableiten.

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

1. **Historischer, inzwischen behobener Fehler: DADEM-Teamfilter** (`889909b`). Die Library liefert rohe
   `GROUPID`-Felder, Generator `sp5_adapter.py:196–200` prüft `group_id`.
   Dadurch wird jede solche Zeile als `None` behandelt und zugelassen.
   Synthetische Quelle: Auswahl Team 1, einzige DADEM-Zeile `GROUPID=99`;
   eine fremde Zeile bleibt in `unresolved_native.daily_requirements`.
   Korrektur: Quellfeld korrekt lesen, ausgewählte und globale/ungeklärte
   Werte erhalten, fremde Teams ausschließen; kein DADEM-Soll erfinden.
   Der damalige Test `test_special_and_zero_preserved_not_summed` deckte nur
   das Erhalten einer ausgewählten Zeile ab. Die inzwischen ergänzten
   DADEM-Scope-Gegenproben in `tests/test_sp5_adapter.py` prüfen auch fremde,
   ausgewählte und ungeklärte Teams.
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
  `test_dst_weekly_cap_includes_context_in_elapsed_minutes` prüft zusätzlich
  Frühjahr (180 Minuten) und Herbst (300 Minuten) mit jeweils 120 Minuten
  Samstags-Randarbeit: sowohl alte Fixierung als auch `boundary_work`, Voll-
  und Teilmodus, exakte Wochengrenze und eine Minute darunter. Bezahlung
  (eine Minute je Dienst) und hohes Periodensoll ändern diese Grenze nicht.
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

## Ursprünglicher Fehler: Randzeit an Besetzungszulässigkeit gekoppelt

**Historischer Analysebefund vor der unten dokumentierten Randarbeitsintegration.**
Alte explizite Fixierungen behalten diesen Vertrag; neue Importe nicht.

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

**Damals priorisierte Korrekturrichtung (inzwischen unten umgesetzt):** bestätigte
personenbezogene Randintervalle getrennt von zu besetzenden Bedarfen abbilden.
Sie müssen weiterhin zwingend in Überlappung, tägliche/wöchentliche reale
Minuten, Ruhe und Serien eingehen. Unbekannte Nachtart darf nicht verschwinden;
Quellvollständigkeit und tatsächliche Zeitabweichungen bleiben eigene
Bestätigungsfragen. Historie darf keine zukünftige Freigabe erzeugen. Das
pauschale Löschen von `unresolved`, Umbenennen von `unconfirmed` oder Umgehen
von `eligibility` für beliebige Fixierungen ist kein geeigneter Fix.

### Sicherheitsvertrag für die Entkopplung der Randarbeit

`tests/test_boundary_time_contract.py` ergänzt 22 synthetische Gegenproben
in Voll- und Teilplanung. Ausgangspunkt sind ausschließlich ausdrücklich
freigegebene Testdienste, keine bereinigten Realdatenimporte. Jede Gegenprobe
prüft zuerst den unabhängigen Validator und dann den Solver. Anschließend
ersetzt sie **nur im Test** fixe Randarbeit durch dieselben Intervalle als
`Employee.unavailable`. Diese vermeintlich einfache Entkopplung verliert
nachweislich wesentliche Regeln:

| Regel | Synthetischer Konflikt mit neuer Arbeit | Ergebnis nach verlustbehaftetem Abwesenheitsersatz |
| --- | --- | --- |
| tägliche Ruhe | Randdienst endet Montag 04:00, neuer Dienst beginnt 08:00; 11h konfiguriert | neuer Dienst fälschlich möglich |
| zusätzliche Nachtruhe | Nacht endet 04:00, neuer Tagdienst beginnt 16:00; ausdrücklich synthetische 16h Nachtruhe | neuer Dienst fälschlich möglich |
| Tageshöchstzeit | 8h Randüberhang am Montag plus 8h neuer Dienst; 12h konfiguriert | nur 8h gezählt |
| Wochenhöchstzeit | Montag 8h Randarbeit plus Mittwoch 8h neuer Dienst; 12h konfiguriert | nur 8h gezählt |
| Periodenhöchstzeit | 8h Randüberhang innerhalb der Ein-Tages-Periode plus 8h neuer Dienst; 12h konfiguriert | nur 8h gezählt |
| Arbeits-/Nachtserie | zwei fixe Vor-Tage/-Nächte plus neuer dritter Tag; Maximum 2 konfiguriert | Serie verschwindet |
| Kalenderwochenruhe | neuer Sonntagsüberhang verkürzt mit fixen Folgezeiten die längste Pause von 40h auf 32h; 36h konfiguriert | Folgearbeit zählt nicht mehr als Arbeit |
| verschachtelter geteilter Dienst | neuer Dienst liegt zwischen zwei Segmenten derselben Randarbeit | Abwesenheit schützt nur Segmente, nicht die Unvereinbarkeit verschachtelter Dienste |

Alle neun Gegenfälle ergeben mit echter Randarbeit eine gezielte harte
Diagnose; Vollplanung ist `INFEASIBLE`, Teilplanung lässt nur den neuen Bedarf
offen. Nach dem absichtlich verlustbehafteten Testumbau wird der neue Dienst
jeweils `OPTIMAL/complete` akzeptiert. Die Randarbeit allein ist in allen
Fällen zulässig. Es handelt sich deshalb nicht um eine nachträgliche
Sanktionierung unbeteiligter Historie. Zwei Kontrolltests zeigen, dass der
Abwesenheitsersatz direkte Überschneidungen tatsächlich verhindert – dieser
einzelne erfolgreiche Test wäre somit kein hinreichender Sicherheitsnachweis.

Zwei weitere Kontrollen sichern die Zeitsorten: 8h fixe Randarbeit mit 6000
bezahlten Minuten und 8h neue Arbeit mit 60 bezahlten Minuten passen exakt
unter ein synthetisches 16h-Wochenmaximum. Das neue Periodensoll von 60 Minuten
ist trotzdem exakt erfüllt; Randbezahlung zählt nicht erneut ins Periodensoll.
Eine Absenkung des Wochenmaximums um eine reale Minute führt zur Ablehnung.
Die zusätzlichen Höchstwerte/Nachtregeln sind **nur Testkonfigurationen**,
keine neuen Defaults oder aus dem Nutzerauftrag abgeleiteten Grenzen.

**Konkrete Integrationsgrenzen des nächsten Modellschritts:**

1. Personenbezogene Arbeitsintervalle benötigen eine eigene Eingabekollektion
   mit stabiler Quellidentität, Person, Segmenten und belegter Nachtart. Keine
   Pflichtreferenz auf künstlichen Arbeitsplatz, Einsatzteam oder Bedarf.
   Zeitabweichungen, unbekannte Nachtart und Quellvollständigkeit bleiben
   explizite offene Fragen; die neue Kollektion ist keine pauschale Freigabe.
2. Solver `by_employee`, Konfliktgraph, `daily/work/night` und Wochenruhezeugen
   müssen diese Zeiten als unveränderliche Arbeit berücksichtigen. Die neue
   Kollektion darf dagegen nicht in `xs`, Bedarfsbesetzung, Kandidatenzählung,
   Mentorplätze oder neu erzeugte Ergebnis-Einteilungen geraten.
3. Validator `_validate` benötigt dieselben Randzeiten direkt aus dem Snapshot,
   unabhängig vom Ergebnis. Sonst könnte das Weglassen aus dem Ergebnis harte
   Grenzen umgehen. Zeitprüfungen bleiben von `eligibility` der **neuen**
   Einteilungen getrennt; alte fixe Bedarfszuweisungen dürfen nicht über ein
   frei setzbares `source`-Kennzeichen von Freigaben befreit werden.
4. Die personenbezogenen `PreparedValidator`-Kopien der Warmstartheuristik
   (`solver.local_validator`) müssen die neue Kollektion mitfiltern. Beide
   Ergebnispfade müssen weiterhin ausschließlich Periodendienste als neue
   bezahlte Minuten ausweisen. Snapshot-Hash, JSON-Speicherung und Workerpfad
   müssen die Randdaten unverändert erhalten.
5. Der Import darf nur eindeutig bekannte normale Randzeiten übernehmen,
   niemals ungeklärte Sonderzeitabweichungen ersetzen oder dieselbe Quelle
   gleichzeitig als alte fixe Einteilung und neue Randarbeit zählen.

Diese Gegenproben und Integrationsgrenzen waren zunächst nur Prüfumfang,
**noch keine eingeführte neue Randdatenkollektion**. Die anschließende Umsetzung
ist unten dokumentiert; der Original-600s-Lauf bleibt nicht reproduziert. Ein neuer Datentyp allein ohne Solver, unabhängigen
Validator, Import und Persistenz würde diese Anforderungen nicht erfüllen.

### Ursprünglicher durchgängiger Importbeleg

**Historischer Fehlernachweis; der Test prüft inzwischen die Korrektur (siehe unten).**

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

### Umgesetzt: unabhängiger Randarbeitsvertrag im Planungskern

`models.BoundaryWork` und `Snapshot.boundary_work` bilden unveränderliche,
personenbezogene Dienste ab: ID, Person, Segmente, Tag-/Nachtart und Herkunft.
Es gibt keine Pflichtreferenz auf Bedarf, Arbeitsplatz oder Team und keine
bezahlten Minuten. Der Dienstbeginn muss außerhalb der Planungsperiode liegen;
Überhänge in die Periode bleiben echte Arbeit. `domain.input_diagnostics`
prüft Referenzen, eindeutige IDs, Minuten/Zeitzonen/Segmente und Kontextgrenzen.
`kind=unknown` blockiert ausdrücklich. Eine identische bereits fixierte
Einteilung darf nicht zusätzlich als Randarbeit gezählt werden. Alte explizite
Fixierungen behalten ihre bisherigen Freigabe- und Zuordnungsprüfungen.

`solver.solve` führt Randarbeit als konstante Eins in den personenbezogenen
Arbeitszeitbedingungen, nicht in den Besetzungsvariablen `xs`. Sie zählt in
Konflikt-, Stunden-, Arbeits-/Nachtserien- und Wochenruheprüfungen einschließlich
der Nachtblock-Zwischendienste. Sie liefert keine Bedarfsdeckung, Betreuung,
Kandidatenchance oder Ergebnis-Einteilung. Der lokale Warmstart-Validator
filtert auch die neue Kollektion nach Person. `validator._validate` liest
Randarbeit unabhängig direkt aus dem Snapshot; ein Ergebnis kann sie nicht
weglassen. Periodensoll und Ergebniskennzahlen bleiben auf neue Einteilungen
bezogen. Vorherige Snapshot-Hashes bleiben bei leerer Kollektion identisch;
nichtleere Randarbeit ist vollständig hashgebunden und persistent.

`tests/test_boundary_work.py` enthält 40 synthetische Regressionen: die zehn
harten Konfliktarten aus dem Sicherheitsvertrag in Voll-/Teilplanung,
Soll-versus-Echtzeit, neue Freigaben ohne erfundene historische Freigaben,
ungültige Eingaben/Doppelerfassung, Personenisolation, Hash-/JSON-Roundtrip,
HTTP/Persistenz/separater Worker, beide rollierenden Ruhebezüge und Nachtblock
mit bzw. ohne echten verbindenden Randdienst. Keine realen Eingaben verwendet.

### Umgesetzt: Randarbeitsimport und ausdrückliche Dienstart-Einrichtung

`sp5_adapter.import_snapshot` übernimmt normale Dienste außerhalb der Periode
jetzt in `boundary_work`. Der bestehende Ist-Kontext bleibt von der gewählten
Ist-/Soll-Referenzsicht innerhalb der Periode getrennt. Person und reale
`SHIFT.STARTEND0..7`-Segmente reichen für die Arbeitszeitprüfung; Team,
Arbeitsplatz, SHDEM-ID und historische Dienstfreigabe werden nicht erfunden.
Es entstehen keine `sp5:existing`-Bedarfe, Positionen oder fixen Assignments.
Nominale Dienste und identische nominale Sonderersetzungen werden weiterhin
nur einmal gezählt; unterschiedliche Arbeitsplatz-/Gruppeneinträge bleiben
getrennte Quelldatensätze und werden nicht heimlich zusammengeführt.

Quellenbeleg: `sp5lib.database.SP5Database.get_schedule` bildet MASHI auf
Person, Datum, Dienst und Arbeitsplatz ab, nicht auf einen konkreten Bedarf
oder eine Einsatzgruppe. `sp5api.routers.schedule.get_schedule` reicht den
Gruppenfilter an diese personenbezogene Sicht weiter. Die OSP5-Personengruppierung
liefert ebenfalls keinen zusätzlichen Einsatzteam-Beleg. Die bisherige
Zuordnungsanforderung war für reine Randarbeitszeit daher sachlich unnötig;
für Bedarfsdeckung **innerhalb** der Periode bleibt sie unverändert notwendig.

`metadata.provenance[work.id]` hält Dienstidentität, Anzeigename, Quellgruppe,
Arbeitsplatz und verwendeten STARTEND-Slot nachvollziehbar fest. `kind=unknown`
bleibt ein harter `boundary_kind`-Blocker. `static/service-groups.js` bietet
Randarbeitsmuster ohne bezahlte Stunden separat zur ausdrücklichen Tag-/Nacht-
Bestätigung an, auch wenn der Dienst in der Planungsperiode keinen Bedarf hat.
Vorschau verändert nichts, bereits bestätigte Arten bleiben bestehen.
`setup-assistant.js` übernimmt Randarten nur bei ausdrücklich gewählter
Wiederverwendung derselben Quelle und eindeutig bestätigtem bisherigen Muster;
widersprüchliche Arten werden nicht entschieden. Keine Freigaben oder
Regelprofile werden dadurch bestätigt.

Nachweise: `test_sp5_adapter` sichert Person/Zeit ohne künstliche Bedarfe,
Quellidentität und nominale Sonderersetzungen; `test_api_adapter` prüft alle
acht Zeit-Slots über die HTTP-Fassade und die getrennte Ist-/Soll-Sicht.
`test_hierarchy.test_single_direct_membership_does_not_prove_context_assignment_team`
belegt den Import bei einer Direktgruppe und mehreren effektiven Vorfahrengruppen:
ursprünglich MODEL_INVALID, nach expliziter synthetischer Einrichtung planbar,
ohne rückwirkende Freigabe. Vier zusätzliche Voll-/Teil-Gegenproben in
`test_imported_boundary_counts_real_weekly_time_without_historical_approval`
sichern die scharfe 480/479-Minuten-Grenze bei jeweils 240 realen, aber nur
60 bezahlten Minuten. Solver und unabhängiger Validator stimmen überein.
Browserprüfungen sichern Vorschau/Bestätigung einschließlich Randarbeit,
Desktop/Mobil, unveränderte übrige Eingaben und die Wiederverwendungsregeln.

Unverändert offen: abweichende Sonderdienste, Quellvollständigkeit,
wirksame bestätigte Profile und tatsächliche neue persönliche Freigaben.
Bestehende gespeicherte Projekte werden **nicht** automatisch migriert.
Der Original-600s-Job ist weiterhin nicht reproduziert.

### Sonderzeiten: vorhandener Live-Datenpfad statt ORM-Fallback

Nachprüfung 2026-09-11 nach `0580aa9`: Die Aussage, der Library-
Schedule-Export enthalte keine SPSHI-Zeiten, gilt für `get_schedule` allein,
**nicht für den vollständigen Generatorimport**. Der vorhandene ergänzende
Leseweg ist:

1. `5SPSHI.STARTEND/DURATION/TYPE/ID` → Library
   `Database.get_spshi_entries_for_day` (`sp5lib/database.py:2626`): direktes
   `_read("SPSHI")`, Datum und optionale Gruppenmitgliedschaft als Filter.
2. API `schedule.get_einsatzplan` (`sp5api/routers/schedule.py:1480`):
   `GET /api/einsatzplan`, delegiert an dieselbe Library-Methode. Kein
   ORM-Spiegel, keine Synchronisierung und kein Schreibaufruf erforderlich.
3. OSP5 `frontend/src/api/client.ts:1630` deklariert `getEinsatzplan`
   über `/api/v1/einsatzplan`. Im untersuchten Frontend ist kein Aufrufer
   dieser Clientfunktion gefunden; eine tatsächliche Anzeige dieser Daten
   ist damit **nicht** belegt.
4. Generator `api_adapter._Database.get_spshi_entries_for_day` → `_scope_schedule`:
   Details werden pro Datum/ausgewählter Gruppe gelesen. Übernahme nur bei
   genau einem Treffer für Person, Dienst, Arbeitsplatz und SPSHI-Typ.
5. `import_snapshot`: Nur Typ 0 mit exakt gleichen realen Zeitsegmenten
   **und** gleichen bezahlten Minuten darf als nominaler Dienst behandelt
   werden. Fehlende Details, Mehrdeutigkeit, abweichende Zeiten oder bezahlte
   Dauer sowie Typ 1 bleiben Sonderdienst-/Quellklärungsblocker. Historische
   Einteilungen bestätigen dabei keine persönliche Freigabe.

Damit ist „fehlender API-Endpunkt“ keine belegte Ursache für die noch offenen
Sonderdienste. Die Mappinglücke ist die weiterhin fehlende eigenständige
Repräsentation abweichender Sonderdienste; nominale Ersatzzeiten wären keine
zulässige Reparatur. Insbesondere dürfen längere reale Zeiten bei identischer
bezahlter Dauer nicht verschwinden. Vor einer Erweiterung müssen Ersatz- versus
Zusatzsemantik und Typ-1-Abweichungen anhand der Library-Arbeitszeitberechnung
abgeglichen werden; weder Dienstzeiten noch Höchstgrenzen werden geraten.

Synthetischer HTTP-Nachweis:
`test_special_duty_details_use_live_read_only_endpoint_and_never_guess`
mit sechs Gegenproben (nominal, längere reale Zeit bei gleicher Bezahlung,
andere Bezahlung bei gleicher Zeit, fehlende Zeit, mehrere Detailtreffer,
Typ 1). Alle sichern ausschließlich GET, exakten Datum-/Gruppenfilter,
keinen ORM-Zugriff und unverändert fehlende persönliche Freigaben.

**Weiterer konkreter Semantikunterschied:** Die Library entscheidet Ersatz
nicht anhand von `SPSHI.TYPE`, sondern in `calculations._replaced_days`
(`calculations.py:436`) anhand einer gesetzten `SHIFTID`: Alle normalen
Dienste dieses Personentags werden in `get_work_hours` ausgenommen; die
Sonderzeile trägt ihre eigene `DURATION`. Ohne `SHIFTID` wird sie zusätzlich
gerechnet. Vorhandene Library-Tests `test_special_shift_replaces_duty` und
`test_pure_special_shift_adds` belegen 5 statt 8+5 bzw. 8+3 Stunden.
`daily_work_intervals` verwendet dieselbe Ersatzentscheidung, berücksichtigt
aber auch `NOEXTRA` für Zuschläge; diese Zuschlagsintervalle dürfen deshalb
nicht ungeprüft als vollständige Arbeitszeit für Ruhegrenzen wiederverwendet
werden.

Demgegenüber exportiert `Database.get_schedule` zunächst die manuellen
MASHI-Zeilen unverändert und unterdrückt mit `replaced_by_spshi` nur
Zykluszeilen; danach kommen die SPSHI-Zeilen hinzu. Ein API-Raster ist daher
keine bereits normalisierte Liste tatsächlich addierbarer Arbeitszeiten.
Der Generator kennt bislang nur die oben beschriebene nominal-identische
Sonderersetzung, keine vollständige tagbezogene Ersatzauflösung. Das ist
vor einer Freigabe abweichender Sonderzeiten zu korrigieren, insbesondere
bei abweichender Dienst-/Arbeitsplatzidentität. Dieser Quellcodebefund ist
noch **keine** Reproduktion der gemeldeten 24h-Dienste des Originaljobs.

### Synthetisch reproduziert: doppelte Randarbeit bei Sonderersatz

`tests/test_api_adapter.py::test_special_replacement_boundary_matches_library_person_day`
verfolgt den lesenden HTTP-Import über `/api/schedule` und `/api/einsatzplan`
bis `Snapshot.boundary_work` und vergleicht ihn mit `calculations.get_work_hours`.
Die künstliche Quelle enthält am Vortag einen vierstündigen Normaldienst und
einen nominal-identischen vierstündigen Sonderersatz mit gesetzter `SHIFTID`.
Nur in diesem Test sind reale Arbeitszeit und bezahlte Dauer bewusst gleich;
die Library-Stundensumme ist kein allgemeiner Ersatz für reale Zeitintervalle.

| Gegenprobe | Library | importierte Randarbeit | Status |
|---|---:|---:|---|
| gleiche Dienst- und Arbeitsplatz-ID | 4 h | 4 h | korrekt |
| anderer Arbeitsplatz | 4 h | 8 h | belegter Mappingfehler |
| andere Dienst-ID, gleiche nominale Zeiten | 4 h | 8 h | belegter Mappingfehler |

Alle drei Varianten laufen mit beiden Quellreihenfolgen. Die vier fehlerhaften
Fälle sind ausdrücklich `xfail(strict=True)` als **offener Sicherheitsvertrag**
markiert, nicht als bestandene Fehlerkorrektur. Mit `--runxfail` scheitern genau
diese vier an `480 == 240`. Die zwei identischen Kontrollen bestehen. Es werden
keine Freigaben bestätigt und keine Sonderzeit-Blocker entfernt. Bereits eine
nominal akzeptierte Sonderzeile reicht aus, um die Lücke sichtbar zu machen.

Ursache: `import_snapshot` konvertiert die passende Sonderzeile lokal zu
`kind="shift"`, verarbeitet den manuellen Normaldienst aber weiterhin.
Die anschließende Rand-Deduplizierung verwendet eine ID aus Person, Datum,
Dienst, Arbeitsplatz und Gruppe. Ein anderer Dienst oder Arbeitsplatz erzeugt
eine zweite `BoundaryWork`-Zeile, obwohl die Library tagbezogen ersetzt.
Dies belegt überzählige, hier auch überlappende Randarbeitsintervalle; es belegt
weder die Ursache des Originaljobs noch einen zulässigen 24h-Dienst.

`test_library_special_replacement_is_day_wide_and_not_type_selected` sichert
zusätzlich vier Quellgegenproben: zwei Normaldienste ergeben mit einer
dreistündigen Sonderzeile **3 h bei gesetzter SHIFTID**, aber **11 h ohne
SHIFTID**, jeweils für Typ 0 und 1. Der Arbeitsplatz ist dabei verschieden.
Damit ist eine Normalisierung nur nach gleicher Dienst-ID oder nur Typ 0
nachweislich unvollständig. Das autorisiert noch keine Interpretation aller
Typ-1-Zeitfelder als bestätigte Arbeitsintervalle.

**Priorisierte Korrektur, noch offen:**

1. Randarbeit nach Person und Datum aus der Ist-Quelle normalisieren und
   ersetzte Normalzeilen in der Herkunft nachvollziehbar halten. Echte
   Zusatzdienste ohne Dienst-ID nicht entfernen; ungeklärte Sonderzeiten
   weiterhin blockieren. Die vier `xfail`-Markierungen nach Behebung entfernen.
2. Ist-/Soll-Referenzen gesondert absichern: `_reference_schedule` mischt
   absichtlich Ist-Sonderkontext mit gewählten regulären Referenzen. Eine
   globale Zeilenlöschung vor dieser Auswahl könnte Soll-Vergleichsdienste
   unzulässig entfernen. Nicht aus der Randkorrektur automatisch ableiten.
3. Danach Wochen-/Tageslimit und Ruhezeit im vollständigen und partiellen
   Solver gegen den unabhängigen Validator prüfen; relevante Runtimekorrektur
   erneut privat gegen die API abnehmen. Die hier ergänzten Tests und dieser
   Befund ändern allein noch keinen Import und rechtfertigen kein Release.


### Korrektur der tagbezogenen Randersetzung

Der oben dokumentierte XFAIL-Stand ist historisch: `import_snapshot` bildet
jetzt vor der zeilenweisen Verarbeitung die ersetzten Personentage aus
Ist-Sonderzeilen mit gesetzter Dienst-ID. Nur außerhalb der Planungsperiode
werden normale Zeilen dieser Tage nicht zusätzlich als Randarbeit angelegt.
Die ursprüngliche Struktur bleibt in `metadata.context_schedule`;
akzeptierte nominale Ersatzarbeit enthält außerdem
`metadata.provenance[id].replaced_normal_rows` mit Dienst-/Arbeitsplatz-/
Gruppenherkunft der ersetzten Normalzeilen. Die Reihenfolge ist unerheblich.

Die sechs ursprünglichen HTTP-Gegenproben bestehen ohne XFAIL. Weitere sechs
Fälle in
`test_boundary_replacement_keeps_blockers_additions_and_selected_references`
sichern beide Referenzsichten, Zusatzdienste mit Dienst-ID 0, Typ 1 und
abweichende reale Sonderzeiten ab. Nicht darstellbare Ersatzzeiten bleiben
harte Sonderdienstblocker, auch wenn die ersetzten normalen Randzeiten nicht
mehr addiert werden. Fehlende Sonderzeiten werden dadurch nicht zu Freizeit
eines gültigen Plans. Persönliche Freigaben bleiben unbestätigt.

Die Normalisierung der Referenzdienste innerhalb der Planungsperiode bleibt
ein separater offener Prüfpunkt. Diese Korrektur ändert weder Soll-Referenzen
noch Bedarfe oder Arbeitszeitgrenzen und reproduziert weiterhin nicht den
fehlenden Originaljob 0.9.29 mit 600 Sekunden Budget.

Die Import-bis-Solver-Gegenprobe
`test_imported_boundary_counts_real_weekly_time_without_historical_approval`
prüft zusätzlich Voll- und Teilplanung mit anderem Ersatzarbeitsplatz:
vier reale Randstunden (eine bezahlte Stunde) plus vier reale Planstunden
sind bei ausdrücklich synthetisch konfiguriertem Wochenmaximum 480 Minuten
zulässig, bei 479 nicht. Solver und unabhängiger Validator stimmen überein;
die Randhistorie erfordert keine rückdatierte persönliche Freigabe.

### Reproduktion und Korrektur: Ersatz innerhalb der Planungsperiode

`test_in_period_replacement_reference_respects_selected_plan` liefert zwei
synthetische HTTP-Gegenproben für Ist (beide Zeilenreihenfolgen) und zwei
Soll-Verhaltenskontrollen, jeweils im Referenz- und Fixierungsmodus. Zwei nominale
Vierstundendienste mit verschiedenen Dienst-IDs haben jeweils eindeutigen
Bedarf. Ein SPSHI-Ersatz mit gesetzter Dienst-ID ersetzt laut
Library `calculations._replaced_days` / `get_work_hours` den normalen Dienst
des Personentags. Vor der Korrektur behielt der Generator innerhalb der Periode
beide Ist-Referenzen und erzeugte zwei Referenzzuweisungen statt einer.
Die ursprüngliche Gegenprobe ohne XFAIL-Ausnahme scheiterte zweimal genau
an den zwei statt einer Dienst-IDs; beide Soll-Kontrollen bestanden.

Quellpfad: `SP5Database.get_schedule` behält MASHI-Zeilen und ergänzt SPSHI;
nur expandierte CYASS-Zeilen werden dort mit `replaced_by_spshi` unterdrückt.
`sp5api/routers/schedule.py:get_schedule` reicht diese Zeilen mit `plan`
weiter. OSP5 `frontend/src/pages/Schedule.tsx` verarbeitet an mehreren
Stellen sowohl `shift` als auch `special_shift`; daraus folgt keine
Stunden-Normalisierung. Generator `_reference_schedule` liefert die Zeilen
an `import_snapshot`. Dessen tagbezogene Normalisierung war bisher auf
Randarbeit beschränkt; nominalidentische Sonderzeiten werden anschließend
als regulärer Dienst dem Bedarf zugeordnet. Unterschiedliche Dienst-IDs
verhindern die spätere Assignment-Deduplizierung.

Wichtige Abgrenzung: Library/API liefern Sonderdienste ausdrücklich in
**beiden** Plansichten; `SPSHI.TYPE` ist kein Soll/Ist-Schalter. Deshalb ist
das Auftauchen des Sonderdiensts im Soll-Vergleich allein kein belegter
Fehler. Die zwei Soll-Kontrollen erhalten dessen Kontext und den regulären
Soll-Dienst. Eine Löschung der Soll-Zielvorgabe aus einer Ist-Ersatzregel
wäre nicht begründet. Rohkontext, zwei echte Bedarfe, unbestätigte Profile
und fehlende persönliche Freigaben bleiben in allen vier Fällen erhalten.

Die Korrektur erweitert die vorhandene Normalisierung auf Ist-Referenzen;
akzeptierte Ersatzreferenzen tragen `replaced_normal_rows`. Rohkontext und
Soll-Auswahl bleiben erhalten. Die acht HTTP-Fälle bestehen ohne XFAIL.
Die bestehende Gegenprobe
`test_reference_selection_never_switches_context_absences_or_special_duties`
prüft zudem: Ein ungeklärter Typ-1-Ersatz bleibt ein harter Sonderblocker,
der ersetzte normale Ist-Dienst wird auch im Fixierungsmodus nicht als
Fallback übernommen. Reguläre Soll-Zielvorgaben bleiben unverändert.
Weitere acht HTTP-Fälle in
`test_in_period_unresolved_special_never_becomes_free_time` sichern
abweichende reale Zeiten bei unverändert bezahlten Stunden und echte
Zusatzdienste ohne Dienst-ID in beiden Sichten/Modi ab. Sonderblocker
bleiben erhalten; Zusatzdienste löschen den Normaldienst nicht.
Dies beweist nicht die Ursache des weiterhin fehlenden Original-600s-Jobs.

### Fixierter Ersatzdienst bis Solver und unabhängige Validierung

`test_replacement_fixed_import_enforces_hard_limits_through_solver` prüft acht
synthetische HTTP-Import-bis-Solver-Fälle: Ist/Soll × Voll-/Teilplanung ×
Wochenmaximum 239/240 Minuten. Vor der ausdrücklich synthetischen Einrichtung
bleiben alle Fälle `MODEL_INVALID`: Referenzen liefern weder persönliche
Freigaben noch eine Profilbestätigung. Auch die Dienstklassifikation wird in
der Testeinrichtung ausdrücklich als Tagdienst gesetzt; Quellzeiten allein
sind keine bestätigte Klassifikation.

Bei 240 Minuten erhält der Ist-Teilplan genau den korrigierten, fixierten
Vierstunden-Ersatzdienst und meldet eine offene Bedarfsposition. Er ist unabhängig
validiert, aber nicht vollständig. Bei 239 Minuten bleibt auch die Teilplanung
`INFEASIBLE`: Die Fixierung darf weder entfallen noch die harte Wochenobergrenze
überschreiten. Vollplanung bleibt wegen der zwei überlappenden Bedarfe unmöglich.
Die Soll-Kontrolle erhält beide fixierten Quellreferenzen und bleibt wegen der
Konflikte unplanbar; sie wird nicht durch Löschen einer Soll-Zielvorgabe passend
gemacht. Der unabhängige Validator bestätigt die jeweiligen Wochenverstöße.
Die bereits importierten 11h/36h-Ruhedefaults bleiben unverändert aktiv.

Dies ist eine Absicherung der vorhandenen Korrektur, kein neuer Runtime-Fix und
kein Nachweis für den fehlenden Original-600s-Job. Insbesondere ist das hier
gewählte Vierstunden-Wochenmaximum ausschließlich ein synthetischer Grenzwert,
keine aus Sollstunden abgeleitete oder für den Nutzer eingeführte Regel.

Die drei HTTP-Import-Abbruchgegenproben
`test_imported_fixed_replacement_timeout_preserves_only_valid_incumbent`
verwenden dieselbe synthetische Einrichtung und echte CP-SAT-Lösungen mit
gezielt kontrolliertem Rückgabestatus (keinen 600-Sekunden-Wartetest):
`FEASIBLE` in der Bedarfsphase und `UNKNOWN` in der anschließenden
Qualitätsphase erhalten genau die fixierte Ersatzschicht und eine Vakanz.
Beide Ergebnisse sind unabhängig gültig, unvollständig und ohne
Optimalitätsbehauptung. Bei `UNKNOWN` bereits vor dem ersten Incumbent
werden keine importierten Fixierungen als vermeintlich berechneter Plan
zurückgegeben; Ergebnisvalidität bleibt falsch und die Personendiagnose
lautet `no_valid_plan`. Eine unabhängige Gegenprüfung derselben gefundenen
Schicht mit 239 statt 240 realen Wochenminuten meldet `weekly_limit`.
Dies prüft die Statusbehandlung und Importintegration, nicht das reale
Laufzeitverhalten oder den weiterhin fehlenden Originaljob.

### Istkonten und Neuplanung: keine pauschale Gutschrift aus Iststunden

Die anschließende Quellanalyse verfolgt den noch offenen Stundenbestandteil
über dieselben Library/API/OSP5-Checkouts wie oben:

| Stufe | Beleg | Bedeutung |
| --- | --- | --- |
| Originalbuchung | `5BOOK`: `EMPLOYEEID`, `DATE`, `TYPE`, `VALUE`; Library `database.get_bookings` | Signierte Stundenbuchung, kein Dienstintervall. |
| Library | `calculations.booking_sum`, `get_actual_hours` | TYPE 0 im inklusiven Datumsbereich plus Arbeitsstunden plus bezahlte Abwesenheitsanrechnung minus DEDUCTACT-Anrechnung. Buchungen wirken vor Beschäftigungsbegrenzung. |
| Konto/Summe | `database.calculate_time_balance`, `_time_balance_from_inputs`, `calculate_annual_statement` | Monatliches Ist minus Soll; TYPE 2 und 5OVER gehören zum gesonderten Überstundenkonto. Jahresübertrag ist bereits eine TYPE-0-Buchung; Jahresabschluss zieht `carry_in` für seinen Nettoausweis wieder ab. |
| API | `sp5api/routers/reports.py:get_bookings`, `get_zeitkonto_detail`, `get_statistics` | GET `/api/bookings` liefert Einzelbuchungen; Zeitkonto-Detail liefert die Library-Jahresauswertung. Statistik kann einen eigenen Datumsbereich haben. Diese Sichten sind keine austauschbaren Anfangssalden. |
| OSP5 | `frontend/src/pages/Zeitkonto.tsx` | Lädt `getZeitkonto(year, groupId)` und Jahreszusammenfassung; zeigt Monats-Ist, Jahres-Ist und Saldo. Anzeige eines Istwerts bestätigt keine Gutschrift für einen neu erzeugten Plan. |
| Generator | `sp5_adapter._nominal_bookings`, `import_snapshot`; `solver.solve` | Importiert bisher nur TYPE 1 ins Periodensoll; Gutschriften/Anfangssalden bleiben ausdrücklich ungeklärt. Weiches Stundenziel ist `abs(geplante bezahlte Minuten + balance_minutes + credit_minutes - target_minutes)`. |

**Konkrete Mappinglücke (automatische Anrechnung weiterhin offen):** Datumsscharfe TYPE-0-Korrekturen und
Abwesenheitsanrechnungen fließen derzeit nicht automatisch in dieses weiche
Stundenziel ein. Das kann bei sonst identischen Eingaben die Verteilung
verändern. Es beweist weder die Ursache der gemeldeten Nichteinplanung noch
einen Verstoß gegen harte Wochen-/Tagesgrenzen. Ein Pluswert senkt im
vorhandenen Zielmodell den verbleibenden Stundenbedarf, ein Minuswert erhöht
ihn. `credit_minutes` ist ausschließlich nichtnegativ; deshalb wäre schon
eine pauschale TYPE-0-Zuordnung zu diesem Feld falsch.

**Nachgewiesene Doppelzählungsgefahr, kein aktuell eingebauter Fehler:**
Ein bestehender Achtstundendienst mit +2h Istbuchung ergibt in der Library
10h Ist. Werden diese 10h als Gutschrift übernommen und derselbe Dienst neu
eingeplant, bewertet der Generator 18h statt 10h. Ebenso darf ein bereits
im Kontosaldo enthaltener Jahresübertrag nicht nochmals addiert werden.
Eine Januarbuchung ist keine Buchung eines einzelnen späteren Planungstags;
ein Anfangssaldo braucht eine ausdrücklich getrennte Stichtagsberechnung.

**Synthetischer Nachweis:**
`tests/test_nominal_bookings.py:test_actual_account_is_not_a_replanning_credit`
prüft vier signierte Korrekturen (-10/-2/+2/+10h), vorhandene Arbeit versus
Neuplanung ohne Arbeit, einen außerhalb des Ausschnitts liegenden Übertrag
sowie getrennte TYPE-1-/TYPE-2-Konten gegen die echte Library. Alle vier
Fälle erhalten die offene Generator-Einrichtungsdiagnose und erfinden keine
Wochenobergrenze. Die 46 vorhandenen Library-Tests in
`tests/test_calculations.py` bestehen ebenfalls, einschließlich
`test_deductact_subtracts` und `test_saldo_booking_types_separated`.

**Priorisierte nächste Korrektur:** Einzelkomponenten zunächst mit Datum,
Vorzeichen und Herkunft nachvollziehbar abbilden, ohne gesamte Ist-/Saldo-
Summen als Gutschrift zu übernehmen. Vor automatischer Anrechnung sind
Periodenkorrekturen, Abwesenheitsanrechnung und Anfangssaldo voneinander zu
trennen; bereits manuell gepflegte Werte dürfen nicht zusätzlich gezählt
werden. Die Quelle belegt die Kontenrechnung, nicht den gewünschten
Saldoausgleich des Nutzers. Keine automatische Regelbestätigung und keine
Änderung harter Arbeitszeitgrenzen folgen aus dieser Analyse.

### Datumsscharfe Istbuchungen: Herkunft erhalten, nicht automatisch anrechnen

Der Import erhält jetzt `metadata.provenance[employee_id].actual_bookings`:
BOOK-Quell-ID, Datum, TYPE 0 und signierter Stundenwert, beschränkt auf die
gewählten Personen und den exakten Zeitraum. `applied: false` und
`classification: unresolved` kennzeichnen die noch ausstehende fachliche
Einordnung. Notiztexte werden dafür nicht kopiert. Fehlende Buchungsquelle
bleibt von einer erfolgreich gelesenen leeren Liste unterscheidbar.

Datenfluss: `SP5Database.get_bookings` (5BOOK) → API
`sp5api/routers/reports.py:get_bookings` → Generator
`api_adapter._Database.get_bookings` → `sp5_adapter._nominal_bookings`.
Der bestehende Monatsabruf liefert beide Buchungsarten; kein zweiter Abruf
und keine neue Kontoberechnung sind nötig. Die OSP5-Kontoanzeige
`frontend/src/pages/Zeitkonto.tsx` bleibt eine aggregierte Kontosicht, keine
Freigabe zur Übernahme ihres Istgesamtwertes als Generator-Gutschrift.

`tests/test_nominal_bookings.py` prüft negative und gleiche getrennte
Buchungen, Quell-IDs, Zeitraum/Personenfilter, Buchungen vor Beschäftigungsbeginn,
JSON-Erhaltung, fehlerhafte Werte und fehlend versus leer. Zielstunden,
Gutschrift, Anfangssaldo und harte Grenzen werden dadurch nicht verändert.
TYPE 0 allein unterscheidet keine manuelle Korrektur von einem Jahresübertrag;
das bleibt vor einer expliziten Übernahme zu klären. Abwesenheitsanrechnung
bleibt separat: `calculations.absence_hours`, `charge_factor`, `absence_sums`
bewerten Arbeitstage/Feiertage, INTERVAL, CHARGETYP/CHARGEHRS und DEDUCTACT.
Ein bloßes Generator-Abwesenheitsintervall enthält diese Bewertung nicht.

### Abwesenheitsart im Planungskontext nicht verlieren

Belegte Mappinglücke: `sp5_adapter.import_snapshot` ließ `leave_type_id`
beim Aufbau von `metadata.context_schedule` weg. Gleichzeitig dient dieser
reduzierte Datensatz als Deduplizierungsschlüssel: verschiedene Abwesenheitsarten
mit identischer Person, Datum und Zeit konnten zusammenfallen. Der Import
behält nun die von der Quelle gelieferte Typ-ID; fehlende/anonymisierte IDs
bleiben `null`. Freitext und Anzeigenamen werden weiterhin nicht übernommen.

Datenfluss: `ABSEN.LEAVETYPID` → Library
`database.SP5Database.get_schedule` → API
`sp5api/routers/schedule.py:get_schedule` einschließlich
`apply_absence_visibility` → Generator `api_adapter._Database.get_schedule`
→ `sp5_adapter.import_snapshot`. OSP5 nutzt dieselbe ID in
`frontend/src/pages/Schedule.tsx` für Abwesenheitsfilter und das Übertragen
von Abwesenheiten. Die Sichtbarkeitsbeschränkung der API wird nicht umgangen:
eine entfernte Typ-ID wird weder erraten noch aus anderen Quellen ergänzt.

Der Typ allein ist **noch kein Stundenwert**. `calculations.absence_sums`
benötigt zusätzlich Typdefinition, Beschäftigung, Arbeitstage und Feiertage;
`absence_hours` und `charge_factor` berücksichtigen unter anderem INTERVAL,
COUNTALL, CHARGETYP und CHARGEHRS. DEDUCTACT kann die Richtung der Anrechnung
ändern. Fehlende Typdefinitionen dürfen deshalb bei einer künftigen Bewertung
nicht als nachgewiesene Nullstunden gelten. Harte Arbeitszeitgrenzen und
Ruhezeiten bleiben getrennt von dieser Kontenbewertung.

Regression: `test_absence_type_provenance_survives_deduplication_and_json`
prüft Ist/Soll-Referenzwahl, unterschiedliche Arten am gleichen Intervall,
doppelte Quellzeilen, fehlende Typ-ID und JSON-Erhaltung. Alle Mitarbeiterfelder
außer der Zahl identischer Sperrintervalle bleiben gleich; die tatsächlich
gesperrten Zeiträume bleiben identisch. Keine Gutschrift, Freigabe oder
Profilbestätigung wird daraus abgeleitet. Dieser Befund erklärt einen
Herkunftsverlust, nicht den weiterhin fehlenden Originalfall mit 600 Sekunden.

### Wochenlimit-Diagnose darf Tagesverstöße nicht verdecken

Synthetisch belegter zusätzlicher Befund in `validator.validate`: Tages- und
Wochenlimits liefen in derselben Tagesschleife. Nach der ersten überschrittenen
Wochensumme beendete `break` die Schleife für das gesamte Profil. Bereits am
Montag konnte dadurch die Tagesüberschreitung eines späteren Dienstags sowie
eine zweite verletzte Kalenderwoche unsichtbar bleiben. Das Ergebnis war
bereits ungültig; der Befund belegt **keine** Annahme eines unzulässigen Plans
und erklärt ohne Originaleingabe nicht den gemeldeten 600-Sekunden-Fall.

Die unabhängige Prüfung durchläuft nun alle relevanten lokalen Tage und danach
jede relevante ISO-Woche genau einmal. Reale Einsatzminuten, Profilgültigkeit,
Randkontext und Überhang nach Periodenende bleiben unverändert. Der Solver
hatte Tages- und Wochenbedingungen bereits getrennt (`solver.solve`); seine
harten Bedingungen werden nicht verändert. Bestehende Bibliotheks-/API-
Sollstunden sind weiterhin keine konfigurierte harte Wochenhöchstgrenze.

`tests/test_partial_limits.py::test_weekly_violation_does_not_hide_later_daily_or_weekly_diagnostics`
reproduziert den alten Fehler für Voll- und Teilplanung: zwei Zehnstundendienste
in zwei Wochen, explizite synthetische Neunstunden-Tages-/Wochenlimits. Erwartet
werden beide Tages- und beide Wochenmeldungen. Vollplanung bleibt INFEASIBLE;
Teilplanung lässt beide Dienste offen und verletzt keine harten Grenzen.
Die synthetischen Neunstundenwerte sind keine Nutzerdefaults.

### Abwesenheitsstunden getrennt bewerten, nicht als Arbeitszeit übernehmen

`api_adapter._Database.get_leave_types(include_hidden=True)` ergänzt den
vorhandenen lesenden API-Endpunkt `master_data.get_leave_types`. Die Library
liest dabei LEAVT einschließlich ausgeblendeter, historisch verwendeter Arten.
Nur die bereits im sichtbaren Schedule gelieferte Typ-ID wird aufgelöst;
anonymisierte IDs werden nicht rekonstruiert. `database.get_schedule` bildet
ABSEN.DATE/LEAVETYPID/INTERVAL/START/END auf die datierten Schedule-Felder ab.
Die OSP5-Kontoansicht `frontend/src/pages/Zeitkonto.tsx` zeigt aggregierte
Konten und Abwesenheitstage; das ist keine replanning-sichere Zeitgutschrift.

Der Generator erhält nun in `metadata.provenance[employee_id].absence_accounting`
eine Bewertung jeder sichtbaren, deduplizierten Abwesenheit innerhalb des
Planungszeitraums. `absence_evidence.absence_evidence` verwendet unverändert
`calculations.EmployeeContext.from_record` und `absence_sums`; diese rufen
`absence_hours` und `charge_factor` auf und klemmen an die Beschäftigung.
Die drei Ergebnisse bleiben getrennt: `charged`, `charged_deduct_actual`,
`raw_deduct_overtime`. Es erfolgt keine neue Stundenarithmetik und keine
Übernahme in Zielstunden, Gutschrift, Anfangssaldo oder Arbeitszeitlimits.
`applied: false` bleibt auch bei erfolgreicher Bewertung bestehen.

Fehlende Typdefinitionen und ungültige Zeitintervalle sind ausdrücklich
`unresolved`, ohne einen Stundenwert. Gleiche Start-/Endminute bleibt wie in
der bisherigen Generator-Verfügbarkeitsprüfung ungeklärt, obwohl die Library
diese rechnerisch als 24 Stunden bewertet; dies ist keine Aussage über die
Zulässigkeit von 24-Stunden-Diensten. Die Schedule-Quelle liefert keine
ABSEN-Datensatz-ID und wird teamübergreifend dedupliziert: Die Einzelbewertungen
sind deshalb **keine zertifizierte vollständige Kontensumme** und werden nicht
automatisch addiert oder bestätigt. Freitext wird nicht übernommen.

`tests/test_absence_evidence.py` prüft Anrechnung/Abzüge, feste Tageswerte,
ganze/halbe/stundenweise Abwesenheiten, Mitternacht, Arbeitstage, ganze/halbe
Feiertage, COUNTALL, Beschäftigungsgrenzen, fehlende Definitionen,
Scope/Deduplizierung, JSON-Erhaltung sowie GET-Transport einschließlich
ausgeblendeter Arten. Bestehende Library-Tests in `tests/test_calculations.py`
belegen dieselbe Anrechnungssemantik. Ungeklärte persönliche Freigaben,
Profile und die fehlende Originaleingabe des 600-Sekunden-Falls bleiben davon
unberührt.

### Datierter Profilwechsel innerhalb einer ISO-Woche

`solver.solve` summiert bei `max_weekly_minutes` für jede vom gültigen Profil
berührte Planungswoche die vollständigen sieben lokalen Kalendertage.
`validator.validate` prüft dieselbe Wochensumme. Bei zwei nacheinander gültigen
Profilen innerhalb derselben Woche gelten damit beide Wochenobergrenzen für
die gesamte Woche (effektiv die strengere), nicht zwei getrennte Teilbudgets.
Dies beschreibt die bestehende Generatorsemantik, keine aus SP5 abgeleitete
neue fachliche Vorgabe oder automatische anteilige Umrechnung.

`tests/test_calendar_limits.py::test_dated_profile_switch_preserves_whole_iso_week_limit`
belegt acht Kombinationen: strengeres altes/neues Profil, Voll-/Teilplanung,
Wechsel innerhalb einer Woche oder Sonntag/Montag. Zwei reale Vierstundendienste
mit je nur einer bezahlten Stunde überschreiten das Vierstunden-Wochenlimit
auch bei hohem Soll; der Teilplan darf dann nur einen Dienst besetzen.
An verschiedenen ISO-Wochen dürfen beide Dienste stattfinden. Der unabhängige
Validator weist genau die erwartete Wochenverletzung aus. In diesen Fällen
wurde kein Solver-/Validator-Unterschied gefunden; der fehlende originale
600-Sekunden-Projekt-/Jobstand bleibt für die konkrete Fehlerursache notwendig.

### Bestätigte Profilabdeckung für tatsächlichen Dienstüberhang

Zusätzlicher reproduzierter Fehler: `domain.input_diagnostics` prüft die
Profilbestätigung nur zwischen `period_start` und `period_end`. Ein am letzten
Planungstag beginnender Dienst konnte danach ohne gültiges bestätigtes
Folgeprofil weiterlaufen. `domain.eligibility` prüfte Beschäftigung, Freigabe und
Verfügbarkeit über den Dienst hinweg, aber nicht diese Profilabdeckung.
Der unabhängige Validator akzeptierte deshalb im synthetischen Beispiel
23–03 Uhr sowohl ein fehlendes als auch ein unbestätigtes Folgeprofil.
Ein fehlendes Profil bedeutete zugleich fehlende profilbezogene Zeitlimits
für den Überhang. Das ist kein Nachweis der Ursache des originalen 600s-Laufs.

Die bestehende Kandidatenprüfung verlangt nun für jeden tatsächlich gearbeiteten
lokalen Folgetag mindestens ein gültiges zugeordnetes Profil und Bestätigung
aller dort gültigen zugeordneten Profile. Solver und Validator verwenden diese
Prüfung; Teilplanung darf den Dienst offenlassen, aber nicht ohne Profil
besetzen. Die Ausschlussdiagnose benennt die fehlende bestätigte Abdeckung.
Historische Randarbeit bleibt unverändert; es werden keine Profile verlängert,
Freigaben erfunden oder SP5-Sollstunden als Höchstgrenzen interpretiert.

`test_overnight_spill_requires_confirmed_profile_coverage` prüft Voll-/Teilplan,
fehlendes/unbestätigtes/bestätigtes Folgeprofil sowie Dienstende exakt um
Mitternacht gegenüber tatsächlicher Arbeit am Folgetag. Für ein Ende um 00 Uhr
wird kein Profil für den nicht gearbeiteten Folgetag verlangt. Vier ursprüngliche
Gegenproben schlugen vor der Korrektur wegen fälschlich gültiger Validierung fehl.


### API-Ruheprüfung ist bei Nullabstand und Überlappung kein Abnahmenachweis

Weiterer konkreter Quellenbefund am unveränderten API-Stand `d578f21`:
`routers/work_time_rules.py:_check_employee` meldet tägliche Ruhe ausschließlich
bei `0 < rest_hours < min_rest`. Bei direkt anschließenden Diensten (0 Minuten)
oder überlappenden Diensten (negativer Abstand) entsteht dort **keine**
Ruheverletzung; eine gesonderte Überlappungsprüfung enthält die Funktion nicht.
Andere Grenzen können trotzdem Meldungen auslösen. Eine leere Meldungsliste
ist deshalb kein Nachweis gültiger Ruhe oder überschneidungsfreier Einteilung.

Der zusammenhängende Pfad ist `MASHI/CYASS/SPSHI` → API `_employee_plan` →
`_collect_day_data` (Library `calculations.parse_startend` für Zeitfenster,
`shift_hours_on_day` für getrennte Stundenbewertung) → `_check_employee` →
OSP5 `frontend/src/pages/WorkTimeRules.tsx` (Aufruf `api.checkWorkTimeRules`)
→ `ViolationList`.
Die Anzeige verwendet die zurückgegebenen Verletzungen und zeigt bei einer
leeren Liste „Keine Verstöße gefunden“; sie prüft die Intervalle nicht erneut.
Der Generator übernimmt diese Prüfantwort nicht als Zertifikat:
`domain.pair_conflict` prüft Überschneidung und Ruhe, und wird von
`solver.solve` und `validator.validate` verwendet.

Synthetische isolierte Gegenprobe am 11.09.2026: Originalfunktion
`_check_employee` per AST unverändert aus dem lokalen Checkout geladen, nur
`_collect_day_data` durch zwei künstliche Vierstundenblöcke ersetzt. Keine
API-Verbindung und keine Personaldaten. Start des ersten Dienstes 07.09.2026
08:00 UTC, zweiter Dienst jeweils nach untenstehendem Abstand. Tages-/Wochen-
und Seriengrenzen für diese isolierte Ruheprobe auf 100h/100h/365 gesetzt;
11h tägliche Ruhe. Generatorfixture `tests/test_calendar_limits.py:sample`
mit denselben Intervallen und 660 Minuten Mindestruhe verwendet.

| Abstand zum Dienstende | API-Ruheverletzungen | Generator: beide Einteilungen gültig | Vollplan | Teilplan |
| --- | --- | --- | --- | --- |
| −60 Minuten | keine | nein, Überschneidung | INFEASIBLE | ein Dienst, gültig |
| 0 Minuten | keine | nein, Ruhe | INFEASIBLE | ein Dienst, gültig |
| 60 Minuten | eine | nein, Ruhe | INFEASIBLE | ein Dienst, gültig |
| 660 Minuten | keine | ja | OPTIMAL | beide Dienste, gültig |

Die bestehenden API-Tests `test_min_rest_violation` und
`test_sufficient_rest_no_violation` prüfen positive 3h beziehungsweise 16h
Abstände; sie belegen nicht die Null-/Negativfälle. Diese Gegenprobe isoliert
nur die Prüfentscheidung, nicht den vollständigen API-Transport oder das
Mapping. Es wurde kein Generatorfehler in diesen vier Fällen gefunden und
keine produktive API oder OSP5-Installation verändert. Die API-Lücke ist als
separater Korrekturpunkt vorgemerkt; sie beweist nicht die Ursache des originalen
0.9.29-Laufs. Die unabhängige Generatorprüfung bleibt für die Abnahme notwendig.

### API-Arbeitszeitprüfung addiert Ist und Soll statt einer ausgewählten Sicht

Weiterer isolierter Quellenbefund am selben API-Stand `d578f21`:
`work_time_rules._employee_plan` liest `MASHI` über `_dated` und filtert dabei
nur Person und Datum, nicht `TYPE`. `_collect_day_data` summiert anschließend
alle zurückgegebenen regulären Dienste. Demgegenüber definiert die Library
`Database.get_schedule` `TYPE=0` als Ist und `TYPE=1` als Soll und trennt die
Sichten über `plan` / `schedule_type` (database.py:545–575, 704–712).
Zwei alternative Sichten sind damit in dieser API-Arbeitszeitprüfung nicht
automatisch zwei tatsächlich geleistete Dienste.

OSP5 `WorkTimeRules.tsx:runCheck` und `runCheckAll` übergeben Person/Gruppe,
Zeitraum und Grenzparameter, aber keine Ist-/Soll-Auswahl. Der eigenständige
Generator-Import folgt dagegen `api_adapter.import_api_snapshot(reference_plan)`
→ `_Database.get_schedule(plan=...)` → API-Schedule-Sicht. Die gemeinsame
Stundensumme des Arbeitszeitprüfrouters ist kein Generator-Abnahmenachweis.

Synthetische Gegenprobe vom 11.09.2026: Die Originalfunktionen `_employee_plan`,
`_collect_day_data` und `_check_employee` unverändert per AST geladen und mit
der echten Library `calculations` ausgeführt. Ausschließlich künstliche
`_read`-Tabellen: eine Person, 07.09.2026, Dienst 08–16 Uhr, DURATION=8,
keine Zyklen/Sonderdienste/Feiertage. Prüfgrenzen ausschließlich für diese
Gegenprobe: 10h täglich, 12h wöchentlich, 11h Ruhe, sechs aufeinanderfolgende
Arbeitstage; dies sind keine neuen Generator- oder Nutzerdefaults.

| MASHI-Typen | API-Stunden | API-Zeitblöcke | gemeldete Verletzungen |
| --- | --- | --- | --- |
| nur 0 (Ist) | 8 | 1 | keine |
| nur 1 (Soll) | 8 | 1 | keine |
| 0 und 1 am selben Tag | 16 | 2 | Tages- und Wochenmaximum |

Alle drei erwarteten Stundensummen und Verletzungsanzahlen wurden per Assertion
bestätigt. Die vorhandenen API-Tests `tests/test_work_time_rules.py` enthalten
keine Ist-/Soll-Gegenprobe; die Library trennt diese Semantik in
`tests/test_soll_ist_plan.py` und `tests/test_conflict_soll_ist.py`.
Dies ist ein weiterer belegter Vergleichsfehlerpfad im separaten API-Werkzeug,
keine bewiesene Ursache des originalen Generator-600s-Laufs und keine neue
Generator-Runtimekorrektur. Keine produktive API geändert, kein Live-POST,
keine Originaldaten verwendet. Ein künftiger Upstream-Fix muss die gewünschte
Prüfsicht explizit festlegen und Zyklen/Sonderersatz konsistent dazu behandeln.

### Soll-Materialisierung unterdrückt einen Ist-Zyklus vor dem Sichtfilter

Am Library-Stand `0dac443` synthetisch reproduziert: In
`Database._cycle_shifts_by_employee` (database.py:287–324) enthält `mashi_days`
alle Person-/Datum-Paare aus MASHI **ohne TYPE-Filter**. Ein ausschließlich
vorhandener Soll-Eintrag unterdrückt deshalb bereits die Zyklusexpansion.
`Database.get_schedule` fügt Zyklusdienste als `schedule_type=0` hinzu und
filtert erst anschließend nach Ist/Soll (database.py:595–619, 704–714).

Gegenprobe mit unveränderter echter `SP5Database.get_schedule` und echter
`calculations.expand_cycle_assignments`, ausschließlich künstlichen Tabellen:
CYCLE ID=1/SIZE=1/UNIT=0, CYENT CYCLEEID=1/INDEX=0/SHIFTID=5,
CYASS EMPLOYEEID=10/CYCLEID=1/START=END=2026-09-07/ENTRANCE=0.
Leere Sonderdienste/Abwesenheiten/Stammdaten; optional ein MASHI-Eintrag für
Person 10 am gleichen Datum mit SHIFTID=9. Nur die Tabellenleser und leeren
Stammdatenleser wurden ersetzt; keine DBF-Datei oder API geändert.

| MASHI am Zyklustag | Ist-Dienste | Soll-Dienste | beide Sichten |
| --- | --- | --- | --- |
| keiner | Zyklus 5 | keine | Zyklus 5 |
| TYPE=0 | Dienst 9 | keine | Dienst 9 |
| TYPE=1 | **keine** | Dienst 9 | Dienst 9 |

Damit ist die fehlende Ist-Ausgabe im dritten Fall belegt. Der fachlich
beabsichtigte Ersatzvertrag muss bei einer Upstream-Korrektur explizit bleiben:
Soll ist eine alternative Sicht, nicht automatisch eine tatsächlich
materialisierte Ist-Belegung. Nicht pauschal alle MASHI-Unterdrückung entfernen;
sonst drohen doppelte Dienste im echten Ist-Fall. Sonderersatz und gemeinsame
Nutzung des Helpers durch `_calc_inputs` ebenfalls berücksichtigen.

Transportpfad: API `sp5api/routers/schedule.py:get_schedule` reicht `plan` an
die Library durch. OSP5 `frontend/src/api/client.ts:1304` fordert dieselbe
Schedule-Sicht an. Generator `api_adapter._Database.get_schedule` →
`sp5_adapter._scope_schedule` erhält nur die schon gefilterten Zeilen;
`_reference_schedule` liest auch Ist als Ersatzbasis. Fehlende Quelldienste
können damit Referenz- und Randkontext unvollständig machen. Das ist eine
Folgerung aus dem Datenfluss, kein Nachweis betroffener realer Personen oder
der ursprünglichen 0.9.29-Fehlerursache. Fehlende Dienste werden nicht erfunden.

Vorhandene Librarytests `test_soll_ist_plan.py` sowie
`test_database_calculations.py:test_schedule_read_paths_expand_cycles`:
5 ausgewählte Tests bestanden am 11.09.2026; die kombinierte Soll-/Zyklusprobe
oben ist darin nicht abgedeckt. Kein Generator-Runtimefix, kein neues Release;
Korrekturpriorität: planbewusste Zyklus-Unterdrückung upstream mit diesen drei
Fällen und Sonderersatz/Kontoberechnung absichern, anschließend Quellenabnahme.

### Zeitkonto zählt alternative Soll-Dienste als Iststunden

Zusätzlich am Library-Stand `0dac443` über die unveränderte öffentliche Fassade
`SP5Database.calculate_time_balance` reproduziert:
`_calc_inputs` → `_movement_by_employee("MASHI", ...)` filtert nur Datum und
Person, nicht die Plansicht. `_plan_kwargs` reicht sämtliche Zeilen an
`calculations.get_actual_hours` → `get_work_hours` weiter; dort werden die
regulären Dienste ebenfalls ohne MASHI-TYPE-Filter summiert.
`_time_balance_from_inputs` veröffentlicht die Summe als monatliche
`actual_hours` und jährliche `total_actual_hours`.

Wiederholbare, ausschließlich synthetische Probe:

```sh
PYTHONPATH=/path/to/libopenschichtplaner5 .venv/bin/python tools/audit_upstream_plan_accounting.py
```

Das Werkzeug ersetzt nur Tabellen-/Stammdatenleser, verwendet echte
Fassaden-/Berechnungsfunktionen und greift weder auf DBF-Dateien noch eine API
zu. Alle Dienste liegen am 07.09.2026, 08–16 Uhr, DURATION=8; keine
Buchungen, Abwesenheiten oder Sonderdienste. Monat und Jahr ergeben jeweils:

| MASHI-Typen | ohne Zyklus | mit gleichwertigem Zyklus |
| --- | --- | --- |
| nur Ist (0) | 8h | nicht separat geprüft |
| nur Soll (1) | **8h Iststunden** | **8h Iststunden** |
| Ist und Soll (0, 1) | **16h Iststunden** | **16h Iststunden** |
| keine | nicht separat geprüft | 8h |

Sechs Fälle mit zwölf Assertions charakterisieren den fehlerhaften Iststand,
nicht den gewünschten Vertrag. Nach einem Upstream-Fix muss die Probe bewusst
angepasst werden; sie ist kein Generator-CI-Gate. Ein erster Fixturelauf ohne
STARTEND-Fenster lieferte korrekt 0h; die endgültige Probe setzt sowohl reale
Zeitfenster als auch bezahlte Dauer explizit.

Datenfluss bis zur Anzeige: API `routers/reports.py:get_zeitkonto_detail`
ruft `calculate_time_balance` auf; Übersicht/Summary verwenden
`get_zeitkonto` mit demselben Berechnungspfad. OSP5 `api/client.ts`
`getZeitkontoDetail`/`getZeitkonto` und `pages/Zeitkonto.tsx` zeigen diese
Iststunden direkt an. Generator `api_adapter.py`/`sp5_adapter.py` verwenden
diese Zeitkonto-Endpunkte und `actual_hours`-Gesamtsummen dagegen nicht.
Keine direkte Übernahme dieser Doppelzählung in die Generator-Zielfunktion
belegt. Ein Vergleich gegen das OSP5-Zeitkonto ist daher allein keine
unabhängige Stundenvalidierung.

Korrektur muss upstream die Plansicht für **beide** Schritte konsistent
festlegen: MASHI-Auswahl und Zyklusunterdrückung. Nur TYPE=1 aus der Summierung
zu entfernen ließe bei vorhandener Soll-Materialisierung weiterhin den
zuvor unterdrückten Ist-Zyklus fehlen. Sonderersatz und Zuschläge bleiben als
weitere gemeinsame Verbraucher zu prüfen. Keine produktive Quelle geändert,
keine harten Generatorgrenzen verändert, kein Original-600s-Ursachennachweis.

### Zuschlagsberichte erben dieselbe Ist-/Soll-Vermischung

Die gemeinsame Verbraucherprüfung am selben Library-Stand `0dac443` ist nun
auch über die beiden unveränderten Fassaden `calculate_extracharge_hours`
und `extracharge_hours_by_day` reproduziert. Das bestehende synthetische
Werkzeug `tools/audit_upstream_plan_accounting.py` enthält dafür eine explizite
Ganztags-Zuschlagsregel am Testdatum. In sämtlichen sechs Fällen stimmen
Monatszuschlag und Summe der Tageszuschläge mit der obigen 8h/16h-Tabelle
überein. Insbesondere ergeben identische Ist- und Soll-Einträge zusammen
**16 Zuschlagsstunden bei nur einem gezählten Mitarbeitertag**; die Tageszahl
ist daher keine Plausibilitätsprüfung der Stundensumme. Insgesamt bestehen
jetzt 30 Assertions. Dies charakterisiert den Quellfehler, nicht Sollverhalten.

Konkreter Pfad: `_calc_inputs` / `_plan_kwargs` liefern beide MASHI-Plansichten
an `calculations.daily_work_intervals`. Die Funktion hängt beide Zeitfenster
an dieselbe Tagesliste, ohne TYPE-Auswahl oder Vereinigungsbildung.
`extracharge_hours_on_day` summiert jeden Fensterschnitt separat. Eine bloße
Intervallvereinigung wäre trotzdem keine vollständige Korrektur: verschiedene
alternative Ist-/Soll-Zeiten müssen nach Plansicht ausgewählt werden, und die
zuvor belegte Zyklusunterdrückung muss dazu passen. `NOEXTRA` wird hier bewusst
berücksichtigt; Zuschlagsintervalle sind deshalb auch unabhängig von diesem
Fehler kein vollständiger Arbeitszeitnachweis für harte Tages-/Wochenlimits.

API `sp5api/routers/master_data.py` reicht Monats-/Zeitraum- und Tageswerte
an `/api/v1/extracharges/summary` beziehungsweise `/api/v1/extracharges/by-day`
weiter; `routers/reports.py` verwendet die Monatsfassade ebenfalls.
OSP5 `frontend/src/api/client.ts:getExtrachargesByDay` →
`pages/Berichte.tsx:reportExtrachargesByDay` übernimmt die Tageswerte für
Druck/CSV, mit Gruppenfilter, aber ohne Plansichtkorrektur.
Generator `api_adapter.py` und `sp5_adapter.py` rufen diese Zuschlagsfassaden
nicht auf. Das Ergebnis grenzt die Verlässlichkeit externer Vergleichswerte
ein, belegt aber weiterhin keinen direkten Generatorfehler und keine Ursache
des fehlenden Original-600s-Laufs.

Vorhandene Librarytests `test_extracharge_hours_by_day_splits_at_midnight`,
`test_extracharge_validdays_compact_format_counts_all_days` und
`test_noextra_shift_yields_no_charge` sichern andere Zuschlagsaspekte;
die zusätzliche Probe deckt die plansichtübergreifende Doppelzählung ab.
Keine produktive Library/API geändert, keine privaten Daten verwendet.

### Konsolidierte Korrekturprobe: Plansicht vor beiden Verarbeitungsschritten

Das bestehende Auditwerkzeug prüft zusätzlich zur Fehlercharakterisierung
jetzt einen **isolierten Eingangsfilter**, keine Änderung der Library oder
Generator-Runtime. Nur beim synthetischen Lesen von MASHI wird TYPE=1 vor
`_movement_by_employee` **und** `_cycle_shifts_by_employee` ausgeschlossen.
Die unveränderten Fassaden rechnen anschließend wie bisher. SPSHI bleibt
vollständig erhalten; sein TYPE=1 ist ausdrücklich keine Soll-Kennzeichnung.

18 Kombinationen (sechs Ist/Soll/Zykluslagen × ohne Sonderdienst / Ersatz /
Zusatz) prüfen monatliche und jährliche Iststunden sowie Monats- und
Tageszuschläge gemeinsam mit 72 Assertions. Die 30 Assertions der bisherigen
Fehlercharakterisierung bleiben daneben bestehen. Testdienst: 08–16 Uhr/8h;
Sonderdienst: 18–20 Uhr/2h, einmal mit SHIFTID=5 als Tagesersatz, einmal mit
SHIFTID=0 als Zusatz. Dies sind ausschließlich künstliche Prüfdaten.

| Quelldaten | Iststunden nach früher Auswahl | mit Ersatz | mit Zusatz |
| --- | --- | --- | --- |
| nur Ist, kein Zyklus | 8 | 2 | 10 |
| nur Soll, kein Zyklus | 0 | 2 | 2 |
| Ist und Soll, kein Zyklus | 8 | 2 | 10 |
| nur Zyklus | 8 | 2 | 10 |
| Soll und Zyklus | 8 | 2 | 10 |
| Ist, Soll und Zyklus | 8 | 2 | 10 |

Alle vier Verbraucher liefern diese Werte. Damit ist ein zusammenhängender
Korrekturansatz für den Ist-Rechenpfad synthetisch belegt: keine Doppelzählung,
kein Verlust des Ist-Zyklus durch eine alternative Sollzeile und weiterhin
unterschiedliche Behandlung von Ersatz und Zusatz. Das ist **kein** fertiger
Upstream-Patch: Index-/Cacheleser, Soll-/Both-Sichten, API-Verträge und
Bestandskompatibilität müssen beim Einbau gemeinsam behandelt werden.

Priorisierte Umsetzung und Abnahme:

1. **Library:** Plansicht explizit an MASHI-Auswahl und Zyklusunterdrückung
   durchreichen; Istkonten als Ist berechnen. Nicht pauschal TYPE auf allen
   Tabellen filtern und nicht lediglich fertige Summen halbieren. Die
   vorhandenen Ersatzfunktionen weiterverwenden.
2. **API/OSP5:** `work_time_rules._employee_plan` und die Aufrufer
   `WorkTimeRules.tsx` auf denselben expliziten Sichtvertrag bringen;
   Zeitkonto/Zuschläge durch die korrigierte gemeinsame Librarybasis führen.
   Ein API-Prüfergebnis bleibt vom unabhängigen Generatorvalidator getrennt.
3. **Generatorquellen:** Schedule-Transport einschließlich Soll/Both,
   Zyklus-Randkontext und Sonderersatz gegen korrigierte Library/API prüfen.
   Die fehlende Ist-Zykluszeile ist hier der konkrete betroffene Importpfad;
   Zeitkonto-/Zuschlagssummen werden dagegen nicht importiert. Keine
   fehlenden Dienste aus aggregierten Stunden rekonstruieren.
4. **Originalfehler:** gespeicherten 0.9.29-Projekt-/Job-/Ergebnisstand mit
   wirksamen Profilen und tatsächlichen Wochenhöchstgrenzen weiter als
   notwendiges Beweisstück führen. Dieser Quellenbefund erklärt nicht
   automatisch die gemeldeten 24h-Dienste oder den 600s-Teilplan.

Keine produktiven Quellen oder Benutzerinstallation geändert. Unveränderte
0.9.31 wurde nicht erneut direkt gegen dieselbe API getestet; deren letzte
private Abnahme bleibt oben ausdrücklich als blockierte Neuplanung geführt.

### Isolierter Library-Korrekturkandidat mit vollständiger Testsuite

`tools/upstream-ist-accounting-candidate.patch` ist ein reviewbarer Patch gegen
Library `0dac443`, **kein installierter Fix**. Er wurde ausschließlich auf eine
Kopie unter `/tmp/sp5-upstream-candidate` angewendet. Originalcheckout, laufende
API und Generator-Runtime bleiben unverändert.

Der Kandidat ergänzt `_movement_by_employee(..., ist_only=False)` kompatibel
und aktiviert die Ist-Auswahl in `_calc_inputs` nur für MASHI. Die
Zyklusunterdrückung berücksichtigt nur Ist-MASHI-Zeilen: Zyklen tragen bereits
`schedule_type=0`, daher darf auch in Both eine Sollzeile den Istzyklus nicht
verdrängen. Der Monatsindex bleibt ungefiltert; der bestehende abschließende
`get_schedule(plan=...)`-Filter erhält Soll/Both. SPSHI bleibt unangetastet.

Reproduktion (Generator-venv, isolierte gepatchte Library auf PYTHONPATH):

```sh
PYTHONPATH=/tmp/sp5-upstream-candidate .venv/bin/python tools/audit_upstream_plan_accounting.py --candidate
PYTHONPATH=/tmp/sp5-upstream-candidate .venv/bin/python -m pytest /tmp/sp5-upstream-candidate/tests -q
```

Ergebnis: **90 Assertions** (72 gemeinsame Stunden-/Zuschlagsprüfungen plus
18 Ist/Soll/Both-Sichtprüfungen) bestanden. Anders als beim Eingangsfilter-
Experiment liest die Kandidatenprobe sämtliche synthetischen MASHI-Zeilen
ungefiltert. `get_schedule` verwendet den echten `_read_by_month`-Leser, mit
getrennten synthetischen Cacheidentitäten. Bestehende vollständige Librarysuite:
**297 passed, 6 skipped**. Ungepatchte Fehlercharakterisierung weiterhin grün.
Dies prüft keine reale DBF-Cacheinvalidierung und ersetzt keine API-Abnahme.

Verbleibende Integrationsgrenze konkret: API
`sp5api/routers/work_time_rules.py:_employee_plan` liest MASHI direkt und
expandiert/unterdrückt Zyklen selbst; es nutzt weder `_calc_inputs` noch den
gepatchten Library-Zyklushelfer. OSP5
`frontend/src/pages/WorkTimeRules.tsx` ruft `api.checkWorkTimeRules` auf.
Der Librarykandidat allein behebt diesen separaten Prüfpfad nicht. Auch
Library-Tages-/Wochenansichten besitzen weitere direkte MASHI-Leser und sind
nicht automatisch als planbereinigt zertifiziert. Deshalb noch keine
Produktivintegration und kein Release; als Nächstes den API-Prüfpfad mit
synthetischen alternativen Plansichten in denselben Vertrag aufnehmen.

### API-Prüfpfad: isolierter Ist-Kandidat und bestehende Helfertests

`tools/upstream-api-ist-plan-candidate.patch` ergänzt am API-Stand `d578f21`
vor `_dated` eine ausschließlich auf MASHI angewendete Ist-Auswahl. Damit
verwenden Stundenaddition und die lokale Zyklusunterdrückung dieselbe Sicht.
SPSHI.TYPE bleibt unberührt. Dies ist ein **explizit Ist-only experimenteller
Kandidat**, keine stillschweigende Festlegung des öffentlichen API-Defaults:
Eine Produktivintegration benötigt weiterhin den ausdrücklichen Sichtvertrag
im Endpoint und in OSP5 `WorkTimeRules.tsx`.

Reproduzierbares Werkzeug `tools/audit_upstream_work_time_plan.py` lädt die drei
Originalfunktionen `_employee_plan`, `_collect_day_data`, `_check_employee`
unverändert per AST, ohne Serverstart, DBF-Zugriff oder HTTP. Gegen Original
und isoliert gepatchte Datei jeweils **18 Fälle / 72 Assertions bestanden**:
Ist, Soll, beide, Zyklus ohne Materialisierung, Zyklus mit Soll sowie mit beiden
Sichten, jeweils ohne Sonderdienst, mit Ersatz oder mit Zusatz. Geprüft werden
Stundensumme, Blockzahl und Tages-/Wochenverletzungen. Die synthetischen Grenzen
10h/12h sind ausschließlich Testwerte, keine fachlichen Nutzerdefaults.

```sh
PYTHONPATH=/home/hilbert/projects/libopenschichtplaner5 .venv/bin/python tools/audit_upstream_work_time_plan.py /home/hilbert/projects/openschichtplaner5-api/sp5api/routers/work_time_rules.py
PYTHONPATH=/tmp/sp5-upstream-candidate .venv/bin/python tools/audit_upstream_work_time_plan.py /tmp/sp5-upstream-api-ist-candidate.py --candidate --helper-tests /home/hilbert/projects/openschichtplaner5-api/tests/test_work_time_helpers.py
```

Zusätzlich **acht bestehende reine API-Helfertests bestanden**, über AST mit
unveränderten Testfunktionen und originalen Defaultwerten ausgeführt. Die zwei
Dateikonfigurations-/HTTP-Tests wurden ausdrücklich nicht ausgeführt; dies ist
keine vollständige API-Testsuite oder Endpoint-Abnahme. Gemeinsame Gegenprobe
mit dem Librarykandidaten: dessen **90 Assertions weiterhin bestanden**.
Originalcheckouts, laufende API und Generator-Runtime unverändert; kein Release.

Die Korrekturprobe löst ausschließlich die Plansichtvermischung. Bekannte
Lücken bei Überlappung/Nullruhe, realen statt bezahlten Stunden und Randkontext
bleiben bestehen. Sie darf deshalb nicht als gleichwertiger Generatorvalidator
verwendet werden und belegt keine Ursache des fehlenden Original-600s-Artefakts.

Nächster zusammenhängender Integrationspunkt ist konkret abgegrenzt:
Library `get_schedule_day` und `get_schedule_week` schreiben nach dem
Zyklushelfer erneut **ungefilterte** MASHI-Zeilen in Person-/Datums-Dictionaries.
API `routers/schedule.py:get_schedule_day/get_schedule_week` reicht diese
Fassaden weiter. Ein korrigierter Zyklushelfer allein kann dort alternative
Sollzeilen als nachträglichen Override nicht verhindern. Dies ist zunächst ein
Codebefund, noch keine hier ausgeführte Tages-/Wochen-Reproduktion. Vor
Produktivintegration diese Ansichten mit unterschiedlichen Ist-/Soll-Diensten
und umgekehrter Quellreihenfolge gegen die Monatsansicht abgleichen.

### Tages-/Wochenansichten: Quellreihenfolge reproduziert

`tools/audit_upstream_schedule_views.py` prüft die echten Library-Fassaden
mit rein synthetischen, unterschiedlichen Ist-/Soll-Diensten. Vier Eingaben
(Ist, Soll, Ist→Soll, Soll→Ist), **20 Assertions bestanden**. Bei beiden
Planarten bleibt die Monatsansicht in `get_schedule(plan="ist"/"soll")`
korrekt getrennt. Tages- und Wochenansicht wählen dagegen jeweils die letzte
MASHI-Zeile: bloßes Umkehren der Quellreihenfolge ändert den sichtbaren Dienst.
Dies ist eine Fehlercharakterisierung, kein Sollverhaltenstest.

Datenfluss und Reichweite:

- Library `database.py:get_schedule_day/get_schedule_week`: ungefilterter
  MASHI-Override in ein Dictionary pro Person/Datum, ohne Planargument.
- API `routers/schedule.py:get_schedule_day/get_schedule_week`: delegiert an
  diese Methoden; nachgelagerter Abwesenheitsfilter trennt keine Planarten.
- OSP5 `api/client.ts:getScheduleDay/getScheduleWeek`: kein Planparameter;
  Nutzer unter anderem `Einsatzplan.tsx`, `DienstBoard.tsx`,
  `TeamUebersicht.tsx` und `Wochenansicht.tsx`.
- Generator `sp5_adapter.py:_scope_schedule` (Aufruf von `get_schedule`)
  und `api_adapter.py:get_schedule` verwenden den Monatsweg. Der neue Befund
  beweist daher **keinen Generator-Importfehler und keine Ursache des
  600s-Teilplans**. Er erklärt, warum ein visueller OSP5-Tages-/Wochenvergleich
  nicht ohne explizite Plansicht als Referenz für den Generator gelten darf.

```sh
PYTHONPATH=/home/hilbert/projects/libopenschichtplaner5 .venv/bin/python tools/audit_upstream_schedule_views.py
```

Priorisierte zusammenhängende Korrekturentscheidung: zuerst einen expliziten
Planvertrag für Library-Tages-/Wochenfassaden, API-Parameter und OSP5-Aufrufer
vorsehen; nicht nur die MASHI-Reihenfolge sortieren. `both` benötigt eine
Darstellung mehrerer Einträge statt eines verlustbehafteten Person/Datum-
Dictionaries. Danach Stundenprüfung und Referenzvergleich an denselben
Vertrag binden. Bisherige Ist-only-Stundenkandidaten bleiben experimentell.
Keine Änderungen an Originalcheckouts, produktiver API oder Benutzerinstallation.

### Mehrfachdienste derselben Planart: zusätzlicher Verlust belegt

Die erweiterte Charakterisierung prüft jetzt acht Quellreihenfolgen mit
40 Assertions. Auch zwei unterschiedliche **Ist-Dienste allein** (ebenso zwei
Soll-Dienste) bleiben im Monatsweg beide erhalten, während Tages-/Wochenweg
nur den jeweils letzten liefert. Ein Planfilter allein behebt diesen Verlust
also nicht. Die synthetische Eingabe belegt den Darstellungsverlust, nicht die
fachliche Zulässigkeit zweier konkreter Dienste oder deren reale Dauer.

Zusätzliche Kompatibilitätsgrenze: OSP5
`frontend/src/pages/Wochenansicht.tsx` baut in der Tageszuordnung mit
`m.set(entry.employee_id, entry)` erneut einen Eintrag pro Person. Nur die
Library auf Listen umzustellen genügt deshalb nicht. API
`routers/schedule.py:get_schedule_day/get_schedule_week` besitzt derzeit kein
Planargument. Vorhandene Librarytests in
`tests/test_database_calculations.py` prüfen Zyklus-/Materialisierungspriorität
und freie Tage, aber dort nicht zwei normale Dienste derselben Person am Tag.

Korrekturvertrag muss deshalb **für ist, soll und both** Mehrfacheinträge
verlustfrei tragen, freie Personentage erhalten und Sonderdienst-/Abwesenheits-
Priorität ausdrücklich abgrenzen. Stundenvergleiche dürfen nicht aus dieser
bisherigen Ein-Zellen-Ansicht berechnet werden. Generator-Monatsimport bleibt
von diesem konkreten Verlust unberührt; keine Erklärung des fehlenden
Original-600s-Jobs daraus ableiten. Nächster gezielter Prüfpunkt sind
Normaldienst plus Sonderdienst/Abwesenheit und die bestehenden Override-Tests,
bevor ein kompatibler gemeinsamer Änderungskandidat entsteht.

### Teiltagsabwesenheit verdeckt Dienst und verliert Zeitfenster

Weitere vier synthetische Fälle in `audit_upstream_schedule_views.py`
(INTERVAL 0/1/2/3), 40 zusätzliche Assertions, belegen: Der Monatsweg
behält den normalen Ist-Dienst neben der Abwesenheit und liefert deren
Intervall einschließlich START/END bei stundenweiser Abwesenheit.
`database.py:get_schedule_day/get_schedule_week` überschreiben hingegen
in der ABSEN-Schleife den kompletten Personeneintrag, setzen `shift_id=None`
und reichen weder `interval` noch `start_time/end_time` weiter. Auch eine
synthetische einstündige Abwesenheit verdeckt damit den ganzen Dienst.
OSP5 `Wochenansicht.tsx:buildStats` zählt anschließend Abwesenheit statt Dienst.
Das ist ein nachgewiesener Informationsverlust der Ansicht, **kein Beweis,
dass Arbeitszeit fachlich entfällt**. Der Generator-Monatsweg ist hiervon
nicht betroffen; daraus folgt keine Ursache des fehlenden 0.9.29-Originaljobs.

Vorhandener Librarytest `test_schedule_read_paths_expand_cycles` sichert
Zyklus-/Materialisierungspriorität und freie Tage, aber nicht diese
Teiltagskonstellation. Ein gemeinsamer Korrekturkandidat muss daher neben
Planselektion und Mehrfachdiensten auch Abwesenheitszeitfenster transportieren
und Anzeigepriorität von Zeitberechnung trennen. Sonderdienst-Kombinationen
bleiben als nächster Prüfpunkt offen; nicht pauschal alle Overrides entfernen.
Zusätzlich unveränderte Generator-Grenzregression geprüft:
`tests/test_partial_limits.py`: **88 passed**. Kein Runtimefix oder Release.

### Sonderdienstvertrag: Anzeige, Rohdaten und wirksame Arbeit trennen

Zwölf weitere synthetische Kombinationen in
`tools/audit_upstream_schedule_views.py` (TYPE 0/1, SHIFTID 0/5,
Einzeleintrag und zwei umgekehrt geordnete Sonderdienste), **156 zusätzliche
Assertions bestanden**: Tages-/Wochenweg zeigt ausschließlich den letzten
Sonderdienst samt dessen Zeitdetail, auch bei SHIFTID=0. Monatsweg erhält
normalen Dienst und sämtliche Sonderdienste, lässt aber STARTEND/DURATION
im Sonderdiensteintrag weg. Insgesamt 236 Auditassertions bestanden.

Das ist **nicht** gleichbedeutend mit additiver wirksamer Arbeitszeit:
`sp5lib/calculations.py:_replaced_days` bestimmt Ersetzung über gesetzte
SHIFTID, unabhängig von TYPE. Der bestehende Librarytest
`test_special_shift_replaces_duty` belegt sechs statt vierzehn Stunden.
Generator `sp5_adapter.py:_scope_schedule` ergänzt Sonderdienstzeiten aus
`get_spshi_entries_for_day` nur bei eindeutiger Zuordnung. `import_snapshot`
normalisiert anschließend ersetzte Ist-Dienste personentagweit und erhält
Soll-Referenzen getrennt. Der Regressionstest
`test_reference_selection_never_switches_context_absences_or_special_duties`
sichert diesen Unterschied und blockiert unbekannte Ersatzzeiten.
**75 Adaptertests bestanden**, unveränderte Runtime.

Damit ist der Vertrag für den nächsten zusammenhängenden Kandidaten eingegrenzt:

1. Explizite Planselektion für normale Dienste durch Library → API → OSP5;
   SPSHI.TYPE niemals als Ist/Soll-Flag interpretieren.
2. Verlustfreie Eintragslisten mit Herkunft, stabiler Identität und Zeitdetails;
   freie Personentage weiterhin darstellbar. OSP5 darf Listen nicht wieder in
   ein einzelnes Person/Datum-Element zusammenfalten.
3. Rohdaten-/Anzeigeeinträge von wirksamer Arbeitszeit unterscheiden:
   Ersetzung mit SHIFTID erhalten, eigenständige Sonderdienste und Abwesenheits-
   fenster nicht durch pauschales Override verbergen oder pauschal addieren.
4. Generatorweitergabe nur nach eindeutiger Zeit-/Quellzuordnung; fehlende
   Details weiter blockieren, keine Freigaben oder Stundenlimits ableiten.

Die Quellansichten taugen damit ohne Normalisierung nicht als unabhängiger
Stundenvalidator. Der fehlende Original-600s-Job bleibt eine getrennte
Reproduktionslücke; keiner dieser Ansichtsbefunde beweist seine Ursache.
Keine produktiven Änderungen oder neue Releasefreigabe aus diesem Audit.

### Zusammenhängender isolierter Kandidat: explizite, verlustfreie Quellansicht

Die Charakterisierung ist jetzt in einen **ausführbaren Library/API/OSP5-
Kandidaten** umgesetzt, nicht nur in weitere Einzelbefunde. Drei Patches
gegen die am Dokumentanfang genannten Originalrevisionen:

- `tools/upstream-entries-library-candidate.patch`: enthält den bisherigen
  Ist-Abrechnungs-/Zyklusfilterkandidaten **bereits**; nicht zusätzlich auf
  `upstream-ist-accounting-candidate.patch` anwenden. `get_schedule` ergänzt
  auf explizites `source_details=True` Herkunft und direkt gelesene Zeitdetails.
  `get_schedule_entries(..., plan=..., week=...)` verwendet diese bestehende
  Monatsfassade für eine verlustfreie Tages-/Wochenstruktur einschließlich
  Monats-/Jahreswechsel und freier Personentage. Normale ersetzte Ist-Dienste
  bleiben als `replaced_in_ist=True` nachvollziehbar; Soll wird nicht ersetzt.
- `tools/upstream-entries-api-candidate.patch`: Tages-/Wochenendpunkte verwenden
  die neue Struktur **nur mit explizitem `plan=ist|soll|both`**; ungültige
  Plansicht ergibt 400. Personen-Scope und bestehende Abwesenheitssichtbarkeit
  werden auf die neue Struktur angewendet. Ohne Planparameter bleibt der alte
  Vertrag unverändert, einschließlich seiner dokumentierten Informationsverluste.
- `tools/upstream-entries-osp5-candidate.patch`: `client.ts` gibt die explizite
  Auswahl weiter; `Wochenansicht.tsx` gruppiert Einträge in Listen statt
  `Map<employee_id, entry>`, zeigt Plansicht, Sonderdienstzeiten,
  Ersatzkennzeichen und Teilabwesenheitsfenster. Die Zählung heißt ausdrücklich
  **Einträge**, nicht Arbeitsstundensumme. Eine alte API ohne den neuen
  `entry_semantics`-/Plan-Nachweis wird abgelehnt; verspätete Antworten einer
  vorherigen Plansicht überschreiben die aktuelle Auswahl nicht.

Der Kandidat wurde ausschließlich unter `/tmp/sp5-entries-candidate` ausgeführt.
Originalcheckouts, Generator-Runtime, produktive API und Benutzerinstallation
bleiben unverändert. Vorhandene Library-/Monatsfassade, Sichtbarkeitsfunktion,
OSP5-Komponenten und ISO-Wochenfunktion wurden wiederverwendet; keine neue
Zeitberechnungsbibliothek oder Frameworkmigration.

**Gezielter zusätzlicher Browserbefund:** In der ursprünglichen
`Wochenansicht.tsx` konvertiert `toISODate` lokale Mitternacht mit
`toISOString().slice(0, 10)` nach UTC. Die Auswahl **01.01.2027** sendete im
Chromium mit `Europe/Vienna` tatsächlich `date=2026-12-27`, statt des lokalen
ISO-Montags `2026-12-28`. `get_schedule_week` würde den Sonntag der Vorwoche
zuordnen. Die Kandidatenkorrektur formatiert lokale Datumskomponenten und
verwendet `utils/isoWeek.ts:getISOWeek` auch für die KW-Beschriftung.
Browser-Gegenproben prüfen Jahreswechsel und den DST-Wechsel 25./26.10.2026.
Dies betrifft den OSP5-Vergleichspfad, **nicht nachgewiesenermaßen den
Generator-Originaljob**.

#### Nachweise und reproduzierbare Prüfungen

Alle Prüfdaten sind synthetisch. Patches mit `git apply --check` gegen alle drei
Originalcheckouts geprüft, ausschließlich auf isolierte Kopien angewendet.

```sh
# In einer Kopie der Original-Library (nicht zusätzlich den früheren Patch anwenden):
git apply /path/to/generator/tools/upstream-entries-library-candidate.patch
# Entsprechend API- und OSP5-Patch jeweils in deren isolierter Kopie anwenden.

# Im Generatorcheckout mit bestehender Testumgebung:
SP5_ENTRIES_ROUTER=/tmp/sp5-entries-candidate/schedule.py \
PYTHONPATH=/tmp/sp5-entries-candidate .venv/bin/python -m pytest \
  tools/test_upstream_entries_candidate.py -q
PYTHONPATH=/tmp/sp5-entries-candidate .venv/bin/python -m pytest \
  /home/hilbert/projects/libopenschichtplaner5/tests -q

# In der isolierten OSP5-Frontendkopie:
./node_modules/.bin/vitest run src/utils/scheduleEntries.test.ts \
  src/pages/Wochenansicht.entries.test.tsx
./node_modules/.bin/tsc -b --pretty false
```

- **18 neue Python-Vertragstests bestanden**, einschließlich echter
  FastAPI-Queryvalidierung via lokalem TestClient, beider Endpunkte, leerem
  Personen-Scope, Gruppenfilter, drei Abwesenheitsmodi, Quellreihenfolge,
  fehlender Sonderdienstzeit, Zyklus/Soll, alten Antwortverträgen und Jahreswechsel.
  Routerfunktionen werden unverändert per AST ohne globalen Serverstart geladen;
  dies ist **keine** vollständige API-Authentifizierungs-/Endpoint-Abnahme.
- **297 bestehende Librarytests bestanden, 6 übersprungen**.
- **6 neue OSP5-Tests bestanden**, einschließlich tatsächlichem React-Rendering,
  Plansichtwechsel, Ablehnung alter API-Antworten, verspäteter alter Antwort
  sowie korrekter KW 1 für 04.–10.01.2027. TypeScript-Build und gezieltes ESLint
  der neuen Test-/Hilfsdateien bestanden.
- `tools/audit_upstream_entries_browser.cjs` prüft die echte Wochenkomponente
  mit Chromium **1280px und 390px**, `Europe/Vienna`. Eingaben sind aus den
  obigen lokalen ASGI-Testantworten exportierte synthetische Ist-/Soll-/Both-
  Fixtures, ausschließlich am Loopback-Vite-Server abgefangen. Es prüft
  Mehrfacheinträge, Ersatz-/Zeitdetails, Auswahl und Datumsnavigation; kein
  Login, keine produktiven HTTP-Aufrufe, kein vollständiger OSP5-App-Test.

Browserreproduktion im isolierten Frontend: eine `entries-audit.html` mit
`<div id="root"></div>` und Moduleinstieg `entries-audit.tsx` anlegen; dieser
importiert React, `createRoot`, `./src/pages/Wochenansicht` und `./src/index.css`
und rendert nur die Wochenkomponente. Fixtures können ohne DBF-Zugriff aus
`tools.test_upstream_entries_candidate` mit `source.__wrapped__()` und
`client.__wrapped__(source.__wrapped__())` exportiert werden: je Plansicht die
lokale Antwort von `/week?date=2026-09-07&plan=...` als JSON-Objekt
`{ist: ..., soll: ..., both: ...}` speichern. Mit Vite auf
`127.0.0.1:5189 --strictPort` ausführen:

```sh
node tools/audit_upstream_entries_browser.cjs \
  /tmp/sp5-entries-candidate/frontend \
  /tmp/sp5-entries-candidate/synthetic-http-responses.json
```

#### Bewusst verbleibende Integrationsgrenzen

1. Die neue Struktur ist eine **Quellansicht**, kein unabhängiger Arbeitszeit-
   validator. `duration` sind Quell-/bezahlte Stunden, `startend` Quellzeiten;
   nicht pauschal addieren. Zeitfenster und Ersetzungskennzeichen ersetzen keine
   vollständige Arbeitszeitnormalisierung oder bestätigte Regeln/Freigaben.
2. `source_table/source_id` gibt vorhandene DBF-Herkunft wieder; fehlende IDs
   und expandierte Zyklusdienste erhalten ausdrücklich **keine erfundene stabile
   Datensatzidentität**. Der Kandidat unterstützt keine Schreib-/Undo-Aktionen.
3. Nur die Wochenansicht ist als OSP5-Aufrufer migriert. Einsatzplan,
   DienstBoard und Teamübersicht verwenden weiter den alten Vertrag. Keine
   pauschale Korrektur aller Quellansichten behaupten.
4. API-Arbeitszeitprüfung bleibt ein separater Pfad: Der ältere Ist-only-
   Stundenkandidat ist noch kein öffentlich durchgängiger Plansichtvertrag.
   Nullruhe/Überlappung, reale statt bezahlte Stunden und Randkontext bleiben
   dort offene fachliche Unterschiede zum Generatorvalidator.
5. Keine Generator-Runtimeänderung, kein Release und keine neue reale
   Planungsabnahme. Die unveränderte 0.9.31 wurde nicht redundant gegen die
   echte API geprüft. Der exakte 0.9.29-600s-Eingang und sein Ergebnis fehlen
   weiterhin; dieser Kandidat beweist nicht die Ursache dieses Laufs.

Nächster zusammenhängender Schritt: expliziten Ist-/Soll-Vertrag des separaten
API-Arbeitszeitprüfers mit OSP5 `WorkTimeRules.tsx` und den belegten realen
Zeit-/Überlappungsgrenzen verbinden. Den Quellansichtskandidaten bis zur
vollständigen API-/Aufruferabnahme isoliert lassen; keine neue UI-/Release-Serie.

### Isolierter API-Ruhe-Korrekturkandidat: verschachtelte Dienste

`tools/upstream-api-rest-candidate.patch` korrigiert ausschließlich den
Intervallvergleich in `_check_employee`; `tools/upstream-osp5-rest-candidate.patch`
ergänzt die deutsche Bezeichnung des neuen Diagnosecodes in `WorkTimeRules.tsx`.
Keine Originalcheckouts, Generatorruntime oder produktiven Regeln geändert.

**Zusätzlicher reproduzierter Fehler:** Ein einfacher Nachbarvergleich reicht
nicht. Bei Intervallen Montag 08:00–Dienstag 08:00, Montag 10:00–12:00 und
Dienstag 00:00–04:00 erkennt das Original den zweiten Konflikt nicht: Es
vergleicht mit dem bereits beendeten kurzen statt dem noch laufenden langen
Dienst. Der Kandidat behält das maximale bisherige Dienstende. Negative
Abstände werden `shift_overlap` (auch bei Mindestruhe null), Nullabstände bei
positiver Mindestruhe werden Ruheverletzungen. Exakt erreichte Mindestruhe
bleibt zulässig. Ein einzelner 24h-Dienst wird durch diesen Vergleich nicht
verboten. Tages-/Wochenhöchstgrenzen sind eine separate Prüfung.

`shift_overlap.value` ist der Abstand des aktuellen Beginns zum noch offenen
vorherigen Ende in Stunden, **nicht** die Schnittmengendauer oder aufsummierte
Überlappungszeit. Der Kandidat meldet einen Konflikt je betroffenem aktuellen
Block, keine vollständige Liste aller kollidierenden Paare.

Reproduktion mit Original-Library (keine DBF-/HTTP-Zugriffe):

```sh
cp /home/hilbert/projects/openschichtplaner5-api/sp5api/routers/work_time_rules.py /tmp/sp5-rest-candidate.py
# Patch in einer isolierten API-Kopie mit gleicher Verzeichnisstruktur anwenden;
# SP5_REST_ROUTER anschließend auf deren work_time_rules.py setzen.
PYTHONPATH=/home/hilbert/projects/libopenschichtplaner5 SP5_REST_ROUTER=/tmp/sp5-rest-candidate.py .venv/bin/python -m pytest -q tools/test_upstream_rest_candidate.py
```

Die obige unveränderte Kopie liefert zunächst **5 fehlgeschlagene, 5 bestandene**
Tests; mit angewandtem Kandidaten **10 bestanden**. Zusätzlich bestehen die
**18 bestehenden synthetischen Quellkombinationen (72 Assertions)** und
**8 unveränderten Upstream-Helfertests** via `audit_upstream_work_time_plan.py`
ohne `--candidate` (Plansichtfilter absichtlich unverändert). Generator:
**115 Tests** in `test_partial_limits.py` und `test_calendar_limits.py` bestanden.
Ruff und `git apply --check` gegen beide Originalrepos bestanden.

**Kein vollständiger API-Fix:** Die Blöcke sind weiterhin Spannweiten über
Quellfenster; Plansichtvermischung, bezahlte statt reale Tages-/Wochenstunden,
fehlender Randkontext, fehlende Zeitangaben und Zeitzonen bleiben offen.
Die neue Bezeichnung ist keine vollständige Browser-/Endpointabnahme.
Vor Integration sind diese Änderungen mit dem expliziten Plansichtvertrag
zu verbinden. Insbesondere darf die OSP5-Meldung „Keine Verstöße gefunden“
weiterhin nicht als unabhängiges Gütesiegel für Generatorpläne gelten.
Der Kandidat belegt keine Ursache des nicht vorliegenden 0.9.29-600s-Jobs.

### API-Stundenprüfung: reproduzierte Kalender- und Vollständigkeitsgrenzen

`tools/test_upstream_work_time_boundaries.py` charakterisiert den **ungeänderten**
API-Prüfer mit sieben synthetischen Tests. Grüne Tests dokumentieren hier die
Abweichungen, nicht deren Behebung. Vier Fälle stellen dem API-Ergebnis direkt
den unabhängigen Generatorvalidator gegenüber; die übrigen vergleichen den
vollen und verkürzten API-Prüfzeitraum beziehungsweise fehlende Quellzeiten.

| Synthetischer Fall | Original-API | Gegenbefund |
| --- | --- | --- |
| 08–08 Uhr, 24 reale, 8 bezahlte Stunden, Tageslimit 10h | Keine Verletzung | Generator meldet Tageslimit: 16h am ersten, 8h am zweiten Tag. |
| Derselbe Dienst, Wochenlimit 10h | Keine Verletzung | Generator meldet Wochenlimit wegen 24 realen Stunden. |
| 12–12 Uhr, 24 bezahlte Stunden, Tageslimit 12h | 24h am Starttag beanstandet | Generator akzeptiert 12h je Kalendertag. |
| Sonntag 11.01.2026 20 Uhr bis Montag 08 Uhr, Wochenlimit 6h | 12h in Woche ab 05.01. beanstandet | Generator beanstandet Woche ab 12.01.: dort 8h, vorherige Woche nur 4h. |
| Montag und Mittwoch je 8h, Wochenlimit 12h | Voller Zeitraum meldet 16h; nur Mittwoch meldet nichts | Identische Quelldaten, aber keine Ergänzung der restlichen Kalenderwoche. |
| Montag Ende 23 Uhr, Dienstag Beginn 08 Uhr, Mindestruhe 11h | Voller Zeitraum meldet 9h; nur Dienstag meldet nichts | Vorgängerdienst wird am Abfrageanfang ausgefiltert. |
| Normaldienst mit DURATION=24, ohne STARTEND | 0 Stunden, kein Block, keine Verletzung | Fehlende Arbeitszeiten werden nicht als unvollständige Prüfung ausgewiesen. |

Alle Grenzen sind ausschließlich synthetische Testkonfiguration, **keine neuen
Nutzerdefaults**. Ein 24h-Dienst ist nicht allein wegen 11h/36h Ruhe verboten.
Die fehlenden Zeitangaben im letzten Fall erlauben gerade **keinen** Schluss
auf 24 reale Arbeitsstunden.

**Zusammenhängender Codepfad:** Library
`sp5lib/calculations.py:shift_hours_on_day` liefert DURATION bei vorhandenem
STARTEND, nicht verstrichene Dauer. API
`sp5api/routers/work_time_rules.py:_employee_plan._dated` begrenzt bereits
Quellzeilen auf `from_date..to_date`; `_collect_day_data` bucht diese Stunden
vollständig auf das Startdatum. `_check_employee` gruppiert diese Startdaten
nach ISO-Woche, ohne den Randkontext nachzuladen. Die ISO-Wochennummer an sich
ist dabei korrekt, die Stundenverteilung nicht gleichwertig zum Generator.
OSP5 `frontend/src/pages/WorkTimeRules.tsx` zeigt für leere Ergebnisse weiterhin
„Keine Verstöße gefunden“ bzw. den Gruppen-Entsprechungstext; eine getrennte
Vollständigkeitsinformation liefert dieser Pfad nicht. Generator
`sp5generator/validator.py:_validate` prüft dagegen reale lokale Kalenderanteile;
`solver.py` setzt konfigurierte `max_daily_minutes/max_weekly_minutes` hart um.
Die vorhandenen Teilplan-/Kalenderregressionen prüfen diese Solvergrenzen mit.

```sh
PYTHONPATH=/home/hilbert/projects/libopenschichtplaner5:tests SP5_WORK_TIME_ROUTER=/home/hilbert/projects/openschichtplaner5-api/sp5api/routers/work_time_rules.py .venv/bin/python -m pytest -q tools/test_upstream_work_time_boundaries.py tests/test_partial_limits.py tests/test_calendar_limits.py
```

Ergebnis: **122 bestanden** (7 neue Charakterisierungen, 115 vorhandene
Generatorregressionen), Ruff bestanden. Keine HTTP-/Browserabnahme und keine
Änderung von Originalcheckouts, Generatorruntime oder laufender Installation.
Unveränderte 0.9.31 nicht redundant real getestet; kein Release.

**Korrekturreihenfolge konkretisiert:** Der explizite Ist/Soll-Vertrag allein
reicht nicht als Gesamtfix. Vor einer positiven Arbeitszeitaussage benötigt der
API-Prüfer (1) sichtgetreue effektive Dienste, (2) reale Zeitsegmente getrennt von
Abrechnung, (3) Kalender-/Zeitzonenaufteilung und ausreichenden Randkontext,
(4) explizite Unvollständigkeit bei fehlenden Zeiten/Kontext. Danach vorhandenen
Überlappungskandidaten und OSP5-Ergebnisvertrag zusammenführen. Nicht einfach
alle Quellfenster addieren: Sonderersatz und Abwesenheiten bleiben zu beachten.
Diese Gegenproben grenzen die API als unabhängige Prüfinstanz ein; sie beweisen
weiterhin nicht die Ursache des fehlenden Original-0.9.29-Projekts/Jobs/Ergebnisses.

### Wochenmodell: Sollwert ersetzt API-Festgrenze, fehlendes Soll überspringt Prüfung

Sechs weitere synthetische Fälle in `tools/test_upstream_week_model.py` verfolgen
den Vertrag vom Library-Modell bis zum API-Prüfer. Die OSP5-Auswahl
`WorkTimeRules.tsx` setzt `week_limit_mode=model` und `week_limit_factor`; ihre
Beschriftung „Vertrags-Wochenstunden“ ist zu eng: Die API ruft tatsächlich
`calc.get_nominal_hours` für Montag bis Sonntag auf, nicht einfach `HRSWEEK`.

* `CALCBASE=1`, `HRSWEEK=40`: acht Stunden sind im Modellmodus zulässig, auch
  wenn `max_hours_per_week=6` gesetzt ist. Im Festmodus werden dieselben acht
  Stunden beanstandet. Das sind alternative Prüfmodi, **keine kombinierten Caps**.
* `CALCBASE=2`, `HRSMONTH=160`, `HRSDAY=1`, fünf Arbeitstage: Für die vollständige
  Woche 05.–11.01.2026 liefert `_nominal_month` fünf Sollstunden, nicht 40 aus
  `HRSWEEK`, nicht 160 und nicht eine pauschale Monatsdivision. Acht Stunden
  überschreiten deshalb die im API-Modellmodus berechnete Fünfstundengrenze.
* Leerer Mitarbeiterdatensatz, Monatsmodell mit `HRSDAY=0` oder Gesamtmodell
  ohne geschlossenen Beschäftigungszeitraum: Das berechnete Soll ist null.
  `_check_employee` überspringt die Wochenprüfung mit `continue`; die Original-API
  meldet trotz acht Stunden und gesetztem Festwert sechs keine Auffälligkeit.
  Bei leerem Datensatz sind dabei fehlende Angaben, nicht tatsächliche Nullstunden
  belegt. Auch ein fachlich beabsichtigtes Null-Soll ist keine Prüffreigabe.

**Begrenzte Korrektur implementiert:**
`tools/upstream-api-week-model-candidate.patch` ersetzt ausschließlich dieses
stille Überspringen durch `weekly_model_unresolved` (Warnung, keine behauptete
Arbeitszeitverletzung). `value` enthält den berechneten nichtpositiven Grenzwert,
`limit=0` beschreibt die fehlende positive Prüfvoraussetzung; beide sind hier
**keine gemessenen Arbeitsstunden**. Es wird weder die Festgrenze als Fallback
eingeführt noch eine neue Wochenhöchstgrenze erfunden. Der passende isolierte
OSP5-Patch benennt die Kategorie „Wochenprüfung unvollständig: Sollmodell prüfen“.
Damit ist die Warnung im bestehenden Ergebnisvertrag darstellbar. Kein umfassender
Vollständigkeitsvertrag: Wochen ohne erfasste Tagesdaten, fehlende Quellzeiten,
Plansichtvermischung und Randkontext bleiben durch diesen kleinen Kandidaten
ausdrücklich ungelöst. Keine vollständige HTTP-/Browserabnahme dieses Kandidaten.

**Abgrenzung Generator:** `api_adapter.py` nutzt `sp5_adapter.import_snapshot`.
Dieser übernimmt Sollwerte über `get_nominal_hours` als Planungsziel, erzeugt aber
ein unbestätigtes Regelprofil mit den autorisierten 660/2160 Minuten Ruhe, ohne
aus Sollstunden ein Wochenmaximum zu erfinden. `RuleProfile.max_weekly_minutes`
ist standardmäßig `None`; konfigurierte Werte prüft der Generator unabhängig.
Die separate API-Modusauswahl ist kein importierter persönlicher Grenzwert.
Ob der Original-600s-Job ein Wochenmaximum hatte, bleibt ohne seine Eingabe offen.

**Reproduktion und Nachweis:**

```sh
# Originalverhalten charakterisieren: sechs bestanden.
PYTHONPATH=/home/hilbert/projects/libopenschichtplaner5:tests SP5_WORK_TIME_ROUTER=/home/hilbert/projects/openschichtplaner5-api/sp5api/routers/work_time_rules.py .venv/bin/python -m pytest -q tools/test_upstream_week_model.py
# An einer isolierten API-Kopie den API-Wochenmodellpatch anwenden; danach:
PYTHONPATH=/home/hilbert/projects/libopenschichtplaner5:tests SP5_WORK_TIME_ROUTER=/tmp/sp5-week-model-candidate/work_time_rules.py SP5_WEEK_MODEL_CANDIDATE=1 .venv/bin/python -m pytest -q tools/test_upstream_week_model.py tools/test_upstream_work_time_boundaries.py tests/test_partial_limits.py tests/test_calendar_limits.py
```

Korrekturvertrag gegen Original: gezielt **3 fehlgeschlagen, 3 bestanden**;
gegen Kandidat einschließlich Kalender-/Teilplanregressionen **128 bestanden**.
Ruff und Patchanwendbarkeit gegen beide Originalrepos bestanden. Keine Änderung
an Originalcheckouts, Generatorruntime oder Installation; kein neues Release und
kein redundanter Realdatentest der unveränderten 0.9.31.

### API-Zeitzonenprüfung: synthetisch belegte Fehlklassifikationen

`tools/test_upstream_timezone.py` ergänzt vier Charakterisierungen des
**unveränderten** API-Prüfers. Datenfluss: `MASHI.DATE` und
`SHIFT.STARTEND[Wochentag]` → Library `parse_startend` (Uhrzeitminuten) → API
`_collect_day_data._add_block` (`datetime.combine` ohne Zeitzone) →
`_check_employee` (naive Subtraktion). Damit fehlt hier eine explizite
Zeitzone; es erfolgt keine UTC-basierte Messung realer Ruhezeit.

Für die ausdrücklich gewählte synthetische Zone Europe/Vienna belegt:

- 28.03.2026 23:00 bis 29.03.2026 10:00: real 10 Stunden, API 11 Stunden;
  die konfigurierte 11-Stunden-Ruheverletzung fehlt.
- 24.10.2026 23:00 bis 25.10.2026 09:00: real 11 Stunden, API 10 Stunden;
  die API meldet eine nicht vorliegende Ruheverletzung.
- Dienstbeginn 29.03.2026 02:30 (nicht existent) bzw. 25.10.2026 02:30
  (mehrdeutig): API erzeugt kommentarlos naive Blöcke und keine Diagnose.
  Generator `timeutils.localize` weist beide ohne eindeutige Auflösung zurück;
  `minute` misst die aufgelösten Endpunkte in UTC.

Die OSP5-Anzeige kann diese vom API-Prüfer fehlenden/falschen Verstöße nicht
als unabhängige Bestätigung einer Planung verwenden. Das ist weder ein
Nachweis für den konkreten 600-Sekunden-Job noch ein angewendeter API-Fix.
Ein zusammenhängender Korrekturvertrag muss die explizite Plansicht,
effektive Zeitsegmente, lokale Kalendertage/ISO-Wochen, UTC-Dauern und einen
Unvollständigkeitsstatus verbinden. Fehlende Zone bzw. Herbst-Fold dürfen
nicht stillschweigend geraten werden. Produktionsregeln bleiben unverändert.

Reproduktion (nur synthetische Daten, aus Generator-Checkout):

```sh
SP5_WORK_TIME_ROUTER=../openschichtplaner5-api/sp5api/routers/work_time_rules.py \
PYTHONPATH=.:tests:../libopenschichtplaner5 .venv/bin/pytest -q \
  tools/test_upstream_timezone.py tests/test_partial_limits.py \
  tests/test_calendar_limits.py tests/test_spill_rest.py
```

Ergebnis: **136 passed**, davon vier neue API-Zeitzonenfälle. Keine
Server-/HTTP-Abnahme und keine Runtimeänderung.

### Konsolidierter Arbeitszeit-Prüfvertrag: API → OSP5, ausdrücklich unvollständig

`tools/upstream-api-worktime-contract-candidate.patch` und
`tools/upstream-osp5-worktime-contract-candidate.patch` verbinden die früheren
Ist-, Überlappungs- und Wochenmodellkandidaten in **einem isolierten Vertrag**.
Sie gelten gegen die unveränderten Originalcheckouts. Die früheren Einzelpatches
nicht zusätzlich anwenden. Keine Produktionsinstallation oder Generatorruntime
ist damit geändert; dies ist kein freigegebener vollständiger Arbeitszeitprüfer.

Datenfluss und abgegrenzte Semantik:

1. OSP5 `WorkTimeRules.limitParams` sendet ausdrücklich `plan=ist|soll` über
   `api/client.ts` / `workTimeCheckQuery` an beide bestehenden Prüfendpunkte.
   Ohne bewusste Grenzüberschreibung werden keine neuen Stundenlimits gesendet.
2. API `check_employee` / `check_all` validieren die Alternative mit `Literal`;
   `both` ist kein addierbarer Arbeitsplan und wird mit HTTP 422 zurückgewiesen.
   Beschäftigten-/Gruppen-/Sichtbarkeitsfilter bleiben erhalten.
3. `_check_employee` → `_collect_day_data` → `_employee_plan`: Auswahl erfolgt
   **vor** der Verdrängung des Library-Zyklus durch materialisierte MASHI-Tage.
   Ist enthält MASHI außerhalb TYPE 1 und gegebenenfalls CYASS-Expansion sowie
   SPSHI; Soll enthält die gespeicherten MASHI-TYPE-1-Dienste, keinen erfundenen
   Soll-Zyklus und keine SPSHI-Istarbeit. SPSHI.TYPE ist nicht MASHI.TYPE.
   Diese Quellenentscheidung entspricht den zuvor belegten Library-Sichten;
   sie macht Quelleneinträge ausdrücklich noch nicht zu effektiven Arbeitssegmenten.
4. Vorhandene Überlappungs-/Nullruhekorrektur und `weekly_model_unresolved`
   laufen auf **derselben** gewählten Sicht. Sollmodell und Festgrenze bleiben
   alternative API-Prüfmodi; keine neue Generator-Wochenhöchstgrenze entsteht.
5. `_build_check_result` ergänzt `coverage` mit Vertragskennung, Plansicht,
   Zeitraum und `complete=false`. Gründe kennzeichnen bekannte Fähigkeitenlücken,
   nicht neue Mitarbeiterverstöße: bezahlte statt reale Stunden, fehlende
   Kalenderaufteilung, ungelöste Zeitzone, nicht geladener Randkontext und
   ungeklärte effektive Segmente. Abgeschaltete Regeln und fehlendes positives
   Wochenmodell werden zusätzlich benannt. Auch eine leere Beschäftigtenmenge
   oder null Auffälligkeiten ergeben **keinen** Vollständigkeitsnachweis.
6. OSP5 akzeptiert nur Antworten, die Vertrag, Sicht und Zeitraum bestätigen.
   Eine alte API ohne Metadaten wird nicht stillschweigend als ausgewählte Sicht
   ausgegeben. Sichtwechsel löscht beide bisherigen Ergebnisse; Perioden- und
   Beschäftigten-/Gruppenwechsel löschen das betroffene Ergebnis. Während eines
   Aufrufs sind dessen Scopefelder und die gemeinsame Plansicht gesperrt.
   Null Auffälligkeiten wird ohne grünes Prüfsiegel als begrenzte Diagnose gezeigt.

Kompatibilitätsgrenze: API-Aufrufer ohne `plan` behalten die alte gemischte
Quellenauswahl (`coverage.plan=legacy_mixed`), **nicht** die fehlerhafte
Überlappungs-/Nullmodellbehandlung. OSP5 verwendet diesen Legacy-Modus nicht.
Die neue OSP5-Prüfseite benötigt den neuen API-Vertrag; sie behauptet bei einem
alten Backend keine erfolgreiche Prüfung. Die bekannten Stunden-/Zeitzonenfehler
bleiben ausdrücklich offen. Die reine Quellansicht aus dem früheren
Library/API/OSP5-Kandidaten ist keine Ersatzimplementierung dieser Zeitmessung.

Reproduktion in isolierten Kopien (keine echten API-Aufrufe):

```sh
# Original-API kopieren und nur upstream-api-worktime-contract-candidate.patch anwenden.
SP5_WORK_TIME_ROUTER=/tmp/sp5-worktime-contract/sp5api/routers/work_time_rules.py \
SP5_REST_ROUTER=/tmp/sp5-worktime-contract/sp5api/routers/work_time_rules.py \
SP5_WEEK_MODEL_CANDIDATE=1 PYTHONPATH=.:tests:../libopenschichtplaner5 \
.venv/bin/pytest -q tools/test_upstream_worktime_contract.py \
  tools/test_upstream_week_model.py tools/test_upstream_rest_candidate.py \
  tests/test_partial_limits.py tests/test_calendar_limits.py tests/test_spill_rest.py
# OSP5 kopieren, nur upstream-osp5-worktime-contract-candidate.patch anwenden.
# tools/upstream-worktime-contract.test.tsx nach frontend/src/__tests__/ kopieren.
# Dort: vitest run src/__tests__/upstream-worktime-contract.test.tsx; tsc -b
```

Nachweis: **162 Python-Tests**, darunter 14 neue synthetische ASGI-Verträge;
**7 neue Frontend-Komponententests**, TypeScript-Buildprüfung, gezieltes ESLint,
Ruff und Anwendbarkeit beider Gesamtpatches. ASGI-Harness extrahiert die echten
Routerfunktionen mit Dependency-Stubs: kein vollständiger API-Start/Auth-Test.
Frontend verwendet synthetische API-Mocks: kein vollständiger Browser-/Login-
oder gemeinsamer Serverabnahmetest. Initiale Testaufrufe hatten einen fehlenden
Resttest-Umgebungsparameter bzw. falschen Testselektor/Matcher; korrigierte
Aufrufe sind maßgeblich, keine Produktfehler daraus abgeleitet.

Nächster zusammenhängender Korrekturschritt bleibt die effektive Arbeitszeit:
Quellansicht → tatsächliche Segmente unter Sonderdiensten/Abwesenheiten → explizite
Zone/Fold → UTC-Dauer → lokale Tages-/ISO-Wochenteilung mit Randkontext. Erst
nach belegter Umsetzung dürfen entsprechende Unvollständigkeitsgründe entfallen.
Der fehlende Original-0.9.29-600s-Job ist weiterhin nicht reproduziert. Unveränderte
veröffentlichte 0.9.31 nicht erneut ohne neue Laufzeitänderung realgetestet.

### Effektive Segmente: vorhandene Zuschlagsfunktion nicht als Prüforakel verwenden

Weitere acht synthetische Charakterisierungen in
`tools/test_upstream_effective_segments.py` grenzen den nächsten Korrekturschritt ab:

- Library `calculations.daily_work_intervals` ist laut Implementierung ein
  **Anrechnungs-Schnitt für Zuschläge**, kein vollständiger Arbeitszeitnachweis.
  Sie entfernt `SHIFT.NOEXTRA`, bei ersetzendem SPSHI das NOEXTRA der referenzierten
  Schicht und bei additivem SPSHI dessen eigenes NOEXTRA. In allen drei Tests
  verbleiben acht Stunden in `get_work_hours`, während die Intervallliste leer
  ist. Eine ungeprüfte Wiederverwendung würde reale Dienste verschwinden lassen.
  Bestehende Library-Tests `test_calculations.py` und
  `test_facade_write_roundtrip.py` behandeln NOEXTRA bereits als Zuschlagsoption.
- API `work_time_rules._collect_day_data._add_block` verdichtet mehrere
  STARTEND-Fenster zu einer Hülle: 08–12 und 16–20 werden 08–20. Acht bezahlte
  Stunden, acht lokale Segmentstunden und zwölf Stunden Dienstspanne sind hier
  drei getrennte Größen. Der Ersatz von DURATION durch Hüllendauer wäre deshalb
  **keine korrekte Reparatur** der belegten 24h/8h-Lücke. Die Library erhält die
  beiden Fenster, jedoch mit der oben beschriebenen Zuschlagsfilterung.
- Die API-Hilfsfunktion liest ABSEN überhaupt nicht: ganztägige, vormittägliche,
  nachmittägliche und stundenweise Einträge ändern dieselbe Dienstliste nicht.
  Library `database.get_schedule` liefert Dienst und Abwesenheit nebeneinander;
  OSP5 `Schedule.tsx` verarbeitet diese als getrennte Eintragsarten. Generator
  `sp5_adapter.import_snapshot` verwendet Abwesenheiten als Verfügbarkeitssperren
  und getrennte Herkunft/Anrechnung (siehe oben). Daraus folgt weder, dass ein
  bestehender Ist-Dienst tatsächlich gearbeitet wurde, noch eine Erlaubnis,
  Abwesenheiten pauschal von Arbeitssegmenten abzuziehen. Diese fachliche
  Auflösung bleibt ausdrücklich offen.

Priorisierte Umsetzung: Quellenauswahl und Ersatzregel erhalten, Arbeit und
Zuschlagsberechtigung trennen, ursprüngliche Segmente plus Dienstidentität
bewahren; erst anschließend Zone/UTC-Dauer/Kalenderteilung berechnen. Keine
neue Intervallbibliothek nötig: Parser und bestehende Generator-Zeitfunktionen
sind vorhanden. NOEXTRA darf keine Arbeit entfernen; eine Hülle darf nicht
als Arbeitsdauer summiert werden. Abwesenheitskonflikte brauchen eine sichtbare
ungeklärte Bewertung, keine erfundene Löschregel.

Nachweis (Originalcheckouts, keine API-Verbindung/Originaldaten):

```sh
SP5_WORK_TIME_ROUTER=../openschichtplaner5-api/sp5api/routers/work_time_rules.py \
PYTHONPATH=.:tests:../libopenschichtplaner5 .venv/bin/pytest -q \
  tools/test_upstream_effective_segments.py tools/test_upstream_work_time_boundaries.py \
  tests/test_partial_limits.py tests/test_calendar_limits.py tests/test_spill_rest.py
```

**147 passed**, davon acht neue Charakterisierungen. Keine Runtimeänderung,
kein Release, kein Nachweis der Originalursache des fehlenden 600s-Jobs.

### Isolierter Kandidat: Dienstsegmente tatsächlich messen

`tools/work_segments_candidate.py:measure_duty` setzt den ersten begrenzten
Korrekturschritt um, ohne API, Library oder Generatorlaufzeit zu ändern. Eingang
ist **ein bereits fachlich ausgewählter Dienst**, nicht eine rohe gemischte
Ist-/Soll-Liste. Dienstidentität und getrennte Fenster bleiben erhalten.
Vorhandene Generatorfunktionen `_parse_native_windows`, `localize`, `minute`
und `day_minutes` übernehmen striktes Parsing, UTC-Messung und Kalenderteilung;
keine zusätzliche Intervallbibliothek. NOEXTRA und bezahlte DURATION beeinflussen
in dieser Schicht die Zeitmessung nicht.

14 synthetische Prüfungen belegen:

- 08–12/16–20 bleibt acht Stunden Segmentarbeit, nicht zwölf Stunden Hülle.
- 00–24 am Wiener Zeitumstellungstag ergibt 23 bzw. 25 reale Stunden.
- Sonntag 20–Montag 08 verteilt vier/acht Stunden auf die richtigen ISO-Wochen;
  auch 03./04.01.2027 wird als 2026-W53/2027-W01 aufgeteilt.
- Fehlende Fenster, ungültige Teilstücke/Uhrzeiten und überlappende Teilfenster
  brechen ausdrücklich ab, statt teilweise oder doppelt zu zählen.
- Nicht existente oder mehrdeutige lokale Endpunkte werden nicht geraten.
- 00–00 bleibt ein undefinierter Quellslot; 08–08 bleibt ein ganzer Diensttag.
  Das ist Zeitsemantik, keine Aussage über dessen fachliche Zulässigkeit.

Bewusste Grenzen: keine Quellenauswahl/Ersatzregel, keine Abwesenheitsauflösung,
keine Regelprüfung, keine bezahlten Stunden, kein Laden von Randkontext und keine
Konfliktprüfung zwischen verschiedenen Diensten. Der Aufrufer muss dieselbe
explizite Kalenderzone verwenden. Überlappungen innerhalb eines Dienstes werden
zur Klärung zurückgewiesen, nicht durch eine erfundene Vereinigungsregel geheilt.
Der bestehende API-Unvollständigkeitsvertrag bleibt unverändert berechtigt.
Als nächstes ist dieser Baustein mit dem bestehenden Quellenauswahlkandidaten
zu verbinden: Dienstidentität und nicht messbare Datensätze sichtbar erhalten,
keine Zeile auf dem Weg zum Prüfbericht stillschweigend verlieren.

Nachweis:

```sh
PYTHONPATH=.:tests .venv/bin/pytest -q tools/test_work_segments_candidate.py \
  tests/test_partial_limits.py tests/test_calendar_limits.py tests/test_spill_rest.py
```

**146 passed**, Ruff erfolgreich. Der erste Testaufruf ohne `PYTHONPATH=.`
scheiterte bei der Modulauflösung; der dokumentierte Aufruf ist erfolgreich.
Keine Runtimeänderung, kein Release und kein Original-600s-Reproduktionsnachweis.

### Quellenauswahl mit strikter Segmentmessung verbunden

`tools/selected_work_segments_candidate.py:measure_selected` verbindet den
vorhandenen expliziten `_employee_plan`-Kandidaten aus
`tools/upstream-api-worktime-contract-candidate.patch` mit `measure_duty`.
Keine neue Quellenauswahlbibliothek, keine Änderung der Originalcheckouts oder
Generatorlaufzeit. Der Selektor wird injiziert; die Integrationstests extrahieren
seine tatsächliche gepatchte Implementierung mit dem bestehenden AST-Testhelfer.

16 synthetische Tests belegen getrennte Ist-/Soll-Auswahl, Ist-Zyklus trotz
vorhandenem Soll-Handeintrag, SPSHI-Ersatz versus Addition (TYPE ist hier kein
Planschalter), unveränderte Arbeit trotz NOEXTRA/DURATION, Feiertagsslot der
Library, getrennte Identitäten doppelter Dienste und explizite nicht messbare
Zeilen bei fehlender Schicht/fehlenden oder beschädigten Fenstern. Ersetzte
Normaldienste bleiben als `replaced` sichtbar. Abwesenheiten aller vier
Intervallarten werden nicht abgezogen: auch am übernächtigen Folgetag steht
`absence_coexists_unresolved`. Die messbaren Minuten sind keine Bestätigung
geleisteter Arbeit oder fachlicher Zulässigkeit.

Identitäten sind **anfragelokale Quellart/Ordinal-Schlüssel**, keine stabilen
DB-Schlüssel. Der Baustein bilanziert alle vom Selektor gelieferten Zeilen,
nicht sämtliche Rohdatensätze: dessen Datumsfilter, Zyklusverdrängung und bislang
übersprungene defekte Datumswerte bleiben separate Deckungslücken. Fehlerhafte
Abwesenheitsdaten führen zum Abbruch. Keine Summenfreigabe, keine Intervallunion,
keine übergreifende Überlappungs-/Ruheprüfung und kein automatisch nachgeladener
Randkontext. Der unvollständige API-Prüfvertrag bleibt deshalb erforderlich.

Reproduktion nach Anwendung des konsolidierten API-Patches auf eine temporäre
Kopie des Originalcheckouts (hier `/tmp/sp5-worktime-contract`):

```sh
SP5_WORK_TIME_ROUTER=/tmp/sp5-worktime-contract/sp5api/routers/work_time_rules.py \
PYTHONPATH=.:tests:../libopenschichtplaner5 .venv/bin/pytest -q \
  tools/test_selected_work_segments_candidate.py tools/test_work_segments_candidate.py \
  tests/test_partial_limits.py tests/test_calendar_limits.py tests/test_spill_rest.py
```

**162 passed**, Ruff erfolgreich. Nächster fachlicher Schritt: ausgewählte
Dienstsegmente gegeneinander auf Überlappung und Ruhe prüfen, ohne gesplittete
Dienste zu verschmelzen; fehlenden Randkontext weiterhin explizit ausweisen.
Kein Release, keine neue private Abnahme unveränderter 0.9.31 und weiterhin kein
Reproduktionsnachweis des fehlenden Original-0.9.29-600s-Jobs.

### Dienstübergreifende Segment- und Ruhediagnose

`tools/duty_conflicts_candidate.py:diagnose_pairs` setzt auf den gemessenen
`SelectedDuty`-Zeilen auf. Vorhandene Generatorhelfer `timeutils.segments`,
`bounds` und `overlap` liefern UTC-Minuten und halboffene Intervalle. Wie
`domain.pair_conflict` trennt der Kandidat tatsächliche Segmentüberschneidung
von ineinandergeschobenen Diensthüllen (`interleaving`). Die Pause innerhalb
eines einzelnen geteilten Dienstes wird nicht als Ruhe zwischen zwei Diensten
geprüft. Es wird keine Intervallunion oder neue Arbeitszeitsemantik eingeführt.

Alle Dienstpaare werden betrachtet, nicht nur zeitlich benachbarte: ein langer
Dienst kann mehrere kürzere enthalten. Null Minuten Abstand sind kein Overlap,
verletzen aber ein explizites positives Ruheminimum. Tageswechsel und DST werden
in verstrichenen Minuten gerechnet. 11 Stunden Wandzeit über den Frühjahrssprung
ergeben im Test 10 Stunden Ruhe; 10 Stunden Wandzeit über den Herbstwechsel
ergeben 11 Stunden. Ein einzelner 24h-Dienst wird ohne passende Längenregel nicht
verboten, und genau 660 Minuten Ruhe erfüllen die entsprechende Schwelle.

`tools/test_selected_work_segments_candidate.py` verfolgt doppelte synthetische
MASHI-Zeilen durch den echten gepatchten API-Selektor bis zum Overlap-Befund mit
getrennten anfragelokalen Identitäten. Ersetzte Zeilen bleiben inaktiv, fehlende
Messungen und Abwesenheitskonflikte bleiben im Bericht ungelöst.

**Grenzen:** Der Aufrufer liefert das Ruheminimum ausdrücklich; das ist kein
Import persönlicher Profile. Nachtregeln, Wochenruhe, Wochenmaxima, vollständige
Quellendeckung und Randkontext werden hier nicht geprüft. Deshalb bleibt auch
bei null Befunden `complete=false`. Die Laufzeit von Generator/API/OSP5 bleibt
unverändert. Keine Original-600s-Reproduktion und kein neues Release.

Nachweis: obiger Testaufruf, zusätzlich
`tools/test_duty_conflicts_candidate.py`: **175 passed** (13 neue Tests), danach
16 Integrationstests erneut erfolgreich; Ruff und `git diff --check` grün.
Nächster Integrationsschritt: Profile und vollständige Randkontextanforderungen
für Tages-/ISO-Wochensummen verbinden, ohne Sollstunden zu Höchstgrenzen zu machen.

### Explizite Profilgrenzen über gemessenen Tages-/ISO-Wochensummen

`tools/calendar_limits_candidate.py:diagnose_calendar` verbindet ausgewählte
Dienstsegmente mit vorhandenen `models.RuleProfile`-Objekten und expliziten
persönlichen `profile_ids`. Keine zweite Profilstruktur und kein neues
Arbeitszeitpaket: Zeitteilung bleibt `timeutils.day_minutes`, Profilsemantik
folgt `validator.validate` (Schleife `limit_days`) und `solver.solve`
(`active_weeks`/`planning_tails`). Mehrere zugeordnete bestätigte Profile bleiben
nebeneinander wirksam; unbekannte, unbestätigte und zeitlich nicht abgedeckte
Zuordnungen werden ausdrücklich als ungelöst gemeldet.

Die Tageswerte zählen verstrichene Segmentminuten aller ausgewählten Dienste
inklusive festem Kontext. Geteilte Dienstpausen zählen nicht; doppelte Dienste
werden nicht durch eine Intervallunion versteckt. Ein Tagesmaximum ist dabei
keine maximale Einzeldienstlänge. `None` bedeutet keine konfigurierte Grenze,
null ist dagegen eine echte Grenze. Ein vorhandenes Ruheminimum erzeugt weder
Tages- noch Wochenmaximum. `DURATION`, `NOEXTRA` und Sollstunden fließen nicht ein.

Wochenprüfungen betreffen Montag bis Sonntag einschließlich Kontext außerhalb
der Planperiode und der Gültigkeit des aktivierenden Profils. Ein in der Periode
beginnender Nachtdienst aktiviert passende Profile auch für seinen Folgetag;
sonstiger zukünftiger Kontext erweitert den Prüfumfang nicht. Das entspricht
der bereits korrigierten Generatorsemantik, nicht einer neuen fachlichen Regel.
Eine explizite Menge `covered_days` benennt fehlende Tage jeder Summenprüfung.
Sie ist lediglich eine Aufruferangabe, kein automatischer Vollständigkeitsbeleg.

**Datenfluss und verbleibende Mappinggrenze:** Die synthetische Integration
verfolgt MASHI/CYCLE/SPSHI über den echten gepatchten API-Selektor
`work_time_rules._employee_plan` bis zu ausgewählten Segmenten und diesen
Profilprüfungen. Ist/Soll werden getrennt gehalten; ein additiver Sonderdienst
führt im Test zu 600 Minuten, Ersatz zu 120 Minuten, die alternative Sollsicht
bleibt jeweils bei 480 Minuten. Das sind Testdaten, keine Nutzerwerte.
Die ursprüngliche API berechnet im Modellmodus in `_check_employee` weiterhin
`get_nominal_hours(Montag, Sonntag) * week_factor`; das ist gemäß
`calculations.get_nominal_hours` eine CALCBASE-Sollrechnung und kein automatisch
importierbares Vertragsmaximum. OSP5 `frontend/src/pages/WorkTimeRules.tsx`
liest/schreibt diese separate API-Konfiguration; der Kandidat behauptet keine
Übertragung dieser Konfiguration in bestätigte Generatorprofile.

**Grenzen:** `complete=false` bleibt immer gesetzt. Quellendeckung, Kalender-
Randabruf einschließlich hineingehender Dienste, Abwesenheitskonflikte,
Überlappung/Ruhe und übrige Profilregeln sind damit nicht vollständig geprüft.
`observed_exceeds` beschreibt die beobachtete Zuordnungssumme; insbesondere bei
überlappenden oder fachlich ungeklärten Quellen ist das kein freigegebenes
Ist-Arbeitszeitkonto. Kein Laufzeiteingriff, kein Release und keine neue private
Abnahme unveränderter 0.9.31. Original-0.9.29-600s-Artefakte fehlen weiterhin.

Tests: `tools/test_calendar_limits_candidate.py` enthält 19 synthetische Fälle
(inklusive vier Vergleichen mit dem unabhängigen Generatorvalidator);
`tools/test_selected_work_segments_candidate.py` vier zusätzliche Integrationen
für Ist/Soll und Sonderdienstersatz/-addition. Zusammen mit Segment-, Paar-,
Teilplan-, Kalender- und Randruhetests: **198 passed**. Ruff und Diffcheck grün.
Die ersten Paritätstestaufrufe hatten falsche Testadapter-Feldnamen
(`Assignment`/`Validation`); nach Anpassung an den bestehenden Vertrag grün.

Nächster offener Integrationsschritt: fehlende/defekte Quelldatumswerte vor
`_employee_plan` sichtbar machen (dessen `_dated` überspringt sie derzeit) und
den erforderlichen Randabruf belegen. Profilimport bleibt eine eigene
fachliche Herkunftsfrage; keine automatischen Höchstgrenzen erfinden.

### Fehlende Quelldaten nicht vor der Messung verlieren

Direkt anschließend reproduziert: API `work_time_rules._employee_plan._dated`
fängt ungültige Datumswerte ab und überspringt sie; leere/fehlende Werte werden
ebenfalls nicht ausgegeben. Sechs synthetische Charakterisierungen belegen das
für MASHI und SPSHI. Sechs zusätzliche Abnahmetests scheiterten zunächst, weil
auch die Messbrücke diese Quellen ohne Hinweis verlor.

`tools/selected_work_segments_candidate.py:measure_selected` prüft deshalb nun
vor der Selektion die Datumslesbarkeit der betreffenden Person und Plansicht.
Unbestimmte Periodenzugehörigkeit führt zu einem ausdrücklichen Abbruch mit
Quellkategorie, ohne Originalfeldinhalt oder Personen-ID. Fehlendes Datum darf
nicht als außerhalb der Periode angenommen werden. Gültige fremde Perioden,
fremde Personen und alternative Plansichten bleiben getrennt; SPSHI gehört
weiterhin nicht zur Sollsicht. Die Library-Konvertierung `calculations.to_date`
wird wiederverwendet; Datetime-Werte werden nicht als reine Quelldaten geraten.

Keine behauptete Gesamtdeckung: CYASS/CYEXC, fehlende Zyklusdefinitionen und
konsistente mehrteilige Datenbanklesung bleiben zu untersuchen. Es wird kein
Originalcheckout und kein produktiver API-Pfad verändert. Der Diagnosestatus
bleibt unvollständig. Nach Korrektur **214 Tests grün**, Ruff und Diffcheck grün.
Öffentlicher lesender GitHub-CI-Metadatenabruf ergibt HTTP 404; `gh` fehlt,
also kein neuer CI-Erfolgsnachweis. Nächster Schritt ist der Zyklus-/Randkontext,
nicht ein weiteres UI- oder Releasepaket.

### Zyklusquellen: fehlende Definition ist kein freier Tag

`sp5lib.calculations.expand_cycle_assignments` überspringt CYASS ohne START,
fehlende CYCLE-Definition und CYCLE.SIZE <= 0. API
`work_time_rules._employee_plan` übernimmt die Expansion ohne Verlustmeldung.
Damit kann der nachfolgende Arbeitszeitprüfer eine unvollständige Dienstmenge
sehen. Das ist ein belegter Diagnosefehlerpfad, kein Nachweis der Ursache des
konkreten 600-Sekunden-Ergebnisses aus 0.9.29.

`tools/selected_work_segments_candidate.py:measure_selected` lehnt diese
Unklarheiten jetzt vor der Selektion ab. Relevante CYEXC benötigen ein lesbares
Datum; fehlende Ausnahme-Daten werden von der Library sonst ignoriert.
Ungültige Datumsstrings können dort dagegen bereits eine Exception auslösen.
Offenes CYASS.END bleibt erlaubt, umgekehrte Intervalle werden abgelehnt.
Nachweislich außerhalb liegende Zuordnungen benötigen keine Zyklusdefinition
für diese Abfrage. Fehlende CYENT-Positionen und SHIFTID=0 bleiben entsprechend
der Library freie Tage, keine erfundenen Dienste.

Zehn synthetische Regressionen in `tools/test_cycle_source_coverage_candidate.py`:
sechs Abnahmetests zunächst rot, nach Korrektur grün; zusammen mit Selektions-,
Segment-, Paar-, Kalender- und Teilplantests **207 passed**, Ruff grün.
Ein erster Editieraufruf scheiterte am fehlenden `python`-Alias; die Änderung
wurde anschließend mit dem Patchwerkzeug angewendet und vollständig geprüft.
Kein produktiver API-/Generatorpfad verändert. Quellendeckung bleibt unbestätigt:
Randabruf, CYENT-Schlüssel/Definitionen und konsistente Datenbanklesung sind
weiter offen. Keine erneute Abnahme der unveränderten veröffentlichten Version.

### Zykluspositionen und hineingehende Dienste: weitere Verlustnachweise

Library `calculations.expand_cycle_assignments` baut CYENT nach
`(CYCLEEID, INDEX)` als Dictionary auf: der letzte Datensatz gewinnt.
Die synthetische Reihenfolge Dienst/freier Tag ergibt keinen Dienst, die
umgekehrte Reihenfolge einen Dienst. Fehlender INDEX wird dort als 0 behandelt;
Positionen außerhalb der Zykluslänge werden nie erreicht. API
`work_time_rules._employee_plan` übernimmt diese Expansion. OSP5
`frontend/src/pages/Schichtmodell.tsx` unterscheidet Tages-/Wochenmodelle und
schreibt flache Tagespositionen; Library `database.get_shift_cycles` baut
ebenfalls ein INDEX-Dictionary für die Darstellung. Kein Beleg, dass solche
defekten Quelldatensätze im konkreten Nutzerprojekt vorkommen.

Der Diagnosekandidat prüft jetzt relevante CYENT auf explizite ganzzahlige,
gültige und eindeutige Positionen (SIZE beziehungsweise SIZE*7). Freie Positionen
und SHIFTID=0 bleiben erlaubt. Dabei korrigiert: Zyklusvorprüfung nur in Ist;
die explizite Sollsicht des API-Kandidaten verwendet keine Zyklen und darf durch
deren defekte Daten nicht blockiert werden. Keine Änderung produktiver Quellen.

Drei Integrationstests mit dem echten gepatchten API-Selektor belegen den
Periodenrand für MASHI, SPSHI und CYASS/CYENT: Sonntag 22–06 Uhr fehlt bei
reinem Montagsabruf vollständig. Mit Vortag sind die sechs Montagsstunden sowohl
im Kalendertag als auch in der neuen ISO-Woche enthalten. Allein vollständige
Datumsabdeckung Montag–Sonntag beweist folglich keine vollständige Arbeitszeit
dieser Woche. Noch kein automatischer Randabruf oder Gesamtgültigkeitsnachweis;
Ruhezeitkontext benötigt zusätzlich seinen eigenen begründeten Horizont.

13 neue synthetische Tests, acht Abnahmetests vor Korrektur rot; insgesamt
**237 passed**, Ruff und Diffcheck grün. Ein Integrationsaufruf verwendete zuerst
einen falschen Pfad zur isolierten API-Testkopie; nach Pfadkorrektur vollständig
grün. Nächster Schritt: expliziter Rand-/Quellendeckungsvertrag statt
Vollständigkeitsannahmen. Kein Release und keine erneute unveränderte Privatabnahme.

### Expliziter Abrufvertrag für native Kalendersummen

`tools/calendar_limits_candidate.py:calendar_source_window` berechnet jetzt den
benötigten Datumsabruf: aktive Planungstage **einschließlich gemessener
Überlauftage**, bei Wochenlimits auf ganze ISO-Wochen erweitert, plus den lokalen
Vortag für hineingehende Dienste. Grundlage ist der vorhandene Generatorparser
`sp5_adapter._parse_native_windows`: Start höchstens 23:59, Ende höchstens 24:00,
ein umgeschlagenes Ende liegt am Folgetag. Dies ist ein Formatvertrag, kein neu
erfundenes Tagesmaximum. Sommer-/Winterzeit werden nicht durch pauschales
Abziehen von 24 UTC-Stunden behandelt.

Der gesamte Abruf muss in **einem** Selektionsaufruf erfolgen: die derzeitigen
MASHI/SPSHI/CYCLE-Identitäten sind anfragelokale Ordinale und dürfen nicht aus
separaten Abrufen zusammengefügt werden. Erweiterte Kontextdienste dürfen auch
nicht wiederum neue Planungstage aktivieren; `diagnose_calendar` unterscheidet
weiterhin anhand des ursprünglichen Planungszeitraums. Für den Abruf sind zuerst
die Überlauftage der Planungsdienste zu bestimmen, anschließend wird der gesamte
Kontext neu selektiert. Konsistente Datenbanklesung bleibt eine offene Voraussetzung.

Die drei echten API-Selektorintegrationstests für MASHI/SPSHI/CYCLE verwenden
nun diesen Vertrag und behalten die sechs Montagsstunden eines Sonntagsdienstes.
Neun zusätzliche Tests prüfen Teilwochen, ISO-Jahreswechsel mit Überlauf,
beide Zeitumstellungen und nicht darstellbare Datumsgrenzen. Fokussierte Suite:
**246 passed**. Kein automatischer produktiver Abruf, kein vollständiger
Ruhezeitkontext, kein Quellendeckungsnachweis und kein Release. Nächster Schritt:
Konsistenz und stabile Quellidentitäten prüfen, bevor die Diagnosekandidaten in
einen produktiven Datenfluss übernommen werden. Der konkrete 0.9.29-Job bleibt
mangels exaktem Eingabe-/Ergebnisartefakt nicht reproduziert.

### Wiederholbare Quellenlesung ist noch kein Datenbank-Snapshot

Library `sp5lib/database.py:SP5Database._read` prüft mtime/Größe pro Tabelle und
liefert bei Cachetreffern dieselbe global gecachte Liste zurück. `_CACHE_LOCK`
sichert Cachezugriffe, aber keine gemeinsame Transaktion über MASHI, SPSHI,
Zyklustabellen, SHIFT, HOLID und ABSEN. Bei Lesefehlern kann `_read` außerdem
`[]` liefern; daraus lässt sich eine fehlende Tabelle nicht von einer leeren
unterscheiden. Ein Cachetreffer ist kein Vollständigkeitsnachweis.

Der API-Kandidat `_employee_plan` liest Tabellen erneut, nachdem der
Diagnosekandidat sie bereits vorgeprüft hat. Vier synthetische Tests mit dem
echten gepatchten API-Selektor waren zunächst rot: ein Versionswechsel zwischen
Vorprüfung und Selektion entfernt MASHI in Ist/Soll; eine Mutation der geteilten
Cacheliste entfernt ein vorgeprüftes Datum; eine Mutation durch den Selektor
verändert die spätere Zeitmessung von acht auf 24 Stunden. Das sind gezielte
Störszenarien, **keine nachgewiesenen Ereignisse im Nutzerprojekt**.

`measure_selected` nutzt jetzt `_RequestTables`: jede benötigte Tabelle wird pro
Aufruf einmal gelesen, mit Standardbibliothek `copy.deepcopy` isoliert und jedem
Verbraucher erneut als Kopie geliefert. Soll liest weiterhin keine unbeteiligten
Ist-/Zyklustabellen. Folgende Aufrufe sehen neue Quelldaten; es entsteht kein
zusätzlicher dauerhafter Cache. Das verhindert nachträgliche Veränderungen einer
bereits gelesenen Tabelle innerhalb dieses Diagnoseaufrufs, **nicht** wechselnde
Tabellenstände während des erstmaligen Einlesens. Zwei zusätzliche Tests belegen
diese Grenze und die Aktualisierung im nächsten Aufruf. `CalendarReport.complete`
bleibt auch bei gemessenen Zeiten und abgedeckten Tagen ausdrücklich `False`.

**100 fokussierte Tests bestanden**, Ruff und Diffcheck grün. Der zusätzliche
Grenztest hatte zunächst einen fehlerhaften RuleProfile-Testaufbau; nach Anpassung
an das bestehende Modell grün. Keine neue Abhängigkeit, kein produktiver Pfad,
keine Originalrepo-/Datenänderung und kein Release. Für produktive Integration
fehlen weiterhin ein belegter konsistenter Quellen-Snapshot samt Fehlerstatus,
tragfähige Quellidentitäten über mehrere Abrufe und der gesonderte Ruhekontext.
Die bisherigen anfragelokalen Ordinale werden nicht zu DB-Schlüsseln umgedeutet.

### Quellenintegrität: abgeschnittene DBF ist nicht zuverlässig ein Lesefehler

Sieben synthetische Charakterisierungstests in
`tools/test_upstream_source_read_integrity.py` prüfen jetzt den **unveränderten**
Librarypfad `SP5Database._read -> dbf_reader.read_dbf_buffer` mit selbst erzeugten
DBF-Bytes. Fehlende Datei und gültige leere Tabelle liefern beide `[]`; nur die
fehlende Datei erzeugt ein Log. Weniger als 32 Headerbytes liefern dagegen
geräuschlos `[]`, das `_read` als erfolgreich geparste Tabelle cached. Bei einem
abgeschnittenen letzten Datensatz beendet der Parser seine Schleife und liefert
den vollständigen Präfix – ebenfalls ohne Fehlerstatus und anschließend gecached.
Der Test unterscheidet fehlenden letzten Datensatz und unvollständige Restbytes.

Ein zusätzlicher Cachetest ersetzt eine synthetische Datei durch andere Bytes
bei identischer Größe und wiederhergestellter mtime: direkter Parser sieht ID 20,
`_read` weiterhin ID 10. Der Hash wird im mtime/size-Schnellpfad nicht erneut
geprüft. Das ist eine reproduzierte Cachegrenze, kein behaupteter Vorgang auf der
produktiven API. Ein weiterer Test zeigt, warum `len(parsed) == num_records`
kein geeigneter Integritätscheck ist: regulär gelöschte DBF-Sätze werden korrekt
nicht zurückgegeben, obwohl sie zum physischen Headerzähler gehören.

**Priorisierte Integrationskorrektur:** vorhandenen Libraryreader um einen
ausdrücklich strikten, strukturierten Lesestatus erweitern, statt im Generator
einen zweiten DBF-Parser oder Logauswertung einzuführen. Fehlend/unlesbar,
strukturell abgeschnitten und gültig leer müssen unterscheidbar sein; physische
Satzvollständigkeit muss vor dem Ausfiltern gelöschter Sätze geprüft werden.
Ein Diagnose-Snapshot benötigt außerdem einen belegten gemeinsamen Quellenstand;
mtime/size und aufruflokale deepcopy allein reichen nicht. Erst danach können
API und OSP5 eine vollständige Arbeitszeitprüfung ausweisen. Diese Änderung ist
hier **noch nicht produktiv implementiert**; die Tests charakterisieren bewusst
den aktuellen Fehlerzustand. Keine Originalrepoänderung, kein Release, keine
neue Aussage zur unveränderten privaten Abnahme oder zum fehlenden Originaljob.

### Isolierter Library-Strict-Reader-Kandidat

`tools/upstream-library-strict-reader-candidate.patch` erweitert den vorhandenen
`sp5lib/dbf_reader.py:read_dbf_buffer` um das optionale `strict=True`. Der
bestehende Standardpfad bleibt unverändert; kein zweiter Generatorparser.
`DBFStructureError.code` unterscheidet kurze Header, ungültige Größen,
unvollständige Felddeskriptoren, Feld-/Satzbreitenfehler, abgeschnittene physische
Sätze und ungültige Löschmarker. Die Prüfung läuft vor der Datensatzselektion:
kein stiller Präfix und kein falscher Fehler wegen regulär gelöschter Sätze.
Fehlermeldungen enthalten nur feste Kategorien, keine Dateipfade oder Nutzdaten.
Headerpadding (FoxPro-Backlink) und optionales EOF-Zeichen bleiben zulässig.

15 synthetische Kandidatentests plus die sieben bisherigen Charakterisierungen
bestehen (22 gesamt), Ruff und Diffcheck grün. Reproduzierbar: Patch auf eine
isolierte Librarykopie anwenden und `SP5_STRICT_READER` auf deren
`sp5lib/dbf_reader.py` setzen; mit Original-Library auf `PYTHONPATH` beide
`tools/test_upstream_{strict_reader,source_read_integrity}.py` ausführen.

**Grenzen:** reine strukturelle Pufferprüfung, keine semantische Feldprüfung,
kein Snapshot und keine neue Vollständigkeitszusage. Der produktive
`SP5Database._read` ruft strict noch nicht auf. Datei fehlt/unlesbar muss im
nächsten Integrationsschritt vor dem Parser explizit gemeldet werden; Diagnose
muss dabei den mtime/size-Schnellcache umgehen und die Fehlerkategorien bis zur
API transportieren. Originalrepos und produktive API sind unverändert. Kein
Release und kein Ursachenbeweis für das weiterhin fehlende 0.9.29-Originaljobpaar.

### Strikter Dateilesepfad im isolierten Library-Kandidaten

Der gleiche Patch erweitert jetzt auch `dbf_reader.read_dbf(..., strict=True)`:
fehlend wird `DBFReadError.code=file_missing`, sonstiger Dateilesefehler
`file_unreadable`, strukturelle Fehler bleiben `DBFStructureError`. Die
Fehlermeldung enthält weder Pfad noch Inhalte; verkettete Betriebssystemfehler
werden in der normalen Traceback-Ausgabe unterdrückt. Legacyaufrufe behalten
`[]` bei Dateilesefehlern. Gültig leere Dateien bleiben erfolgreich leer.

Fünf zusätzliche synthetische Tests prüfen fehlend/leer/abgeschnitten,
PermissionError/IsADirectoryError/OSError und erneutes Lesen trotz identischer
Dateigröße/mtime. **27 Tests bestanden**, Ruff und Diffcheck grün. Der direkte
Lesepfad nutzt keinen Tabellen-Schnellcache. Er garantiert aber weder atomare
Dateilesung noch einen konsistenten tabellenübergreifenden Snapshot. Insbesondere
nutzt `SP5Database._read` ihn noch nicht: die API-Diagnoseanbindung bleibt der
nächste Integrationsschritt. Keine Änderung an Originalrepos, produktiver API,
Generatorlaufzeit oder Installation; kein Release. Kein neuer Ursachenbeweis für
den fehlenden Originaljob 0.9.29 und keine erneute unveränderte private Abnahme.

### Strikter Library-Lesepfad bis zur isolierten Plananalyse

`tools/selected_work_segments_candidate.StrictSourceTables` verbindet jetzt
`SP5Database._table` (native Dateinamensauflösung) mit dem gepatchten
`read_dbf(..., strict=True)`. Der vorhandene API-Selektor `_employee_plan`
und `measure_selected` verwenden damit denselben Libraryparser, umgehen jedoch
den permissiven Tabellen-Cache. Die bereits vorhandene aufruflokale Kopie
verhindert wiederholte Lesungen innerhalb einer Messung. Lesefehler brechen die
Messung ab; es wird kein partielles Stundenresultat zurückgegeben.

31 zusätzliche synthetische Integrationstests prüfen fehlende, leere und
abgeschnittene relevante Tabellen trotz zuvor gefülltem Legacycache, gültig
leere Tabellen sowie fünf nur für Ist benötigte Quellen: ein fehlendes
SPSHI/CYCLE/CYASS/CYENT/CYEXC blockiert Ist, aber nicht die unabhängige Sollsicht.
Zusammen mit den vorhandenen Selektions- und Readerprüfungen: **103 passed**;
Ruff und Diffcheck grün. Testaufruf wie oben, zusätzlich
`SP5_WORK_TIME_ROUTER` auf die isoliert gepatchte API-Datei setzen und
`tools/test_selected_work_segments_candidate.py` einbeziehen.

Dies ist eine explizit zu verdrahtende Diagnosebrücke, keine Änderung des
produktiven API-Endpunkts oder des Generatorimports. Noch offen sind ein
konsistenter tabellenübergreifender Snapshot, semantische Quellenintegrität,
stabile Quellidentitäten und Ruhezeit-Randkontext. Fehlende Daten werden nicht
durch Freigaben oder Regeln ersetzt. Kein neues Release, keine erfolgreiche
Echtdatenplanung und kein Ursachenbeweis für den fehlenden 0.9.29-Originaljob.

### Mehrdeutige Dienstdefinitionen nicht nach Tabellenreihenfolge messen

Im Diagnosekandidaten `measure_selected` war der Aufbau der SHIFT-Tabelle als
Dictionary eine weitere belegte Integritätslücke: zwei Definitionen derselben
ID wurden still auf die letzte reduziert. Vier synthetische Abnahmetests
(Ist/Soll, beide Reihenfolgen; 08–16 versus 00–24) waren zunächst rot. Der
Kandidat hält jetzt alle Definitionen fest und meldet bei einer tatsächlich
benötigten mehrfachen ID `unmeasurable/shift_ambiguous`, ohne Dauer zu wählen.
Nicht verwendete doppelte IDs blockieren die ausgewählten Dienste nicht.

Fünf neue Regressionen; zusammen mit Reader-, Selektions-, Konflikt- und
Kalenderlimitprüfungen **167 passed**, Ruff und Diffcheck grün. Der erste
erweiterte Testaufruf hatte vier Importfehler, weil `tests` im PYTHONPATH fehlte;
der korrigierte Aufruf mit `PYTHONPATH=<Library>:.:tests` besteht vollständig.
Dieser Befund betrifft den isolierten Diagnosekandidaten. Er belegt weder
doppelte Definitionen in Originaldaten noch die Ursache der gemeldeten
24h-Dienste. 24h bleiben nach tatsächlichen konfigurierten Grenzen zu beurteilen.

### Zyklusidentität und Feiertagsdatum vor Stundenmessung

Weitere synthetisch belegte Quellenlücken im isolierten Diagnosepfad:

- Library `calculations.expand_cycle_assignments` reduziert CYCLE auf ein
  Dictionary nach ID. Zwei Definitionen (positive versus Null-Länge) liefern
  allein nach Reihenfolge einen Dienst oder keinen. `_validate_cycle_sources`
  lehnt jetzt mehrfach definierte tatsächlich verwendete CYCLE-IDs ab, auch
  identische Dubletten. Fremde Zyklen/Personen, außerhalb liegende Zuordnungen
  und die Sollsicht werden dadurch nicht zusätzlich blockiert.
- Library `holiday_calendar` ignoriert fehlende/leere DATE; `day_index` wählt
  dann den Wochentag statt STARTEND7. Bei ungültigem String wirft die Library
  einen Fehler mit Rohinhalt. `measure_selected` prüft jetzt das Datum vorab
  und bricht mit der inhaltsfreien Kategorie `Unresolved HOLID source date`
  ab. Ein unbekanntes Datum kann keiner Periode sicher zugeordnet werden.
  Doppelte gültige Feiertagsdaten sind für diesen Zeitpfad hingegen nicht
  mehrdeutig: `day_index` nutzt nur die Datumsmitgliedschaft, nicht INTERVAL.

Belege: `tools/test_cycle_source_coverage_candidate.py` (7 neue Fälle,
3 zunächst rot), `tools/test_selected_work_segments_candidate.py` (7 neue
Fälle, 6 zunächst rot, echter gepatchter API-Selektor). Zusammen mit
Kalenderkontext/-limits, Dienstkonflikten und Generator-Teilplan-/Ruhetests:
**257 passed**; Ruff und Diffcheck grün. Bestehende Library-Funktionen werden
weiter verwendet; kein zusätzlicher Parser und keine neue Fachregel.

Keine produktive Integration, kein Release und kein Nachweis solcher Fehler
in Originaldaten. Der konkrete 0.9.29-Job bleibt für einen Ursachenbeweis
erforderlich. Konsistenter Snapshot, stabile Zuordnungsidentitäten und
vollständiger Ruhezeit-Randkontext bleiben Integrationsvoraussetzungen.

### Zykluszuordnung: Ausnahme-Schlüssel und widersprüchliche TYPE-Erklärung

Library `calculations.expand_cycle_assignments` adressiert CYEXC über
`(EMPLOYEEID, CYCLEASSID)` und expandiert jede CYASS-Zeile einzeln. Zwei aktive
Zuordnungen derselben Person mit derselben ID ergeben synthetisch zwei Dienste;
eine einzige Ausnahme unterdrückt beide, selbst bei unterschiedlichen Zyklen.
Der isolierte `_validate_cycle_sources`-Kandidat lehnt diese Kollision jetzt vor
der Selektion mit `Unresolved CYASS ambiguous identity` ab. Fremde Personen,
außerhalb liegende Zuordnungen und unterschiedliche IDs bleiben erlaubt.
Doppelte Ausnahme-Datumszeilen sind dagegen im bestehenden Set-Pfad idempotent.
Belege: sechs neue Tests in `tools/test_cycle_source_coverage_candidate.py`,
zwei davon vor der Korrektur rot. Kein Nachweis solcher Dubletten in Realdaten.

Die anschließende zusammenhängende Prüfung zeigt eine **offene Semantik**, keine
Berechtigung zur stillen Korrektur: API `routers/schedule.py::CycleExceptionSet`
kommentiert TYPE mit `1=skip, 0=normal`; Library `set_cycle_exception` wiederholt
dies. `expand_cycle_assignments` liest TYPE aber überhaupt nicht: 0, 1 und None
unterdrücken jeweils den Dienst (drei neue Charakterisierungstests).
OSP5 `frontend/src/pages/Schichtmodell.tsx::AddExceptionModal` nennt TYPE dagegen
Plan-Eintragsart, sendet es nicht und nutzt so API-Default 1. Der vorhandene
`AddExceptionModal.test.tsx` sichert nur diesen ausgelassenen Parameter ab, nicht
TYPE=0. Daher weder TYPE=0 als Wiederherstellung implementiert noch Ausnahmen
als persönliche Freigaben interpretiert.

Zusätzliche belegte Zuordnungslücke für die nächste Untersuchung: OSP5
`AddExceptionModal::getAssignmentId` nutzt `assignments.find` ausschließlich nach
Person, ohne ausgewähltes Datum oder eindeutige Zykluswahl. Bei mehreren
Zuordnungen hängt das adressierte Ziel von der Listenreihenfolge ab. Erst
Quellvertrag/Zeitraum prüfen und synthetisch reproduzieren; noch kein UI-Fix.

Keine Originalrepo-/Runtimeänderung und kein Release. Exaktes 0.9.29-Jobpaar,
atomarer Quellensnapshot und vollständiger Ruhekontext bleiben offen.

### Datum der Zyklus-Ausnahme: wirkungsloser Erfolg synthetisch belegt

`tools/test_cycle_exception_target_audit.py` führt den aus der unveränderten
OSP5-Datei extrahierten JavaScript-Ausdruck `getAssignmentId` mit Node aus und
verbindet dessen ID mit der echten Library `expand_cycle_assignments`. Es ist
kein Browser-/HTTP-Test und führt keinerlei Schreiboperation aus.

Sechs Charakterisierungen belegen:

- Steht eine abgelaufene oder erst künftig gültige Zuordnung vor der am
  Ausnahmedatum gültigen Zuordnung, adressiert OSP5 die inaktive ID. Der
  beabsichtigte Dienst bleibt in der Library erhalten. Umkehr der Listenfolge
  unterdrückt ihn. START/END gelten dabei einschließlich des Grenztags.
- Bei zwei gleichzeitig gültigen, unterschiedlichen Zuordnungs-IDs unterdrückt
  eine Ausnahme nur den zuerst adressierten Zyklus; ein Dienst bleibt übrig.
  Die UI-Bezeichnung „freier Tag“ ist deshalb ohne eindeutigen Zielzyklus keine
  verlässliche Aussage über den gesamten Tag der Person.

Datenfluss: OSP5 `Schichtmodell.tsx::AddExceptionModal` → API
`schedule.py::set_cycle_exception` (reicht die ID unverändert durch) → Library
`database.py::set_cycle_exception` (speichert nach Person/Zuordnungs-ID/Datum,
ohne dort den Zuordnungszeitraum zu validieren) →
`calculations.py::expand_cycle_assignments` (Ausnahmen pro Person/Zuordnungs-ID,
Expansion innerhalb START/END). Der bestehende OSP5-Test
`AddExceptionModal.test.tsx` hat nur eine Zuordnung ohne Zeitraum und sichert
das Weglassen von TYPE ab; diese Mehrfachzuordnungsfälle deckt er nicht ab.

Konkrete Korrekturrichtung für den Quellenvertrag: Datum vor Zielauswahl prüfen;
bei genau einer gültigen Zuordnung diese adressieren; bei keiner nicht
speichern; bei mehreren Zielzyklus explizit bestimmen, nicht alle unterdrücken
oder den ersten raten. Serverseitig Person/ID/Datum ebenfalls validieren.
Das ist hier noch **nicht implementiert**; insbesondere wird die offene
TYPE-Semantik nicht geändert. Keine neuen Generatorfreigaben oder Tagesverbote.

Relevanz: Ein vermeintlich ausgenommener Ist-Referenzdienst kann bestehen bleiben
und weiter Stunden/Überlappungen verursachen. Dieser Nachweis betrifft
synthetische Quelldaten, nicht den fehlenden originalen 0.9.29-600s-Job. Vorrang
für dessen Reproduktion und harte Generatorgrenzen bleibt bestehen; keine
produktive UI-Änderung und kein Release aus dieser Quellencharakterisierung.

### Direkter Versionsvergleich zur 0.9.29-Teilplanmeldung (11.09.2026)

Zur Konsolidierung wurde `sp5generator/` aus dem unveränderten Git-Tag
`v0.9.29` per `git archive` in ein temporäres Verzeichnis extrahiert. Dieselben
heutigen synthetischen Tests liefen dort und gegen `fc10e59`, mit demselben
Python-/OR-Tools-Environment. Keine Installation, Quelldaten oder Runtime
wurden geändert. Das ist ein kontrollierter Codevergleich, kein Nachbau des
ursprünglichen Docker-Environments und kein 600-Sekunden-Lasttest.

Aus `test_partial_limits.py`, `test_calendar_limits.py`, `test_spill_rest.py`
wurden diese Testfunktionen samt Parametrisierungen ausgewählt:

- `test_daily_limit_sums_separate_duties_not_paid_minutes`
- `test_weekly_limit_uses_fixed_context_and_not_target_or_paid_minutes`
- `test_24_hour_duties_are_not_forbidden_by_11_36_rest_alone`
- `test_spill_limits_include_fixed_following_context`
- `test_spill_uses_assigned_profile_valid_on_tail_date`
- `test_overnight_spill_requires_confirmed_profile_coverage`
- `test_calendar_spill_rest_exact_36_hour_boundary`
- `test_partial_never_keeps_conflicting_assignments`
- `test_no_rule_requires_every_eligible_employee_to_receive_a_duty`

Ergebnis: **aktuell 39 bestanden; 0.9.29 29 bestanden / 10 fehlgeschlagen**.
Neun Altfehler sind unzulässige `Validation(valid=True, complete=True)` für
Überhanglimits, Folgeprofilabdeckung oder Kalenderwochenruhe. Der zehnte ist
**kein zusätzlicher Regelverstoß**: `planning_diagnostics` fehlte damals.
Die davor geprüfte Aussage, dass ein Bedarf mit Maximum 1 bei drei geeigneten
Personen zwei Personen ohne Einteilung lässt, besteht auch unter 0.9.29.
Die Zahl zehn darf deshalb nicht als zehn unabhängige Sicherheitsfehler gelten.

Da fehlgeschlagene Validator-Assertions den Solverteil eines Tests abbrechen,
wurden drei Fälle zusätzlich unmittelbar durch `solve(..., 3, partial=True)`
und anschließendes `validate` geführt:

| Synthetischer Fall | 0.9.29 | Aktueller Stand |
| --- | --- | --- |
| Sonntag 23–Montag 08 plus Montag 12–14; Tagesmaximum 599 Minuten | Überhang gewählt, OPTIMAL, Validator gültig trotz 600 Minuten Montag | Überhang offen, Fixdienst erhalten, OPTIMAL, Validator gültig |
| Gleiche Dienste, Wochenmaximum 599 Minuten | Überhang gewählt, OPTIMAL, Validator gültig trotz 600 Minuten neuer ISO-Woche | Überhang offen, Fixdienst erhalten, OPTIMAL, Validator gültig |
| `spill_case()`: 11h tägliche / 36h Kalenderwochenruhe; Überhang reduziert längste Folgewochenruhe von 40h auf 32h | Überhang gewählt, OPTIMAL, Validator gültig | Überhang offen, vier Fixdienste erhalten, OPTIMAL, Validator gültig |

**Damit waren diese Altfehler nicht erst Folge eines Zeitlimits:** Sie treten
bereits mit OPTIMAL auf. OPTIMAL zertifiziert das damalige Modell, nicht dessen
fachliche Vollständigkeit. Die Korrekturen liegen in `solver.solve` (aktive
Überhangtage, datierte Profile, ISO-Wochensummen, bedingte Folgewochenruhe),
`validator.validate`/`weekly_windows` und der Profilabdeckung in `domain`;
sie sind in 0.9.30/0.9.31 beschrieben, nicht erst auf dem Analysebranch behoben.

Priorisierte verbleibende Abgrenzung:

1. Originales 0.9.29-Projekt/Job/Ergebnis fehlt weiterhin laut privater
   Artefaktprüfung. Keine Aussage, welcher der synthetisch belegten Fehler dort
   tatsächlich wirksam war. Verlorene Profilzuordnungen müssen aus tatsächlicher
   Einrichtung rekonstruiert werden, nicht aus angenommenen Höchststunden.
2. 11h/36h allein verbieten keinen 24h-Dienst; Soll-/bezahlte Stunden sind keine
   harten Wochenmaxima. Die entsprechenden Kontrollen bestehen auch unter
   0.9.29. Keine Pflicht zur Einplanung aller Personen hinzufügen.
3. Der produktive Import setzt `context_complete=False`; Kalenderabdeckung ist
   kein Nachweis vollständiger Quelldaten. `validate` unterscheidet weiterhin
   `valid` von `complete`: ein Kontextdiagnostikum verhindert Vollständigkeit,
   ist aber kein nachgewiesener persönlicher Regelverstoß. Der isolierte
   Library/API-Diagnosekandidat benötigt weiter atomaren Quellenstand und einen
   eigenständigen Ruhekontextvertrag; Tages-/Wochenlimitfenster reichen dafür
   nicht aus.
4. Unveränderte private 0.9.31-Abnahme nicht redundant wiederholt: beide Sichten
   MODEL_INVALID wegen offener Einrichtung, kein realer generierter Vergleich.
   Nächste Abnahme bei relevanter Runtimeänderung oder neuem Release. Dieser
   Versionsvergleich fügt keine fachlichen Regeln hinzu und benötigt kein Release.

### Ruhekontext ist ein eigener Quellenvertrag (11.09.2026)

`tools/test_rest_source_window_contract.py` charakterisiert vier synthetische
Fälle mit den bestehenden `calendar_source_window`- und `diagnose_pairs`-Helfern:
jeweils Tages-/ISO-Wochenfenster und vor-/nachgelagerter Randdienst. Ein Samstag
23:00 bis Sonntag 23:00 laufender Dienst liegt außerhalb des ab Sonntag
selektierten Kalenderquellenfensters für Montag. Zu Montag 06:00 bleiben aber
nur sieben Stunden Ruhe. Umgekehrt fehlt nach Sonntag 15:00–23:00 der Montag
06:00 beginnende Dienst, obwohl der Sonntagsdienst keinen Überhang hat.

Die eingeschränkte Auswahl meldet in allen vier Fällen keinen Paarkonflikt;
mit dem fehlenden Randdienst werden jeweils 420 statt erforderlicher 660 Minuten
erkannt. Beide Berichte bleiben ausdrücklich `complete=False`. Der 24h-Dienst
im ersten Fall ist nicht selbst der beanstandete Verstoß; beanstandet wird der
Abstand zum Folgedienst. Dies ist ein belegter Integrationsbedarf des isolierten
Diagnosekandidaten, kein neuer nachgewiesener Fehler im produktiven Generator.

Folgerung: Kalenderlimit- und Ruhequellenfenster getrennt bestimmen und für die
Selektion zusammenführen; anschließend nur planungsrelevante Paare bewerten.
Ein zusätzlich geladener Kalendertag darf nicht pauschal als ausreichender
Ruhekontext gelten. Datierte Profile, längere konfigurierte Ruhe, Nachtblock-
und Wochenruhe sowie UTC/DST bleiben Teil des noch offenen Vertrags. Auch ein
korrektes Fenster beweist weder vollständige Quelltabellen noch einen atomaren
Datenstand. Keine Änderung an produktiver API, Profilen oder Benutzerinstallation.

Prüfung: `PYTHONPATH=.:tests .venv/bin/python -m pytest -q
tools/test_rest_source_window_contract.py tools/test_duty_conflicts_candidate.py
tools/test_calendar_limits_candidate.py` — 36 bestanden. Der erste Aufruf ohne
`tests` im Suchpfad scheiterte bei vier bestehenden Quervergleichstests am
Fixture-Import; nach korrektem Suchpfad bestanden auch diese.

### Expliziter Planungsumfang der Paardiagnose (11.09.2026)

Der isolierte `tools/duty_conflicts_candidate.diagnose_pairs` akzeptiert jetzt
optional `planning_source_ids`: Nur Paare mit mindestens einer ausdrücklich
benannten Planungsquelle werden als Befund ausgegeben. Die unbeschränkte
Bestandsprüfung bleibt der Default. Eine leere Auswahl prüft keine Planpaare;
unbekannte Identitäten werden abgewiesen. Unaufgelöste Kontextquellen bleiben
sichtbar und `complete=False` bleibt unverändert. Keine Datumsheuristik leitet
hier persönliche Freigaben oder die Zugehörigkeit zum Plan ab.

Synthetisch belegt: Ein ausschließlich historischer Überlappungskonflikt wird
im Planungsmodus nicht ausgegeben, während beide Konflikte zum vorangehenden
und folgenden Randdienst erhalten bleiben (420 bzw. 360 Minuten bei 660 Minuten
Vorgabe). Drei neue Tests sichern auch offene Kontextquellen und falsche IDs ab;
die kombinierte Paardiagnose-/Kalenderlimit-Suite besteht mit 39 Tests.

Abgrenzung zur Runtime: `validator.validate` prüft derzeit alle Paare der
jeweiligen Person einschließlich Fixkontext. Diese bestehende konservative
Semantik wurde **nicht** geändert. Der Diagnosefilter ist keine Erlaubnis,
einen produktiven Plan trotz Fixkontextfehlern freizugeben.

Die gelesenen Runtime-Horizonte in `validator.validate` berücksichtigen tägliche,
Nachtnachruhe, Nachtblockruhe, Serienlängen und Wochenfenster; `domain.pair_conflict`
verwendet datierte Profile an beiden Dienstanfängen, `night_block_conflict`
zusätzlich den Abstand der lokalen Starttage. Ein einfacher konstanter
Minutenfilter bildet diese Regeln nicht gleichwertig ab. Die Ableitung des
Quellselektionsfensters muss außerdem den vor dem Ruhefenster beginnenden
eingehenden Dienst erfassen. Weiter offen: datierter Ruhequellenvertrag und
atomarer Quellenstand; keine neue Vollständigkeits- oder Echtdatenfreigabe.

### Datierte Ruhe und ausgewählte Nachtblockbrücken: Vertragsgrenze belegt

Sechs weitere synthetische Regressionen in
`tools/test_rest_source_window_contract.py` vergleichen den isolierten
Skalar-Diagnosekandidaten direkt mit `domain.pair_conflict`,
`domain.night_block_conflict`, `validator.validate` und `solver.solve`:

- Zwei Dienste mit 16 Stunden Abstand erfüllen den 660-Minuten-Skalar.
  Ein explizit zugeordnetes 1020-Minuten-Profil, das nur am Anfangstag des
  ersten **oder** zweiten Dienstes gilt, verhindert trotzdem die gemeinsame
  Auswahl. Das gleiche nicht zugeordnete Profil tut dies nicht. Validator und
  Teilplansolver stimmen überein; der Teilplan wählt genau einen statt zwei
  Dienste. 1020 Minuten sind ausschließlich synthetische Testkonfiguration,
  kein neuer Standardwert.
- Drei Nachtdienste an aufeinanderfolgenden Starttagen sind unter expliziter
  2880-Minuten-Nachtblockruhe gemeinsam zulässig. Entfällt der mittlere Dienst,
  werden die äußeren Dienste zu aufeinanderfolgenden ausgewählten Diensten:
  40 Stunden Abstand unterschreiten dann die geforderten 48 Stunden.
  Der Teilplansolver wählt nur einen; der Validator verwirft beide zusammen.
  Ein beliebiger Paarvergleich der äußeren Dienste würde dagegen bei vorhandener
  Brücke einen falschen Konflikt melden. Ein reiner 660-Minuten-Vergleich erkennt
  den echten Konflikt ohne Brücke nicht.

Damit ist die nächste Integrationsanforderung konkreter: Ein Ruhequellenvertrag
muss datierte persönliche Profilzuordnung an beiden Dienstanfängen, fachlich
belegte Nachtkennzeichnung und die tatsächlich ausgewählte Reihenfolge erhalten.
Quellfenster allein ersetzen diese Daten nicht. Der aktuelle `Duty`-Messkandidat
enthält nur Identität und Zeitsegmente, keine Nachtart und keine Profilzuordnung;
er darf daher nicht als gleichwertiger Regelvalidator integriert werden.
Die bereits vorhandenen DST-Regressionen prüfen zusätzlich reale statt lokale
Uhrzeitabstände. Alle 45 Tests der kombinierten Ruhe-/Paardiagnose-/Kalenderlimit-
Suite bestanden. Kein produktiver Code, keine Quelldaten und keine Defaults
wurden geändert; daraus folgt kein Nachweis über den fehlenden Originaljob.

### Kombinierte Ruhebedingungen: vollständiger synthetischer Auswahlvergleich

`test_exhaustive_selected_nights_cannot_bridge_dated_daily_rest` erweitert den
vorstehenden Vertrag um sechs Kombinationen aus Profilzuordnung und Gültigkeit
am ersten, mittleren oder letzten Nachtstart. Für jede Kombination werden alle
acht Teilmengen der drei Dienste gegen eine explizit vorgegebene Zulässigkeitsliste
geprüft (48 Validatorprüfungen), anschließend die maximale Besetzung des
Teilplansolvers gegen diese Liste. Die erwartete Liste wird nicht aus Solver-
oder Validatorfunktionen abgeleitet.

Befund: Die ausgewählte mittlere Nacht überbrückt die synthetische
48h-Nachtblockbedingung, aber nicht die zugleich geltende datierte 17h-Tagesruhe.
Bei Zuordnung des strengeren Profils am mittleren Start ist nur eine Nacht
zulässig; bei Zuordnung am äußeren Start sind zwei zulässig. Ohne Zuordnung
bleiben alle drei zulässig. `domain.pair_conflict` und die harten Paarbedingungen
in `solver.solve` bleiben somit neben der auswahlabhängigen Nachtblockbedingung
wirksam. Der Vergleich bestätigt diese Kombination im aktuellen Stand, belegt
keinen weiteren Runtimefehler und reproduziert nicht den fehlenden 600s-Originaljob.
Keine neuen fachlichen Defaults, kein produktiver Code geändert.

### Nachtkennzeichnung: drei Quellheuristiken sind kein Regelvertrag

Zusammenhängend geprüft gegen Library `0dac443`, API `d578f21`, OSP5 `addf5c2`:
`5SHIFT.STARTEND0/STARTEND<weekday>` → Library
`SP5Database._is_night_shift` / `get_employee_stats_year` → API-Jahresstatistik
→ OSP5 `MitarbeiterProfil.tsx` (`getEmployeeStatsYear`). Daneben liefert
API `reports.py:is_night` die Nachtzählung für OSP5 `Fairness.tsx`
(`/api/v1/fairness`); `reports.py:categorize_shift` klassifiziert nochmals anders.

Der neue ausführbare Audit `tools/audit_upstream_night_semantics.py` extrahiert
die bestehenden Funktionen per AST unverändert, ohne Server/DB-Zugriff. Sieben
synthetische Fälle belegen:

| Zeitfenster | Library-Jahresstatistik | API-Fairness | API-Kategorie |
|---|---|---|---|
| 18–23 Uhr | keine Nacht | keine Nacht | Nacht |
| 20–08 Uhr | keine Nacht | Nacht | Nacht |
| 05–13 Uhr | keine Nacht | Nacht | Früh |
| 22–06 Uhr | Nacht | Nacht | Nacht |

Die Library prüft Start ab 22 Uhr oder Ende bis 06 Uhr, die Fairness nur den
Start des ersten `STARTEND0`-Fensters ab 20 Uhr/vor 06 Uhr; die Kategorie nutzt
18 Uhr/vor 04 Uhr und einen Namensfallback. Zusätzlich klassifiziert die Library
einen konkreten 08–16-Uhr-Wochentag weiterhin als Nacht, wenn `STARTEND0` 22–06
enthält. Umgekehrt erkennt nur sie das konkrete Nachtfenster bei tagsüber
liegendem `STARTEND0`. Das sind nachgewiesene Unterschiede der Statistikpfade,
kein Beleg für die fachlich richtige Nachtdefinition des Nutzers.

Generator `sp5_adapter.import_snapshot` übernimmt diese Statistiken bewusst
nicht als harte Art: importierte `Shift` bleiben unbestätigt, `BoundaryWork.kind`
bleibt `unknown`. Auch persönliche datierte Generator-Regelprofile werden aus
diesen Zahlen nicht geliefert. Folgerung für den offenen Ruhequellenvertrag:
explizite datierte Art/Profilzuordnung mit Herkunft erhalten; bei fehlender
Quelle Klärungsbedarf behalten. Keinen der drei Statistikwerte automatisch als
Nachtblockfreigabe einsetzen. Eine automatische Übernahme könnte Ruhebedingungen
auslassen oder zusätzliche Bedingungen erfinden. Kein Originaljob-Nachweis.

Prüfung: Audit mit beiden oben genannten Quelldateien: sieben Fälle bestanden;
`tests/test_sp5_adapter.py`, `tools/test_rest_source_window_contract.py` und
`tests/test_partial_limits.py`: 182 bestanden. Ruff grün. Keine Runtimeänderung,
kein Release und deshalb keine redundante Abnahme desselben Dockerstands.

### Wiederholte API-Antworten sind kein atomarer Quellenstand

Analyse 2026-09-11, gleiche oben dokumentierte Library/API/OSP5-Quellstände.
Vorhandenen Mechanismus geprüft, keine zweite Snapshot-Implementierung gebaut:

- Library `database.py:SP5Database._read` sichert den DBF-Cache je Tabelle mit
  `_CACHE_LOCK`, liest aber nicht alle Tabellen in einer gemeinsamen Transaktion.
  Der Schnellpfad verwendet Änderungszeit und Größe; der Inhalts-Hash wird erst
  bei deren Änderung berechnet. Das ist kein globaler Quellenrevisionsvertrag.
- API `dependencies.py:get_db` wählt das Backend; `routers/master_data.py:get_shifts`
  und `routers/schedule.py:get_schedule` liefern getrennte Abfragen. Dieser Befund
  betrifft den untersuchten DBF-Pfad, nicht eine behauptete PostgreSQL-Isolation.
- OSP5 `frontend/src/pages/Schedule.tsx:loadSchedule` lädt Plan, Feiertage und
  Konflikte mit `Promise.all`; SSE veranlasst erneutes Laden. Weder gemeinsame
  Anzeige noch paralleles Laden beweisen einen transaktionalen Quellenstand.
- Generator `api_adapter.py:APIClient.get` cached pro URL; `verify` liest jede
  URL erneut und vergleicht Antworten. Der SHA-256 identifiziert die gesammelten
  Antworten, nicht eine serverseitige Transaktion. `import_api` kennzeichnet das
  bereits ehrlich in `source_consistency` und behält einen offenen Quellblocker.

Neuer synthetischer Gegenbeweis
`test_repeated_responses_do_not_prove_atomic_source_revision`: Zwei jeweils
intern konsistente Quellenstände wechseln zwischen den Endpunktabfragen. Die
gesammelte Dienst-/Plan-Kombination existierte in keinem dieser Stände; dennoch
bestehen zwei aufeinanderfolgende `verify`-Durchläufe mit gleichem Fingerprint.
Das charakterisiert eine Vertragsgrenze, keinen erfolgreichen Import dieses
inkonsistenten Beispiels. Die übrigen Importprüfungen werden damit nicht umgangen.
`test_api_import_retains_nontransactional_source_blocker` sichert zusätzlich die
bestehende Kennzeichnung und den offenen Klärungsbedarf im vollständigen Import.
Der vorhandene Änderungstest prüft weiterhin die Ablehnung abweichender Antworten.

Priorisierte Konsequenz: Für belastbare Reproduktion den tatsächlich verwendeten
Generator-Projekt-/Jobstand und das Ergebnis privat erhalten. Für einen künftig
atomaren Import ist ein quellseitig konsistenter Export oder ein über sämtliche
Antworten gültiger Snapshot-/Revisionsvertrag nötig; weitere Vergleichsrunden
allein lösen das Problem nicht. Keine solche Garantie aus Zeitstempeln, SSE oder
Hash ableiten. Kein Beleg, dass diese Lücke den Originalfall 0.9.29 verursacht hat;
fehlende Freigaben, Profilbestätigung und harte Grenzwerte bleiben separat zu prüfen.

Unmittelbarer Folgecheck: `master_data.py:get_shifts` verwendet zusätzlich
`sp5api/cache.py` mit 60 Sekunden Default-TTL. API-Schreibpfade invalidieren
`shifts:`; eine externe Änderung ist dadurch allein nicht erfasst. Der isolierte
Audit `tools/audit_upstream_source_cache.py` führt das vorhandene Cache-Modul mit
synthetischen Dienstfenstern und kontrollierter Uhr aus: zweimal gleiche alte
Antwort vor Ablauf, Cache-Miss nach Ablauf, explizite Invalidierung funktioniert.
Das ist ein Frische-Gegenbeispiel für den Cache, kein Nachweis eines tatsächlich
veralteten privaten Imports. Warten auf TTL würde weiterhin keine Atomarität
herstellen. Verifikation: 201 API-/Teilplan-/Kalenderlimit-Tests, drei Cachefälle,
Ruff und `git diff --check` bestanden. Nur Analyse-/Teständerungen, kein Release;
unveränderte private Dockerabnahme nicht wiederholt.

### Datierte Kalenderwochenruhe: direkte Modellierung und Nachprüfung

Neuer synthetischer Befund 2026-09-11, `tests/test_dated_calendar_rest.py`:
Planungszeitraum nur Montag, optionaler Dienst Montag 16–24 Uhr; fester
Randkontext Mittwoch 08–16, Freitag 00–16 und Sonntag 00–08 Uhr. Zugeordnetes,
bestätigtes Wochenruheprofil gilt nur Samstag derselben Woche: 36h Kalenderruhe,
11h tägliche Ruhe, keine zusätzlichen Stundenmaxima. Mit Montag beträgt die
längste Wochenruhe 32h, ohne Montag 56h; die tägliche Ruhe ist nicht verletzt.

- `validator.weekly_windows` erzeugt die Planungs-Kalenderwoche;
  `validator.validate` prüft das Profil, wenn seine Gültigkeit das Wochenfenster
  überlappt. Deshalb lehnt er den Montagdienst ab.
- `solver.solve` bildet `active_weeks` dagegen aus Profiltagen **innerhalb des
  Planungszeitraums**; ohne Überhang aktiviert das Samstagprofil keine direkte
  Wochenruheklausel. Der erste Modellkandidat verletzt daher die Wochenruhe.
- Die bestehende unabhängige Nachprüfung erkennt dies und schließt die Auswahl
  aus. Ergebnis: gültiger optimaler Teilplan mit drei unveränderten Fixdiensten,
  Montag offen, genau eine `separation_rounds`-Runde. Ein Montagprofil braucht
  keine solche Runde; ein nicht zugeordnetes Profil wirkt in beiden Fällen nicht.
- Eine fünfte Regression erzwingt `UNKNOWN` nach dem verworfenen Kandidaten:
  Es werden **keine Einteilungen** ausgegeben und `validation.valid` bleibt falsch.
  Das ist ein kontrollierter Status-Test, kein echter 600-Sekunden-Lauf.

Damit ist eine konkrete Lücke in der direkten Modellabdeckung belegt, **kein
Durchlassen eines ungültigen Ergebnisses**. Sie kann zusätzliche Suchrunden
verursachen; ein Einfluss auf Laufzeit oder Ursache des Originaljobs ist nicht
gemessen. Priorisierte Korrektur: direkte Kalenderwochenruheklauseln auf denselben
datumsbezogenen Fensterumfang wie den bestehenden Validator ausrichten und die
bedingte Überhangaktivierung erhalten. Nicht die Nachprüfung abschwächen und
nicht diese Wochenfenstersemantik pauschal auf Tages-/Stundenlimits übertragen.

Einordnung im zusammenhängenden Quellenbefund: Library/API liefern bisher keinen
übernommenen autoritativen datierten persönlichen Ruheprofilvertrag; Generator-
Profile und Freigaben bleiben explizite Einrichtung. Dieser Test verwendet bewusst
ein synthetisch bestätigtes Profil, keine abgeleitete Ist-Historienfreigabe. Die
bereits belegten 0.9.29-Stunden-/Überhangfehler, fehlenden Originaljob-Artefakte und
der private `MODEL_INVALID`-Einrichtungsblocker bleiben davon getrennt.

Prüfung: 167 Tests (`test_dated_calendar_rest`, `test_partial_limits`,
`test_spill_rest`, `test_core_rules`) bestanden; Ruff grün. Nur Tests/Analyse,
keine Runtimeänderung, kein Release und kein erneuter identischer Dockerabnahmelauf.


### Korrektur: datierte Kalenderwochenruhe direkt im Solver

Folgeschritt 2026-09-11 zum oben belegten Fall: `solver.solve` bildet für
`calendar_week` nun eigene `rest_weeks` aus allen Planungswochen, deren Fenster
das zugeordnete Profil überlappt. Das entspricht der Kombination aus
`validator.weekly_windows` und der Profilüberlappungsprüfung in `validate`.
Tages-/Wochenstundenlimits behalten ihre bisherige datumsbezogene Aktivierung.
Zusätzliche Zukunftswochen durch Überhang bleiben nur bei Auswahl des auslösenden
Dienstes aktiv; fremder fester Randkontext aktiviert sie nicht pauschal.

Die synthetische Regression in `tests/test_dated_calendar_rest.py` deckt jetzt
32 Kombinationen aus Profil am 4./5./10./12. Januar, Zuordnung ja/nein,
Voll-/Teilplanung und Planung nur Montag beziehungsweise nur Sonntag ab. Nur die zugeordneten Profile innerhalb der Planungswoche
wirken. Der jeweils problematische Planungsdienst wird direkt ausgeschlossen, mit null
`separation_rounds`; Vollplanung ist entsprechend unlösbar. Außerhalb liegende
und nicht zugeordnete Profile sperren den Dienst nicht. Die UNKNOWN-Sicherheit
wird weiterhin mit einem tatsächlich verworfenen Kandidaten geprüft, nun am
bestehenden `rolling_elapsed`-Überhangbeispiel; kein fingierter Validator.

Dies ändert die direkte Modellabdeckung, nicht die fachliche Regel oder den
unabhängigen Validator. Kein Beleg für die Ursache des fehlenden Originaljobs
0.9.29 und keine gemessene Beschleunigungszusage für dessen 600-Sekunden-Lauf.

Prüfung der Runtimekorrektur: vollständige lokale Suite 772 bestanden (zwei
bestehende Testclient-Deprecation-Warnungen); anschließend um die spiegelbildliche
Sonntagsplanung ergänzt, alle 33 Tests dieser Datei bestanden. Ruff und
`git diff --check` grün. Remote-CI nicht nachgewiesen (`gh` fehlt, lesende
GitHub-API-Abfrage ohne Authentifizierung liefert 404).

Private lokale API-Abnahme des Kandidaten: 11.09.2026, 16:27:47–16:31:34 UTC,
September und derselbe bisherige Teamumfang, Ist/Soll jeweils Import, Speichern,
Job und unabhängige Validierung. Basisimage 0.9.31 mit lesend eingebundenem
aktuellem Python-Paket; geladener Solverpfad im Container verifiziert, Modulhashes
privat gesichert. Health und lesende API-Verbindung erfolgreich; beide Sichten
weiterhin `MODEL_INVALID`, null generierte Einteilungen, unabhängige Validierung
nicht gültig, null persönliche Freigaben und kein bestätigtes Profil. Keine
Freigaben oder zusätzlichen Regeln erfunden. Keine erfolgreiche reale Neuplanung
und kein Originaljob-Nachweis. Privater Prüfcontainer anschließend gestoppt;
keine Benutzerinstallation verändert. Kein neues Release.

### Datierter Überhang: rollierende Ruhe und Statussicherheit

Zusätzliche synthetische Absicherung 2026-09-11 nach der Kalenderkorrektur:
`test_spill_rest_respects_profile_assignment_and_validity` prüft 24 Kombinationen
(Kalenderwoche/rolling_elapsed/rolling_local, Voll-/Teilplanung, zugeordnet/nicht
zugeordnet, Profil ausschließlich am 12. oder 19. Januar). Planung bleibt nur
Sonntag 11. Januar, ein möglicher Dienst reicht bis Montag; feste Folgedienste
bleiben unverändert. Tägliche Ruhe 11h, Wochenruhe 36h, keine neuen Stundenmaxima.
Das zugeordnete Montagprofil sperrt den Überhang, das spätere oder nicht
zugeordnete Profil nicht. Ohne ausgewählten Überhang ist der Randkontext gültig.
Vollplanung ist im gesperrten Fall INFEASIBLE; Teilplanung liefert nur den gültigen
Fixkontext. Unabhängige Validierung bestätigt alle ausgegebenen Teilpläne.

`solver.solve` modelliert Kalenderwochenruhe direkt, rollierende Wochenruhe
weiterhin über Kandidatennachprüfung und Ausschluss. Im geprüften datierten Fall
benötigt die Kalenderregel null, jede rollierende Variante eine Separationrunde.
Das ist eine belegte Abdeckungseigenschaft, kein neuer durchgelassener Regelbruch
und keine Messung am fehlenden Originaljob. `validator.weekly_windows` erzeugt
die jeweiligen Fenster; `validate` filtert anhand der Profilgültigkeit und der
persönlichen Profilzuordnung. Gültigkeit nur am Folgetag darf daher nicht mit
„Profil am Planungsstart nicht aktiv, also irrelevant“ verwechselt werden.

`test_unknown_after_rejected_rolling_candidate_never_publishes_it` deckt nun beide
rollierenden Varianten mit einem nur am Montag gültigen Profil ab. Ein echter,
regelverletzender Modellkandidat wird über die OPTIMAL- beziehungsweise FEASIBLE-
Statusverzweigung nachgeprüft; die nächste Solverantwort wird kontrolliert auf
UNKNOWN gesetzt. In allen vier Fällen: zwei Solveraufrufe, UNKNOWN, keine
Einteilungen, Validierung nicht gültig. FEASIBLE wird hier bewusst simuliert bei
erhaltenen echten Kandidatenwerten; dies ist kein echter Zeitlimitversuch.

Verifikation: 219 gezielte Tests bestanden, Ruff und `git diff --check` grün.
Nur synthetische Tests und Analyse geändert, keine Runtime-/Importänderung,
kein Release. Die unveränderte private Kandidatenabnahme 896b3cc wurde deshalb
nicht nochmals wiederholt. Fehlende Originalartefakte, Freigaben und bestätigte
Profile bleiben unverändert offene Voraussetzungen; keine fachlichen Angaben
aus Library-/API-Statistiken ergänzt.

### Minutenreferenz für rollierende Ruhe bei Profilwechsel und Wiener DST

2026-09-11: `tests/test_rolling_window_oracle.py` ergänzt den bisherigen einfachen
UTC-Vergleich aus `test_core_rules`. 24 Kombinationen prüfen `rolling_elapsed`
mit 1-/7-Tage-Fenstern, additiver täglicher Ruhe an/aus, zugeordnetem/nicht
zugeordnetem datiertem Zusatzprofil und Winter-/Frühlings-/Herbsttermin in Wien.
Die tatsächlichen lokalen Tageslängen 1440/1380/1500 Minuten werden explizit
geprüft. Das Zusatzprofil endet am Vortag: bei aktivierter Addition und Zuordnung
muss die erforderliche Ruhe je nach Fenster zwischen beiden Werten wechseln.
Die Hauptregel gilt ausschließlich am Planungstag, entsprechend wird wie in
`validate` nach Fensterüberlappung mit ihrer Gültigkeit gefiltert.

Je Kombination werden zehn synthetische Belegungsmuster untersucht (leer,
vollständig belegt und acht deterministisch erzeugte Intervallmuster). Eine
unabhängige Zerlegung an Belegungsendpunkten bestimmt zusammenhängende Freizeit,
ohne `timeutils.longest_free` zu verwenden. Die Entscheidung über einen Verstoß
an den kritischen Fenstern aus `validator.weekly_windows` wird mit einer
minutenweisen Suche über sämtliche relevanten Fensteranfänge verglichen.
Gültige und ungültige Muster sind in jeder Kombination nachgewiesen.

Ergebnis: kein Unterschied in diesen 240 Muster-/Konfigurationsfällen. Dies ist
kein allgemeiner Vollständigkeitsbeweis, kein `rolling_local`-Nachweis und kein
Reproduktionsnachweis für den fehlenden 600-Sekunden-Originaljob. Keine neue
Runtimeänderung, keine automatische Übernahme dieser synthetischen Profile in
reale Projekte. Bestehende Library/API/OSP5-Vertragslücken und der private
Einrichtungsblocker bleiben unverändert. Deshalb keine identische API-Abnahme
wiederholt und kein Release erstellt.

### Nicht eingeplant trotz individueller Eignung: feste Arbeitszeit als Gegenbeweis

2026-09-11: `test_individual_candidates_do_not_claim_joint_feasibility` ergänzt
sechs synthetische Fälle (Voll-/Teilplanung × Wochenmaximum/tägliche Ruhe/
Überlappung). Beide Personen besitzen gültige persönliche Freigaben, Team- und
Profilzuordnung. Nur die erste hat unveränderlichen Arbeitszeitkontext. Ein
explizites synthetisches 8h-Wochenmaximum ist bereits ausgeschöpft, alternativ
verletzt der neue Dienst 11h Ruhe oder überlappt einen am Vortag begonnenen
Dienst. 36h Kalenderwochenruhe bleibt aktiviert. Dieses 8h-Maximum ist eine
Testkonfiguration, keine behauptete Nutzerregel oder importierte SP5-Grenze.

`domain.eligibility` liefert dennoch korrekt keine individuellen Ausschlüsse:
die gemeinsamen Zeitbedingungen werden in `solver.solve` und `validator.validate`
separat geprüft. Der unabhängig validierte Gegenplan für die erste Person
verletzt jeweils `weekly_limit`, `rest` oder `overlap`. Der Solver besetzt den
Bedarf vollständig mit der zweiten Person; die erste erhält korrekt
`not_selected_with_candidates`, einen Kandidaten und keine individuellen
Ausschlüsse. Der Diagnosevertrag sagt ausdrücklich „not a joint feasibility or
causal optimality proof“. Diese Kategorie darf daher weder als reine
Zielfunktionsentscheidung noch als bestätigte zusätzlich mögliche Einteilung
interpretiert werden. Die konkrete Ursache wird hier durch den synthetischen
Gegenplan nachgewiesen, nicht durch den Kandidatenzähler.

Die erste Überlappungsfixture begann versehentlich innerhalb des Planungszeitraums
und wurde zutreffend als `boundary_period` abgewiesen. Korrigiert wurde nur die
Fixture: Beginn am Vortag mit Überhang. Keine Runtimeänderung. 191 Tests aus
Teilplangrenzen, Randarbeitszeit und Kernregeln bestanden. Die unveränderte private
API-Abnahme wird nicht wiederholt; Originaljob 0.9.29 weiterhin nicht reproduziert.

### Individuelle Ausschlüsse: Gegenplan und gezielte Wiederzulassung

2026-09-11: `test_remaining_individual_exclusions_and_explicit_recovery` prüft
zwölf Kombinationen (Voll-/Teilplanung × Dienstart, Wochenende, Feiertag,
optionale Qualifikation, Anfrage-Sperre, Abwesenheit). Der explizite Gegenplan
wird jeweils mit genau dem erwarteten Ausschlusscode abgewiesen; der Solver
liefert keine Einteilung. Teilplanung bleibt gültig, aber unvollständig, und
meldet `individually_ineligible` mit dem passenden Ausschlusszähler. Nach einer
gezielten Änderung ausschließlich der synthetischen Sperre ist derselbe Bedarf
vollständig besetzt und validiert. Eine unmittelbar bei Dienstbeginn endende
Abwesenheit blockiert nicht. Eine bestätigte Anfrage (Stufe 1) erlaubt den
Dienst, aber Stufe 2 bleibt auch mit gesetztem `approved` gesperrt.

Quellkette erneut gelesen: `sp5lib/database.py:Database.get_restrictions` liest
`RESTR.RESTRICT`; `set_restriction` dokumentiert 0/1/2 als keine/Anfrage/nie.
`sp5api/routers/schedule.py:get_restrictions` reicht die Datensätze unverändert
weiter. OSP5 `frontend/src/pages/Employees.tsx` rendert bei `restrictions.map`
Name und Begründung, nicht die Stufe. Generator
`api_adapter._Database.get_restrictions` → `sp5_adapter.import_snapshot`
übernimmt die Stufe und setzt keine Anfragebestätigung voraus (`approved=False`).
`domain.eligibility` wird sowohl für Solver-Kandidaten als auch durch
`validator.validate` verwendet: die Ergebnisprüfung läuft separat, der
individuelle Ausschlussprädikat ist jedoch geteilt, also kein unabhängiger
Neuimplementierungsbeweis. Persönliche positive Freigaben bleiben zusätzlich
erforderlich. Bestehende Importtests `test_restriction_grades_retained` und
`test_import_uses_personal_approval_without_implicit_qualification_gate` sichern
die Stufenübernahme und den optionalen Qualifikationsfilter.

238 gezielte Tests bestanden; Ruff und Diffprüfung grün. Keine neue belegte
Runtimeabweichung in diesen Fällen, kein Release, keine identische private
API-Abnahme wiederholt. Die fehlende OSP5-Stufenanzeige bleibt eine belegte
Darstellungslücke, keine Erlaubnis zum Lockern einer Sperre. Nächster fachlicher
Prüfpunkt: Wochentags-/Feiertagszuordnung nativer RESTR bei über Mitternacht
reichenden Diensten gegen Library und Generator, statt weitere Wiederholung
bereits abgedeckter individueller Ausschlusscodes.

### RESTR: Starttag, Feiertagsersetzung und irreführende OSP5-Erfassung

2026-09-11: 64 synthetische HTTP-Importfälle in
`tests/test_api_adapter.py:test_http_restrictions_use_duty_start_slot_not_midnight_spill`
prüfen alle acht Dienststart-Indizes gegen alle acht RESTR-Indizes. Jeder Dienst
läuft 22–06 Uhr in Europe/Vienna, bezahlt werden absichtlich nur drei Stunden.
Bei gewöhnlichen Starttagen ist der Folgetag Feiertag; der Feiertagsstart liegt
auf einem Montag. Erwartungswerte sind explizit `restricted_slot == slot`, nicht
vom Generator abgeleitet. Keine Abweichung zwischen Library-Implementierung und
Generator-Mapping: RESTR gilt für den Starttag des konkreten Dienstes, nicht für
jeden vom Überhang berührten Kalendertag. Feiertagsindex 7 ersetzt den normalen
Wochentag; Montagindex 0 ist kein Platzhalter für alle Tage. Importierte Stufe 2
bleibt unbestätigt und hart, persönliche positive Freigaben bleiben leer.

**Nachgewiesener Quellenwiderspruch:**
`sp5lib/calculations.py:is_restricted` behauptet im Docstring, zusätzlich den
normalen Wochentag eines Feiertags zu prüfen. Seine Implementierung vergleicht
aber nur mit dem übergebenen Index, und `day_index` liefert am Feiertag nur 7.
`eligible_for_shift` übergibt genau diesen Index. Der zusätzliche Ausdruck
`weekday_index == HOLIDAY_INDEX and wd == HOLIDAY_INDEX` ist redundant und kann
keinen Montagindex rekonstruieren. Die vorhandenen Library-Tests
`test_excluded_by_restriction_on_weekday`,
`test_restriction_for_other_weekday_does_not_block` und
`test_restriction_on_holiday_uses_holiday_slot` belegen nicht die im Docstring
versprochene Vereinigung. Das ist ein Dokumentations-/Implementierungswiderspruch,
keine hinreichend belegte fachliche Erlaubnis, den Generator anders zu sperren.

**Zusätzliche konkrete Eingabelücke in OSP5:**
`frontend/src/pages/Employees.tsx:handleAddRestriction` sendet fest `weekday: 0`
und keine Stufe. `frontend/src/api/client.ts:addRestriction` reicht den Body an
`/api/restrictions` weiter. API `RestrictionCreate` definiert 0 ausdrücklich als
Montag und setzt `grade=2`; `set_restriction` gibt beide Werte an
`Database.set_restriction` weiter. `Database.get_restrictions` liest
`RESTR.WEEKDAY/RESTRICT`, der API-GET reicht sie unverändert an den Generator
weiter. Die OSP5-Liste `restrictions.map` zeigt weder Wochentag noch Stufe.
Damit erzeugt dieser UI-Pfad nachweislich eine **Montagssperre**, obwohl die
Anzeige nur eine allgemeine Schichteinschränkung erkennen lässt. Das erklärt
mögliche Erwartungsunterschiede zur Generator-Zuordnung, ist aber kein Nachweis,
dass der fehlende Originaljob 0.9.29 genau solche Daten enthält.

Priorisierte Korrektur nach fachlicher Untersuchung: OSP5 muss bei Erfassung
und Anzeige den tatsächlichen Wochentag und die Stufe explizit machen; bestehende
Montagssätze dürfen nicht rückwirkend zu globalen Sperren umgedeutet werden.
Die Feiertagsvereinigung bleibt vor einer Verhaltensänderung fachlich zu klären.
Keine Änderung an produktiver API, Originalbeständen oder fremden Checkouts.
331 gezielte Import-/Teilplan-Tests bestanden. Nur Tests und Analyse geändert;
keine identische private API-Abnahme wiederholt, kein Release. Nächster Prüfpunkt:
Sperrenzuordnung bei mehreren segmentierten Zeitfenstern und nativen
Datums-/Gruppenvarianten, einschließlich bislang nicht zuordenbarer RESTR-Sätze.

### RESTR: geteilte Dienste, Teamvarianten und nicht zuordenbare Sätze

2026-09-11: `test_http_split_duty_restriction_covers_each_group_variant`
belegt sechs HTTP-Importfälle: Stufen 0/1/2, ein/zwei Teams, zwei Zeitfenster
08–10 und 22–06 Uhr bei absichtlich nur vier bezahlten Stunden. Jeder erzeugte
Teamdienst erhält dieselbe persönliche Sperrstufe; der Nachtüberhang und die
Pause erzeugen keine zusätzlichen Freigaben und verlieren keine Sperre.

Der geprüfte Datenfluss ist `Database.get_restrictions` (RESTR-Felder
EMPLOYEEID/SHIFTID/WEEKDAY/RESTRICT) -> API `schedule.get_restrictions` ->
`APIClient.get_restrictions` -> `sp5_adapter.import_snapshot`, Schleife über
`native_restrictions`. Das Library-ORM-Modell `Restriction` und API
`RestrictionCreate` enthalten weder Datums- noch Gruppenbindung. Der Generator
expandiert den Wochentag auf konkrete Bedarfsdaten und gegebenenfalls alle
`:group:`-Varianten. Es gibt in diesem Vertrag daher keine native datierte oder
teambezogene Sperre, die stillschweigend erfunden werden dürfte. OSP5
`Employees.tsx:handleAddRestriction` benutzt denselben Vertrag.

**Belegte verbleibende Diagnoselücke:**
`test_http_unmatched_restriction_current_mapping_gap` reproduziert vier Fälle:
unbekannte/nicht ausgewählte Person, nicht erzeugter Dienst, anderer Wochentag
und ungültiger Wochentag 8. Alle werden aktuell ohne RESTR-Diagnose ausgelassen.
Die ersten drei können regulär außerhalb des gewählten Imports liegen; Index 8
ist dagegen außerhalb des dokumentierten API-Vertrags 0–7. Die Stufenprüfung
findet erst nach erfolgreicher Dienst-/Tageszuordnung statt. Das ist kein Beleg,
dass eine konkret zuordenbare gültige Sperre verloren geht, aber ein fehlender
Nachweis über verworfene Quellsätze. Diese Charakterisierung ist keine Billigung
ungültiger Quellwerte. Priorität: importbezogene Zähler/Kategorien für gültig
außerhalb Scope versus ungültig/nicht auflösbar entwerfen und erst danach
gezielt fail-closed umsetzen; legitime fremde Teams nicht pauschal blockieren.
Der Originaljob 0.9.29 bleibt für einen konkreten Kausalnachweis erforderlich.

### RESTR-Verwurfdiagnose und ungültige zugehörige Quellsätze

2026-09-11: `sp5_adapter.import_snapshot` behebt die oben charakterisierte
Diagnoselücke. `metadata.restriction_mapping_counts` zählt Quellsätze außerhalb
von Personen-, erzeugtem Dienst- und Starttag-Scope getrennt von ungültigen
Wochentagen/Stufen. `mapped_rows` zählt Quellsätze, `mapped_instances` ihre
Expansion auf konkrete Tage/Teamvarianten. Die Kategorien behaupten bei
fehlender Dienstzuordnung ausdrücklich nicht, dass die Quelle ungültig sei:
fehlender Bedarf kann ebenfalls erklären, warum kein Dienst erzeugt wurde.

Für eine ausgewählte Person und mindestens eine erzeugte Variante ihres
Quelldienstes blockiert ein Wochentag außerhalb des Integer-Vertrags 0–7 jetzt
über `unresolved`, statt die Einschränkung unbemerkt zu verlieren. Ungültige
Stufen blockieren bei passendem Starttag. Boolesche, Fließkomma- und Textwerte
werden nicht still in Integer umgedeutet. Fremde Personen/Dienste und gültige
andere Starttage bleiben außerhalb Scope; es werden weder globale Sperren noch
Freigaben erfunden. Die bestehenden Regeln für die Feiertagsauswahl bleiben
unverändert. Die Zähler enthalten keine personenbezogenen Quellzeilen.

`test_http_restriction_mapping_diagnoses_scope_and_invalid_rows` prüft 18
synthetische HTTP-Fälle, darunter ungültige Werte außerhalb der Auswahl.
`test_http_split_duty_restriction_covers_each_group_variant` prüft außerdem die
Quellsatz-/Instanzzählung bei ein/zwei Teams und allen drei gültigen Stufen.
Dies behebt einen belegten Importfehler, erklärt aber ohne Originaleingabe nicht
die gemeldeten 24-Stunden-Dienste oder Wochenüberschreitungen von 0.9.29.

Zusätzlicher Sicherheitsnachweis:
`test_invalid_imported_restriction_blocks_otherwise_valid_planning` überträgt
nur den neuen RESTR-Klärungsblocker auf ein ansonsten nachweislich lösbares
synthetisches Modell. Voll- und Teilplanung liefern danach `MODEL_INVALID`,
keine Einteilungen und ungültige Validierung. Vollsuite vor diesen beiden
Zusatzfällen: 942 bestanden; anschließend alle 176 HTTP-Adaptertests bestanden.

### RESTR ohne erzeugten Dienst: Ursachen sauber trennen

2026-09-11: `test_http_restriction_shift_scope_does_not_identify_root_cause`
prüft acht Ursachen jeweils über den HTTP-Import mit Ist- und Sollreferenz
(16 synthetische Fälle). Bestehende Transportfixture und Importdiagnosen wurden
verwendet; keine zusätzliche Mappingbibliothek oder parallele Implementierung.

| Synthetischer Quellzustand | Erzeugter Dienst / RESTR | Bestehende Diagnose |
| --- | --- | --- |
| Kein Bedarf zum bekannten Dienst | nein / nein | `outside_shift_scope`, kein eigener RESTR-Blocker |
| Bedarf nur für anderes Team | nein / nein | `outside_shift_scope`, kein eigener RESTR-Blocker |
| Bedarf nur für anderen Starttag | nein / nein | `outside_shift_scope`, **nicht** `outside_day_scope` |
| RESTR verweist auf unbekannten Dienst, regulärer Bedarf ist gültig | regulärer Dienst ja / nein | `outside_shift_scope`, kein eigener RESTR-Blocker |
| Dienststamm für zugehörigen Bedarf fehlt | nein / nein | `outside_shift_scope` plus SHDEM-Stammdatenblocker |
| Arbeitsplatzstamm für zugehörigen Bedarf fehlt | nein / nein | `outside_shift_scope` plus SHDEM-Stammdatenblocker |
| Zugehöriges Dienstzeitfenster fehlt | nein / nein | `outside_shift_scope` plus SHIFT-Zeitfensterblocker |
| Gültiger Bedarf MIN=MAX=0 | ja / ja | `mapped_rows=1`, Maximum bleibt 0 und Sperrstufe 2 bleibt erhalten |

Die Prüfung belegt: **MAX=0 ist nicht gleich fehlender erzeugter Dienst.**
Ein Referenzdienst kann wegen Nullkapazität unzuordenbar sein, obwohl seine
RESTR-Zuordnung vollständig erhalten ist. Ebenso bedeutet `outside_day_scope`
nur, dass bereits erzeugte Dienstvarianten nicht zum RESTR-Starttag passen;
es zählt nicht sämtliche fehlenden Bedarfsdaten. Die Kategorien sind nach
Verarbeitungsreihenfolge exklusiv, keine vollständige Ursacheninventur.

Quellkette: Library `sp5lib/database.py:Database.get_restrictions` behält
RESTR auch bei unbekannter SHIFT-ID; dann sind nur `shift_name/shift_short`
leer. API `sp5api/routers/schedule.py:get_restrictions` reicht diese Liste durch,
ohne Ist-/Soll-, Tages- oder Teamfilter. Generator `APIClient.get_restrictions`
und `import_snapshot` wenden erst danach Personen- und erzeugten Dienstscope
an. In `import_snapshot` entsteht der Dienst aus einem anwendbaren SHDEM/SPDEM
mit auflösbaren Stammdaten und Zeitfenstern, nicht aus RESTR oder Historie.
Die unbekannte RESTR-Referenz ist deshalb als eigener Datenqualitätsbefund
diagnostizierbar, rechtfertigt aber keine erfundene Sperre auf andere Dienste.

**Präzisierung zur OSP5-Anzeige:** Die oben belegte Erfassungs-/Anzeigelücke
betrifft `frontend/src/pages/Employees.tsx`, nicht die gesamte Anwendung.
`MitarbeiterProfil.tsx:restrictions.map` zeigt Wochentag und Stufe bereits an.
`Einschraenkungen.tsx:handleCreate` übermittelt `formWeekday` und `formGrade`;
diese dedizierte Verwaltungsseite hat entsprechende Anzeigen.
Für eine spätere Korrektur des Employees-Pfads ist der vorhandene vollständige
Vertrag zu verwenden, nicht eine neue fachliche Semantik.

Priorisierte nächste Korrektur: den bestehenden Sammelzähler um eine getrennte
Diagnose unbekannter Dienststammreferenzen ergänzen; bekannte, aber nicht
erzeugte Dienste ausdrücklich nicht als verwaist bezeichnen. Danach fehlenden
Bedarf versus verworfene Bedarfs-/Zeitfensterangaben anhand vorhandener
SHDEM/SPDEM-Provenienz aufschlüsseln. Unbekannte fremde Quellsätze nicht pauschal
zum globalen Planungsblocker machen. Originaljob 0.9.29 bleibt für den
600-Sekunden-Kausalnachweis erforderlich. Keine Runtimeänderung in diesem
Prüfschritt und keine identische private API-Abnahme wiederholt.

### RESTR-Quellreferenzdiagnose und nächste SHDEM-Lücke

2026-09-11: `sp5_adapter.import_snapshot` ergänzt
`metadata.restriction_shift_scope_counts` mit `unknown_source_shift` und
`known_shift_not_generated`. Beide sind Unterkategorien des unveränderten
`restriction_mapping_counts.outside_shift_scope`, keine zusätzlichen exklusiven
Zeilenergebnisse. Ihre Summe entspricht dem Sammelzähler. Erst wird der
Personenscope geprüft; fremde Personen werden hier nicht zusätzlich gezählt.
Es werden keine Originalzeilen oder Namen in die neuen Zähler aufgenommen.

Der Dienststamm wird bereits mit `include_hidden=True` geladen. Ein dort
bekannter, aber nicht erzeugter Dienst ist nicht automatisch eine verwaiste
Referenz. Die erneut gelesenen Quellen `Database.get_restrictions` und API
`schedule.get_restrictions` behalten dagegen tatsächlich unbekannte SHIFT-IDs.
Die bestehenden 16 HTTP-Ursachenfälle prüfen nun die getrennten Unterkategorien,
die 18 Scope-/Ungültigkeitsfälle weiterhin den exklusiven Sammelzähler. Keine
Änderung an Freigaben, Sperrstufen, Bedarfen oder Solverregeln.

Anschließender begrenzter Prüfschritt:
`test_http_invalid_requirement_weekday_is_currently_silently_not_generated`
belegt vier weitere SHDEM-Zustände (8, -1, null, String "7"): Bei ansonsten
auflösbarem Bedarf entstehen weder Dienst noch Bedarf, aber auch kein eigener
SHDEM-Blocker. Die RESTR-Unterkategorie lautet korrekt
`known_shift_not_generated`. Dies ist eine **offene Eingabevalidierungslücke**,
kein erlaubter Umgang mit ungültigen harten Bedarfen.

Quellbeleg: Library `Database.get_staffing_requirements` reicht `SHDEM.WEEKDAY`
unverändert weiter; API `master_data.get_staffing_requirements` filtert nur die
Gruppe. Dessen Schreibmodell begrenzt den Wochentag auf 0–7, aber der GET-Pfad
validiert vorhandene Quelldaten nicht darüber. Generator
`api_adapter._Database.get_staffing_requirements` prüft nur Listen/Objekte;
`import_snapshot` vergleicht anschließend `idx == row.get("weekday")`.
Nächste Korrektur: ungültige ausgewählte SHDEM-Wochentage explizit blockieren,
fremde Teams und gültige nicht passende Tage nicht global blockieren; danach
SPDEM-Vorrang und weitere Verwerfungsursachen einbeziehen. Kein Kausalnachweis
für den weiterhin fehlenden Originaljob 0.9.29.

### SHDEM-Wochentage: expliziter Importblocker statt stiller Bedarfsverlust

2026-09-11: Die oben charakterisierte Lücke ist in
`sp5_adapter.import_snapshot` korrigiert. Nach dem Teamscope und vor dem
Tagesvergleich werden reguläre Bedarfszeilen auf einen ganzzahligen Wochentag
0–7 geprüft. Auch boolesche Werte und Fließkommazahlen werden nicht implizit
als Tage interpretiert. Ungültige ausgewählte Zeilen bleiben in der vorhandenen
`unresolved_native.regular_requirements`-Provenienz erhalten und erzeugen einen
SHDEM-Blocker. Keine Ergänzung oder Lockerung von Bedarf, Freigaben oder Grenzen.

Die bestehende HTTP-Fixture belegt sechs ungültige Werte, gültige Slots 0–7
einschließlich Feiertag, einen gültigen nicht passenden Tag und ein fremdes
Team. `test_invalid_requirement_weekday_blocks_full_and_partial_plans` isoliert
den Importblocker mit ansonsten lösbarer Einrichtung: Voll- und Teilplanung
liefern `MODEL_INVALID`, keine Einteilungen und keine gültige Validierung.
`test_dated_special_requirement_keeps_precedence_without_weekday` belegt, dass
datierte SPDEM-Zeilen keinen Wochentag benötigen und ihren Vorrang behalten.
Ein ungültiger regulärer Wochentag bleibt dabei ungeklärt: Ohne gültigen Tag
kann dessen Geltungsbereich nicht zuverlässig als ersetzt nachgewiesen werden.

Quellkette erneut geprüft: `Database.get_staffing_requirements` reicht WEEKDAY
durch; API `master_data.get_staffing_requirements` filtert nur Teams, während
`StaffingRequirementSet` beim Schreiben 0–7 vorgibt. OSP5
`Personalbedarf.tsx:reqMap` übernimmt den Index, seine `WEEKDAYS`-Anzeige umfasst
acht Slots. Der Generator nutzt diese bestehende Semantik und die vorhandene
Unresolved-Sperre, keine neue Mappingbibliothek. Dieser synthetisch belegte
Defekt ist weiterhin kein Nachweis der Ursache des fehlenden Originaljobs 0.9.29.

Nächster belegter Prüfschritt: Vier HTTP-Fälle in
`test_http_requirement_counts_currently_coerce_non_integer_source_values`
zeigen, dass SHDEM-MIN/MAX `true` und `1.0` nach numerischem Vergleich vom
Demand-Modell als Ganzzahl 1 übernommen werden. Zwei Fälle in
`test_http_requirement_string_count_currently_aborts_import` belegen dagegen
für Textwerte den allgemeinen APIImportError (Vergleich vor Demand-Erstellung).
Dies ist zunächst eine Typvertrags-/Diagnose-Inkonsistenz, kein Beleg für eine
Überschreitung harter Stundenlimits. Vor einer Verschärfung native DBF-Zahltypen
und SPDEM prüfen; nicht allein aus der HTTP-Darstellung eine fachliche Grenze
ableiten. Vorhandene MIN/MAX-Sonderwertsemantik unverändert lassen.

### Numerischer Quellverlust bereits im Library-DBF-Reader

Anschließend anhand des vorhandenen Upstream-Prüfwerkzeugs belegt:
`tools/test_upstream_source_read_integrity.py` erweitert die bestehende
synthetische DBF-Bytefixture um neun MIN/MAX/WEEKDAY-Fälle. Die rohe Zahl
`nope`, ein leeres Feld und `.` werden jeweils zu Ganzzahl 0, wie eine echte
Null. Alle 16 Reader-Charakterisierungen bestehen gegen den Library-Checkout.
Quellpfad: `sp5lib.dbf_reader._parse_record_specs`, N/F-Zweig setzt bei leerem
Inhalt sowie ValueError auf 0; numerische Dezimalwerte werden abhängig von
Inhalt/Feldpräzision dagegen als float geliefert. Die Library-Methoden
`get_staffing_requirements` und `get_special_staffing` reichen MIN/MAX durch.
API-GET und Generator können eine zuvor verlorene Rohzahl nicht rekonstruieren.

Damit kann eine strengere Generator-Typprüfung allein diesen Quellverlust
nicht erkennen. Null darf nicht pauschal verboten werden: MIN=0/MAX=0 und
WEEKDAY=0 sind gültige, unterschiedlich bedeutsame Angaben. Ein nachfolgender
Korrekturschritt muss den bestehenden Reader-Integritätsvertrag und dessen
strikten Kandidaten prüfen, Fehlerprovenienz erhalten und Library/API gemeinsam
berücksichtigen. Keine Änderung am produktiven Reader oder API-Bestand in
diesem Prüfschritt. Keine Behauptung, dass die private Quelle solche Werte
enthält oder dies den gemeldeten 0.9.29-Plan verursacht hat.

### Strikter Zahlenlesepfad: isolierter Korrekturkandidat

Der vorhandene `upstream-library-strict-reader-candidate.patch` prüft jetzt
N/F-Felder aktiver Datensätze vor Ausgabe des Ergebnisses. Der opt-in Pfad
`read_dbf_buffer(strict=True)` unterscheidet `missing_numeric_value`,
`invalid_numeric_value` und `nonfinite_numeric_value`; Meldungen enthalten
weder Feldinhalt noch Personen-/Dateiangaben. Ein gültiger Präfix wird bei
späterem Zahlenfehler nicht zurückgegeben. Gelöschte Datensätze bleiben
ordnungsgemäß ausgenommen. Echte Null, negative Werte und Dezimalzahlen
bleiben unverändert: Der Reader erfindet keine MIN/MAX-/Wochentagsregeln.

42 zusätzliche synthetische Fälle in `tools/test_upstream_strict_reader.py`
prüfen MIN/MAX/WEEKDAY als N/F, leere/dot/nichtnumerische/nicht-ASCII/nichtendliche
Werte, gültige Zahlen, gelöschte Sätze und die Weitergabe durch
`StrictSourceTables` trotz bereits mit falscher Null gefülltem Legacycache.
Mit den vorhandenen Reader- und Selektionsprüfungen: **109 Tests bestanden**.

Wichtig: Leerwerte sind im strikten Kandidaten ausdrücklich ungeklärte Werte,
nicht nachweislich beschädigte Originaldaten. Vor produktiver Integration
muss der Tabellen-/Feldvertrag klären, wo leere Zahlen legitime optionale
Angaben sind; sie dürfen nicht global als fachliche Null interpretiert werden.
Dieser Patch bleibt isoliert, produktive Library/API und Generatorlaufzeit
unverändert. `StrictSourceTables` reicht die Kategorie weiter, ein produktiver
API-Fehlervertrag ist damit noch nicht implementiert. Der normale Readerpfad
bleibt kompatibel. Kein erneuter identischer privater Release-Test nötig;
keine Aussage über Vorkommen dieser Quellwerte in echten Daten oder die Ursache
des weiterhin nicht vorliegenden Originaljobs 0.9.29.

### Gegenprobe: leere Zahlen entstehen auch im vorhandenen Schreibpfad

`sp5lib.dbf_writer._encode_field` schreibt für `None` ausdrücklich Leerzeichen;
der N/F-Zweig schreibt bei ValueError/TypeError dieselben Bytes.
`append_record` verwendet `record.get(fname)`: Auch ein ausgelassenes Feld wird
damit leer geschrieben. Neun zusätzliche synthetische Regressionen im
Strict-Reader-Test prüfen N/F mit None/leerem Text/ungültigem Text sowie echte
Dateianhänge mit ausgelassener ID, None und expliziter Null. Der Legacyreader
liefert in allen drei Anhangfällen 0; der Kandidat unterscheidet explizite Null
von fehlender Zahl, kann aber die Herkunft der fehlenden Zahl nicht erkennen.
**Ein Leerfeld ist damit kein ausreichender Beleg für Dateibeschädigung.**
Das belegt noch nicht, dass MIN/MAX/WEEKDAY fachlich optional sind.

Der konkrete Bedarfs-Schreibvertrag ist enger: `SP5Database.set_staffing_requirement`
füllt bei Neuanlage ID/GROUPID/WEEKDAY/SHIFTID/WORKPLACID/MIN/MAX ausdrücklich
(WORKPLACID=0). `create_special_staffing` füllt die entsprechenden datierten
Felder einschließlich MIN/MAX ebenfalls. In API `routers/master_data.py`
verlangt `StaffingRequirementSet` min/max und weekday; `SpecialStaffingCreate`
setzt ausgelassene min/max ausdrücklich auf 0. `SpecialStaffingUpdate` erlaubt
None, aber die Route `update_special_staffing` filtert None vor dem DB-Aufruf:
None bedeutet dort keine Änderung, nicht Zahl löschen. OSP5
`frontend/src/api/client.ts` bietet diese drei Schreibaufrufe an;
`pages/Personalbedarf.tsx` verwendet sie beim Speichern der regulären bzw.
datumsbezogenen Bedarfe. Diese Quellbelege rechtfertigen keine globale
Leerwert-Ablehnung aller Tabellen und keine zusätzlichen Personalregeln.

Prüfung: **118 Reader-/Schreib-/Bridge-Tests bestanden**, Ruff und diff-check
grün. Für die Bridge-Tests ist der vorhandene **Worktime-Contract-Kandidat**
als `SP5_WORK_TIME_ROUTER` erforderlich, nicht der unveränderte API-Router
(dessen Selektor hat noch nicht die erforderliche plan-Signatur):

```sh
PYTHONPATH=/home/hilbert/projects/libopenschichtplaner5:tests:tools \
SP5_STRICT_READER=/tmp/sp5-numeric-reader-candidate/sp5lib/dbf_reader.py \
SP5_WORK_TIME_ROUTER=/tmp/sp5-worktime-contract/sp5api/routers/work_time_rules.py \
.venv/bin/python -m pytest -q tools/test_upstream_strict_reader.py tools/test_upstream_source_read_integrity.py
```

Keine Runtimeänderung/Release, keine produktiven Schreibzugriffe. Nächste
Integration muss Feldvollständigkeit von struktureller Integrität trennen und
ungeklärte Pflichtzahlen als quellfreie API-Diagnose erhalten. Die gemeldete
0.9.29-Planung bleibt ohne Originaljob nicht kausal reproduziert.

### Strukturfehler und ungeklärte Zahlen getrennt (isolierter Kandidat)

Der strikte Reader-Kandidat verwendet jetzt `DBFValueError` für fehlende,
ungültige und nichtendliche Zahlen. `DBFStructureError` bleibt ausschließlich
für Header-/Datensatzstrukturfehler; `DBFReadError` für fehlende/unlesbare
Dateien. `_validate_dbf_structure` prüft zuerst die **gesamte** Struktur,
`_validate_dbf_numbers` anschließend die Zahlen. Ein später ungültiger
Datensatzmarker wird damit nicht mehr durch ein früheres Leerfeld verdeckt.
Strukturell gültig bedeutet weiterhin nicht fachlich vollständig.

18 zusätzliche synthetische Regressionen belegen diese Unterscheidung und
den Durchstich durch die echten Library-Methoden
`SP5Database.get_staffing_requirements` (SHDEM) sowie `get_special_staffing`
(SPDEM): MIN/MAX mit expliziter Null bleiben Null, Leer-/Textwerte liefern im
Legacy-Pfad irreführend Null und im strikten Pfad eine quellfreie Wertkategorie.
Die Tests verwenden ausschließlich erzeugte Dateien und keine produktiven
Schreibzugriffe. **136 Reader-/Writer-/Library-Bridge-Tests bestanden.**

API-Integrationslücke bleibt ausdrücklich offen: In `routers/master_data.py`
reicht `get_staffing_requirements` Library-Ausnahmen ungefangen weiter;
`get_special_staffing` fängt jede Exception über `_sanitize_500` ab. Eine neue
Library-Fehlerklasse allein ist daher **noch kein stabiler API-Fehlervertrag**.
Vor Integration müssen beide GET-Routen dieselben quellfreien Kategorien
transportieren, ohne eine kaputte Teilantwort oder einen gültigen Nullbedarf
vorzutäuschen. Der Kandidat bleibt opt-in und wird nicht global eingesetzt:
Die Frage optionaler numerischer Felder außerhalb dieses Bedarfsvertrags ist
nicht geklärt. Kein Runtimefix/Release und kein Nachweis, dass diese Quellwerte
im Originaljob 0.9.29 vorkamen.

### Bedarfsfehler: Library → API → Verbraucher (isolierter HTTP-Kandidat)

`tools/upstream-api-staffing-source-contract-candidate.patch` ergänzt in
API `routers/master_data.py` den gemeinsamen Helfer `_staffing_source_error`.
Die beiden GET-Funktionen `get_staffing_requirements` und
`get_special_staffing` liefern für die drei strikten Library-Fehlerklassen
HTTP 500 mit `detail.code=staffing_source_unresolved` und einer festen
Kategorie `numeric_value`, `structure` oder `read`. Es werden weder
Exceptiontext/-code noch Dateipfad oder Feldinhalt übernommen. Bekannte
Quellfehler gehen nicht durch den allgemeinen Fehlerlogger; unbekannte
Ausnahmen behalten `_sanitize_500`. Ein gültiger Präfix wird nicht als
erfolgreicher Bedarf zurückgegeben. Echte Null und gültige leere Tabellen
bleiben erfolgreiche Antworten. Gruppenfilter und Query-Weitergabe bleiben
unverändert.

**33 neue synthetische Regressionen** in
`tools/test_upstream_staffing_source_contract.py` führen erzeugte DBF-Dateien
durch die tatsächlichen Library-Bedarfsfunktionen und die extrahierten
Kandidaten-GET-Funktionen mit ihren echten FastAPI-Dekoratoren im ASGI-Test.
MIN/MAX leer, ungültig und nichtendlich, echte Null, fehlende Datei,
abgeschnittener Datensatz, quellfreie Fehlermeldungen, gültige Leerquellen
und Filterweitergabe sind abgedeckt. Die letzten zwei Tests führen die
ASGI-Antwort über einen lokalen Transport zum echten Generator
`APIClient.get/_read`: HTTP 500 bricht mit `APIImportError` ab und erzeugt
keinen Cacheeintrag; ein späterer erfolgreicher Retry liest neu.
Zusammen mit Reader-/Library- und bestehenden API-Adapter-Tests:
**379 Tests bestanden**, Ruff, diff-check und Patch-Dry-run grün.

Die Verbraucherdiagnose ist noch nicht vollständig: Generator
`sp5generator/api_adapter.py:APIClient._read` zeigt bei HTTP 500 nur seine
generische Zugriffs-/Versionsmeldung, nicht die Quellkategorie. OSP5
`frontend/src/api/client.ts:extractErrorMessage` verwendet `String(data.detail)`;
ein strukturiertes Detail würde deshalb als `[object Object]` erscheinen.
`pages/Personalbedarf.tsx` fängt den Fehler sowohl im regulären `Promise.all`
als auch im datierten `load` ab, interpretiert ihn also nicht als erfolgreiche
Bedarfsliste. Eine verständliche kategorisierte Diagnose bleibt vor Integration
erforderlich; dies ist ein belegter Vertragskonflikt, kein neuer UI-Auftrag.

Reproduzierbarer Testaufruf nach Anwendung der beiden Kandidaten in isolierten
Verzeichnissen (der API-Patch benötigt die neuen Library-Fehlerklassen):

```sh
PYTHONPATH=/home/hilbert/projects/libopenschichtplaner5:tests:tools \
SP5_STRICT_READER=/tmp/sp5-numeric-reader-candidate/sp5lib/dbf_reader.py \
SP5_STAFFING_ROUTER=/tmp/sp5-staffing-api-contract/sp5api/routers/master_data.py \
SP5_WORK_TIME_ROUTER=/tmp/sp5-worktime-contract/sp5api/routers/work_time_rules.py \
.venv/bin/python -m pytest -q tools/test_upstream_staffing_source_contract.py \
tools/test_upstream_strict_reader.py tools/test_upstream_source_read_integrity.py \
tests/test_api_adapter.py
```

Die Routen aktivieren striktes Lesen ausdrücklich **nicht** global. Tests
injizieren die vorhandene `StrictSourceTables`-Brücke; produktive Library,
API und Generatorlaufzeit bleiben unverändert. Vollständiger API-Appstart,
Authentifizierung und produktive v1-Routenregistrierung sind durch den
isolierten ASGI-Test nicht abgenommen. Kein Release, keine erneute identische
Privatabnahme und weiterhin kein Originaljob-Nachweis für die 0.9.29-Meldung.


### Kompatibler Bedarfsfehlervertrag für den bestehenden OSP5-Verbraucher

Der isolierte API-Kandidat wurde korrigiert: `detail` ist jetzt ein fester,
verständlicher String, die maschinenlesbaren Werte stehen in
`X-SP5-Error-Code: staffing_source_unresolved` und
`X-SP5-Error-Category: read|structure|numeric_value`. Damit ersetzt dieser
Abschnitt das oben beschriebene Objekt unter `detail`. Es werden weiterhin
keine Quelldateinamen, Exceptiontexte oder Feldinhalte übertragen. Die
Antwort bleibt HTTP 500, niemals ein erfolgreicher leerer Bedarf.

`tools/audit_upstream_staffing_error.cjs` extrahiert mit dem vorhandenen
TypeScript-Parser die **unveränderte** Funktion `extractErrorMessage` aus
OSP5 `frontend/src/api/client.ts`, transpiliert sie und führt sie mit der
jeweiligen tatsächlichen synthetischen ASGI-JSON-Antwort als `Response` aus.
Sechs neue Regressionen (beide GET-Routen × drei Kategorien) belegen die
lesbare Meldung statt `[object Object]`. Insgesamt 39 Vertragstests bestanden.
Dies ist ein Funktionsvertragstest, keine Browser- oder vollständige
App-/Auth-Abnahme. Die Header benötigen für spätere browserseitige
maschinenlesbare Cross-Origin-Auswertung gegebenenfalls CORS-Exposition;
der bestehende OSP5-Verbraucher benötigt sie nicht und liest den JSON-Text.

Für den obigen Testaufruf zusätzlich setzen:
`SP5_OSP5_FRONTEND=/home/hilbert/projects/openschichtplaner5/frontend`.
Node und die dort vorhandene TypeScript-Abhängigkeit sind erforderlich.

Generator `APIClient._read` bricht weiterhin korrekt ab und cached keine
Fehlerantwort, zeigt aber noch die generische HTTP-500-Meldung. Nächste
Integration: ausschließlich bekannte Fehlercodes/Kategorien auf feste lokale
Meldungen abbilden; keine ungeprüften fremden Fehlertexte anzeigen. Danach
strikte Pflichtfeldprüfung gezielt in SHDEM/SPDEM integrieren. Keine globale
Zahlenpflicht ohne Vertrag optionaler Felder. Produktive Upstream-Repositories
und Generatorlaufzeit bleiben unverändert; daher keine identische erneute
Privatabnahme. Kein Release und kein Kausalnachweis für den Originaljob 0.9.29.

### Generator-Verbraucher des quellfreien Bedarfsfehlervertrags

`APIClient._read` interpretiert jetzt ausschließlich HTTP 500 der beiden
Bedarfs-Endpunkte mit `X-SP5-Error-Code=staffing_source_unresolved` und einer
bekannten Kategorie `read`, `structure` oder `numeric_value`. Es verwendet
feste lokale Meldungen samt Importabbruch, weder fremde Headertexte noch den
Responsebody. Unbekannte Kategorien, andere Endpunkte/Statuscodes und fehlende
Header behalten die allgemeine Fehlermeldung. Keine leere Ersatzliste und
kein Fehlercache; ein erneuter Aufruf liest erneut. Queryparameter der
Sonderbedarfsroute und die normale Groß-/Kleinschreibungsunabhängigkeit von
HTTP-Headern sind abgedeckt.

Elf neue Transportregressionen in `tests/test_api_adapter.py` prüfen bekannte
Kategorien, negative Vertragsfälle und zwei fehlgeschlagene Leseversuche.
`test_generator_aborts_and_does_not_cache_failed_source` reicht jetzt die
tatsächlichen synthetischen ASGI-Header weiter und prüft die Zahlenwertdiagnose
bis zum Generator. Der produktive Upstream unterstützt diesen Kandidatenvertrag
noch nicht; normale vorhandene Antworten werden nicht umgedeutet.

### Nachgewiesene verbleibende Pflichtspaltenlücke

Vier neue Charakterisierungstests
`test_missing_count_column_currently_becomes_zero` zeigen: Selbst mit dem
strikten Reader-Kandidaten wird eine **fehlende** MIN- oder MAX-Spalte einer
synthetischen SHDEM-/SPDEM-Datei nicht erkannt. Der Reader prüft vorhandene
Feldbeschreibungen und Zahlenbytes. Anschließend ersetzen Library
`SP5Database.get_staffing_requirements` und `get_special_staffing` durch
`r.get("MIN", 0)` / `r.get("MAX", 0)` die fehlende Spalte durch Null. Die
isolierten API-Routen liefern HTTP 200. Dies ist keine Freigabe dieses Defaults,
sondern ein reproduzierbarer Restfehler vor der geplanten Tabellenvertragsprüfung.

Damit reicht ein strikter Zahlenparser allein nicht: SHDEM/SPDEM benötigen
gezielte Pflichtspaltenprüfung vor dem Library-Mapping. Explizite Null muss von
fehlender Spalte unterscheidbar bleiben, insbesondere weil Generator
`import_snapshot` MAX=0 als keine Besetzung und MAX=-1 als unbegrenzt behandelt.
Leere gültige Tabellen dürfen nicht pauschal als defekt gelten; ein globaler
Pflichtvertrag für alle numerischen Spalten wäre weiterhin unbegründet.
Keine Aussage, dass die echte 0.9.29-Eingabe diese fehlenden Spalten enthält.

### Opt-in Pflichtspaltenvertrag für Bedarfszahlen

Der isolierte Reader-Kandidat akzeptiert jetzt `required_fields=("MIN", "MAX")`
bei `read_dbf` und `read_dbf_buffer`. Er prüft die Feldbeschreibungen nach der
Strukturprüfung, vor dem Library-Mapping: jede angeforderte Spalte muss genau
einmal vorhanden sein. Fehlende oder doppelte Pflichtspalten führen zu
`DBFStructureError("required_column_missing_or_duplicate")`, ohne Quellinhalt.
Der Vertrag gilt auch bei null Datensätzen oder ausschließlich gelöschten
Datensätzen; eine Prüfung nur der zurückgegebenen Dictionaries wäre unzureichend.
Ohne `required_fields` bleibt das bisherige Verhalten unverändert. Es wird
kein globaler Pflichtspaltenvertrag für andere Tabellen behauptet.

`test_explicit_staffing_column_contract` injiziert diesen Vertrag gezielt für
SHDEM bzw. SPDEM vor die echte Library-Mappingfunktion und die isolierte
API-Route. 24 neue Fälle prüfen fehlende/doppelte Spalten sowie korrekte leere,
gelöschte und explizite Null-Datensätze. Die bestehenden vier
Charakterisierungstests ohne Opt-in bleiben als Nachweis der ursprünglichen
Lücke erhalten. Der API-Kandidat liefert bei Verletzung die bereits geprüfte
quellfreie HTTP-500-Strukturdiagnose, niemals erfundenen Nullbedarf.

557 Tests bestanden: Bedarfsvertrag, strikter Reader, ursprüngliche
Quellintegrität, API-Adapter, Teilplan- und Kalendergrenzen. Der erste lokale
Testaufruf hatte eine fehlende Test-Umgebungsvariable; der vollständige Aufruf
mit `SP5_WORK_TIME_ROUTER` ist grün. Produktive Library/API und Generatorruntime
wurden nicht geändert; keine identische private API-Wiederholung, kein Release.
Nächster Integrationsschritt: gezielte Aktivierung im isolierten vollständigen
API-App-/Auth-Pfad statt nur injizierter Routerprüfung. Feldtypen und weitere
Bedarfs-Identitätsspalten sind damit noch nicht vollständig vertraglich geprüft.
Originalprojekt, Jobeingabe und Ergebnis 0.9.29 fehlen weiterhin; dieser Befund
belegt nicht die Ursache der gemeldeten 600-Sekunden-Planung.

### Pflichtspalten sind noch kein Zahlenvertrag

`test_required_count_column_wrong_type_is_not_yet_rejected` ergänzt zwölf
synthetische DBF→Library→API-Charakterisierungen: SHDEM/SPDEM, jeweils MIN oder
MAX als DBF-Typ C, mit `0000`, Leerzeichen oder `nope`. Auch bei `strict=True`
und `required_fields=("MIN", "MAX")` liefert der Reader Strings. Die Library
reicht sie in `get_staffing_requirements` bzw. `get_special_staffing` unverändert
weiter; beide isolierten API-Routen antworten HTTP 200. Die numerische Prüfung
des Readers gilt nur für numerisch deklarierte Spalten; die Pflichtprüfung
kontrolliert bisher Namen und Eindeutigkeit, nicht Typen.

Generator `sp5_adapter.import_snapshot` prüft MIN/MAX bisher auf None und
vergleicht danach MAX mit -1 bzw. MIN. Dieser Codepfad benötigt einen expliziten
Zahlenvertrag vor Vergleichen, statt Quellstrings stillschweigend umzuwandeln.
Dies ist eine getrennte Restlücke neben fehlenden Spalten. Der jetzige Test
belegt die HTTP-Grenze, nicht einen vollständigen Generatorimport oder den
vollständigen API-App-/Auth-/v1-Pfad. Keine Behauptung, dass echte Quelldaten
diese Typverletzung enthalten oder sie die gemeldeten Wochenstunden erklären.

Priorität: vor Aktivierung des Kandidaten Bedarfszahlen mit einem gezielten
Typvertrag prüfen und Generator-Fehlerdiagnose absichern; anschließend den
vollen API-Pfad prüfen. Gültige Null, leere Tabellen und ausdrücklich
unbegrenztes MAX=-1 müssen erhalten bleiben. Keine globale Typvorgabe für alle
DBF-Felder und keine neue Arbeitszeitregel daraus ableiten.

212 Tests bestanden (Bedarfsvertrag, Teilplangrenzen, Kalendergrenzen). Der erste
Aufruf hatte sechs reine Harnessfehler wegen fehlendem `SP5_OSP5_FRONTEND`;
der korrigierte Aufruf ist grün. Für diese Tests immer zusätzlich zu
`SP5_STRICT_READER`, `SP5_STAFFING_ROUTER`, `SP5_WORK_TIME_ROUTER` auch
`SP5_OSP5_FRONTEND=/home/hilbert/projects/openschichtplaner5/frontend` setzen.
Keine Runtimeänderung, kein Release und keine Wiederholung der unveränderten
privaten API-Abnahme.

### Gezielter numerischer DBF-Spaltenvertrag (isolierter Kandidat)

Der Reader-Patch erweitert beide Lesewege um opt-in
`numeric_fields=("MIN", "MAX")`. Angeforderte Spalten müssen genau einmal
vorhanden und als numerischer DBF-Typ N oder F deklariert sein. Andere Typen
werden vor dem Mapping als `required_numeric_column_type` abgewiesen,
auch bei leeren oder ausschließlich gelöschten Tabellen. Bestehendes
`required_fields` bleibt ein reiner Präsenzvertrag; ohne Opt-in ändert sich
nichts. Zusammen mit `strict=True` greift zusätzlich die vorhandene
Prüfung numerischer Inhalte. Der Typvertrag allein ist noch keine Prüfung
ganzzahliger, fachlich gültiger Besetzungszahlen.

`test_explicit_numeric_staffing_contract` prüft 80 synthetische
DBF→Library→isolierte API-Fälle: SHDEM/SPDEM, MIN/MAX, C/L/D/N/F,
leere/gelöschte Datensätze, echte Null sowie MAX=-1. Falsche Typen ergeben
die quellfreie HTTP-500-Strukturdiagnose; gültige Null und unbegrenztes
MAX bleiben unverändert. Die zwölf bisherigen Charakterisierungen ohne
numerischen Opt-in bleiben erhalten.

Dies ist nur ein isolierter Korrekturkandidat, keine Änderung der produktiven
Library/API oder Generatorruntime und kein Nachweis der Ursache des
0.9.29-Teilplans. Offen bleiben die Generatorprüfung vor Zahlenvergleichen,
der ganzzahlige Wertevertrag sowie die Integration im vollständigen
API-App-/Auth-/v1-Pfad.

Prüfnachweis: 412 Tests grün (Bedarfsvertrag, strikter Reader, Teilplan- und
Kalendergrenzen), Ruff, diff-check und Patch-Dry-run grün. Zwei anfängliche
Harnessfehler wurden korrigiert: pytest als `python -m pytest` starten und
`SP5_WORK_TIME_ROUTER=/tmp/sp5-worktime-contract/sp5api/routers/work_time_rules.py`
verwenden; der normale Checkout besitzt keinen `work_time.py`.
Für diesen Lauf:
`SP5_STRICT_READER=/tmp/sp5-count-contract/sp5lib/dbf_reader.py`.
Die unveränderte private API-Abnahme wurde nicht wiederholt.

### Teilplan: ISO-Jahreswechsel mit festem Randdienst und UTC-Datumsabweichung

`tests/test_partial_limits.py:test_iso_year_local_midnight_with_fixed_context`
ergänzt acht synthetische Fälle für vollständige und partielle Planung. Der
01.01.2027 gehört noch zur ISO-Woche ab 28.12.2026: zwei Stunden fester
Randdienst am Vortag plus zwei Stunden neuer Dienst ergeben 240 reale Minuten.
Am 04.01.2027 beginnt hingegen eine neue ISO-Woche; dort zählen nur die
120 neuen Minuten. Der neue Dienst beginnt jeweils lokal um 00:30, also am
vorherigen UTC-Datum. Erwartungswerte werden ausdrücklich vorgegeben und nicht
aus dem Tagesminuten-Helfer übernommen. Beide Dienste haben nur eine bezahlte
Minute und die Person ein großes Soll; beides darf die harte Grenze nicht
verändern. Die konfigurierte tägliche Ruhe beträgt 660 Minuten.

`solver.solve` summiert `dates_by_shift` je lokalem Tag und Wochenmontag,
einschließlich fester Randdienste. `validator.validate` prüft dieselben
relevanten Kalenderwochen über `daily`, getrennt vom Sollkonto. Bei exakt
passender Grenze bleiben beide Einteilungen erlaubt; eine Minute darunter
weist der Validator die richtige Wochenüberschreitung aus, der Vollsolver
meldet INFEASIBLE und der Teilsolver lässt den neuen Bedarf offen. Der feste
Randdienst bleibt erhalten. Keine neue Wochenhöchstgrenze wird als Default
festgelegt.

177 Tests bestanden (Teilplangrenzen, Kalendergrenzen, datierte Kalenderruhe),
Ruff und diff-check ebenfalls. Kein neuer Fehler in diesen Fällen, keine
Runtimeänderung und kein Release. Die unveränderte private API-Abnahme wird
nicht wiederholt. Originalprojekt/Jobeingabe/Ergebnis des gemeldeten
0.9.29-Laufs sind weiterhin nicht verfügbar; dieser Test ist kein Nachweis
für dessen Ursache und keine Reproduktion des 600-Sekunden-Zeitlimits.
# Generator staffing count boundary: characterization (2026-09-11)

Following the DBF numeric-column candidate, twelve synthetic HTTP-import cases
now locate the remaining generator boundary precisely:

- `api_adapter.import_api` -> `sp5_adapter.import_snapshot` compares `max` with
  `-1` and `min` before validating their types. Text in either field (`"0"`,
  empty text or nonnumeric text) produces the generic API import-contract error,
  rather than a local staffing-field diagnosis.
- Boolean `true` and integral float `1.0` survive those comparisons and Pydantic
  `Demand` construction as integer 1. This demonstrates coercion, not evidence
  that upstream booleans are legitimate staffing counts.
- Fractional `1.5` reaches `Demand`, is rejected, and is caught by the surrounding
  shift-construction `ValueError` handler. The unresolved diagnostic incorrectly
  starts with `SHIFT`, although the invalid field belongs to staffing; no demand
  is created. The snapshot remains unresolved, not a validated plan.

Evidence: `tests/test_api_adapter.py` tests
`test_staffing_text_counts_currently_fail_before_local_diagnosis`,
`test_staffing_boolean_and_integral_float_counts_currently_coerced` and
`test_fractional_staffing_count_currently_reported_as_shift_error`.
These intentionally characterize current behavior pending the corrective change.
Focused API-adapter plus partial-limit run: **347 passed**; Ruff and diff check pass.

Next correction: validate staffing values before comparisons, reject booleans,
text and fractional/nonfinite values without echoing raw source values; settle
integral JSON-number normalization consistently with DBF N/F output, retain
MAX=-1 and zero semantics, and preserve blocking unresolved source rows. Cover
both regular and dated staffing before private API revalidation. This is a
mapping/diagnostic finding, not a proven cause of the user's 0.9.29 partial plan;
the exact original job/project/result is still unavailable. No runtime change
or release was made for this characterization.

## Generator staffing count correction (2026-09-11)

The characterization above is now superseded by a runtime correction in
`sp5_adapter.import_snapshot`, immediately before staffing comparisons and
`Demand` construction. Both SHDEM and dated SPDEM accept integer values and
finite integral floats (the numeric DBF/JSON representation), but reject
booleans, strings, fractions and nonfinite values. Negative MIN is rejected;
MAX=-1 remains unbounded, MAX=0 remains zero capacity, and MAX below MIN remains
unresolved. No upper bound or personal approval is invented.

Invalid rows produce a local staffing-field diagnostic (SHDEM/SPDEM and MIN/MAX),
not a SHIFT time-window error. Source values are not echoed in that diagnostic.
Original rows remain in local unresolved metadata. An invalid dated override
still occupies its source cell: it cannot silently fall back to the regular
requirement. Full and partial solve both remain MODEL_INVALID for unresolved
staffing, even when the unrelated profile confirmation blocker is removed in
the synthetic fixture. The HTTP JSON parser already rejects NaN/Infinity before
mapping; direct Library imports are covered separately at the mapping boundary.

Data flow remains `database.get_staffing_requirements/get_special_staffing`
(SHDEM/SPDEM MIN/MAX) -> API `master_data` read routes -> generator API facade ->
shared `import_snapshot`. Validation on an API **write** model is not validation
of its read response. Existing source-contract tools and regression fixtures
were reused; no replacement reader/library or UI component was introduced.

Evidence: `test_invalid_staffing_counts_block_with_field_diagnosis`,
`test_integral_numeric_staffing_preserves_bounds` (HTTP regular/dated paths),
`test_direct_library_invalid_counts_do_not_reach_shift_builder` (direct source),
and the existing partial-limit suite. Focused run: **462 passed**. This fixes a
proven boundary defect, not a proven cause of the reported 600-second 0.9.29 run.
Original job/project/result are still missing. No new release is claimed.

OSP5 consumer evidence: `frontend/src/api/client.ts` declares numeric
`ShiftRequirement.min/max` and fetches `/api/v1/staffing-requirements`;
`Personalbedarf.tsx` builds its weekday matrix from `shift_requirements`.
Those TypeScript declarations do not validate JSON at runtime. The corrected
Generator boundary is therefore necessary even with a typed OSP5 consumer;
it does not repair missing/incorrect source fields already defaulted upstream.
The separate strict DBF-reader/API candidates remain outstanding.

### Full API middleware contract for staffing candidates (2026-09-11)

`tools/test_upstream_staffing_full_app.py` now imports the complete upstream
`sp5api.main.app`, with the isolated master-data router/strict-reader candidates.
It copies **only Python source**, uses a fresh subprocess environment and
throwaway backend, and never imports upstream test fixtures or `.env` files.
The existing upstream TestClient/session-injection pattern is reused without
its potentially real DBF fixture copying.

Evidence across `/api` and `/api/v1`, regular SHDEM and dated SPDEM:

- Real auth middleware rejects absent/invalid/removed synthetic sessions (401).
- Real version-prefix middleware preserves the candidate's HTTP 500 error
  category headers and source-free message; only unversioned responses carry
  the deprecation header.
- Missing MIN/MAX schema, blank numeric cells and unreadable sources remain
  errors through Library mapping and the complete HTTP middleware stack.
- Generator `APIClient.get` rejects these responses without caching them;
  a subsequent valid source is actually read. Explicit zero, MAX=-1 and empty
  valid tables remain successful; no invented demand or permission is added.

Run with `SP5_API_SOURCE` (API checkout), `SP5_STAFFING_ROUTER` (candidate file),
`SP5_STRICT_READER` (candidate file); the combined existing router suite also
needs `SP5_OSP5_FRONTEND`. Combined result: **161 passed**, two known dependency
deprecation warnings; Ruff passed.

Scope limits: no lifespan startup/migrations/background schedulers are run;
no credential login is tested (session injected), and numeric-reader activation
is explicitly injected on SHDEM/SPDEM, **not yet shipped upstream**. This closes
the middleware/auth/versioning test gap, not the original 0.9.29 reproduction
gap or an end-to-end production deployment gate. Runtime remains unchanged.

### Reviewable staffing activation candidate (2026-09-11)

The full-app contract now compares test injection with actual constructor/factory
activation. `tools/upstream-library-staffing-activation-candidate.patch` adds
`SP5Database(..., strict_staffing=False)`; when explicitly enabled, `_read` uses
the existing strict DBF reader for SHDEM/SPDEM MIN/MAX only. It bypasses the
shared permissive cache rather than trusting previously unvalidated parses.
`tools/upstream-api-staffing-activation-candidate.patch` enables that option in
`dependencies.get_db` for the DBF backend. The PostgreSQL branch is unchanged
and **not validated by this candidate**. Both patches require the previously
reviewed strict-reader and staffing-error-router candidates; neither is deployed.

`test_upstream_staffing_full_app.py` loads the candidate database source and
copies the candidate dependencies into the isolated API package. In this mode
there is no replacement of `SP5Database._read`. Both API prefixes still enforce
auth and retain source-error categories. A legacy instance first warms the
permissive global cache with each synthetic source; strict instances still reject
missing columns and blank numeric values. Valid zero, MAX=-1, empty tables and
retry after source repair retain their prior behavior. Constructor opt-in defaults
to false, preserving existing Library callers. Strict reads deliberately reread
these two tables; performance/cache optimization is not claimed.

Additional harness inputs: `SP5_STAFFING_DATABASE` and
`SP5_STAFFING_DEPENDENCIES` point to isolated files produced by the new patches.
Combined full-app/source-contract/partial-limit run: **293 passed**, two known
dependency warnings. Both new patches pass `git apply --check` against the
existing upstream checkouts. No production source or Generator runtime changed;
no identical private API recheck or release was performed. Next source-contract
work remains identity/scope fields; the original 0.9.29 job/project/result and
its 600-second causal reproduction remain unavailable.

### Missing staffing identity can be filtered away (2026-09-11)

Synthetic DBF evidence now distinguishes structural identity loss from valid
MIN/MAX values. `test_missing_staffing_identity_survives_count_contract` removes
one of GROUPID, SHIFTID, WORKPLACID, keeping present values and both counts at 1:

* Library `SP5Database.get_staffing_requirements` maps absent descriptors with
  `r.get(...)` to null `group_id`, `shift_id` or `workplace_id`. The API regular
  staffing route explicitly retains null group IDs even with `group_id=1`.
* Library `SP5Database.get_special_staffing` also maps absent identities to null,
  but applies `r.get("GROUPID") != group_id` **before** returning rows. With a
  missing GROUPID descriptor, the same special source gives one unfiltered row
  but **HTTP 200 with an empty list** for `group_id=1`.
* Generator `api_adapter._Database.get_special_staffing` forwards the selected team as
  `group_id`; this source row can therefore disappear before Generator validation.
  The regular import's null-group diagnostic cannot repair a special row it
  never receives. Existing OSP5 error handling cannot display a source error
  when the API returns success (its error path is separately tested above).

The count-only strict activation candidate does not close this gap. A paired
synthetic test enables the existing reader's `required_fields` for those three
identity descriptors: both routes then return the categorized `structure` error,
with and without the team filter. This proves a bounded correction mechanism
without inventing global-team or zero-ID semantics. It is **test opt-in only**;
the activation patch has not yet been expanded. Next: incorporate that structural
contract into the isolated activation candidate and verify full-app/cache paths,
including valid empty tables and explicit identity values. DATE/WEEKDAY and
identity value/type contracts still require separate investigation.

Combined source-contract and hard partial-limit suite: **301 passed**, two known
dependency warnings. No runtime, production API or installation changed. This
is a demonstrated synthetic data-loss path, **not evidence that the user's
0.9.29 source had missing descriptors**, nor the cause of the 600-second result.


### Staffing identity contract activated in isolated full-app candidate (2026-09-11)

The Library activation patch now requires exactly one GROUPID, SHIFTID and
WORKPLACID descriptor in SHDEM/SPDEM in addition to numeric MIN/MAX. This reuses
`read_dbf(required_fields=...)`; it does not invent IDs, permissions, staffing or
maximum hours. The API DBF factory opt-in remains isolated, not deployed.

`tools/test_upstream_staffing_full_app.py::run_contract` verifies the real
`sp5api.main` middleware/auth and both `/api` and `/api/v1` routes, with both
injected-reader and constructor/factory activation paths. Missing identity
columns fail with HTTP 500 category `structure` for populated, empty and
deleted-only tables, with and without `group_id=1`. Duplicate identity columns
also fail. Warming the permissive Library cache first does not hide the error.
Valid empty/deleted-only sources remain HTTP 200; explicit identity value 1
survives the scoped request for all three fields. Existing numeric/read failure,
authentication and Generator error-cache/retry checks remain in this harness.

This closes the demonstrated structural candidate gap before Library filtering;
it does not establish DATE/WEEKDAY or identity value/type semantics. No production
source mutation or Generator runtime change is involved. The exact 0.9.29
project/job/result is still unavailable, so this is not a causal reproduction of
the reported 600-second result. Next investigate date/weekday source integrity
and its effect on selected-period demand, without inferring missing demand.

### Temporal descriptors: OSP5 filtering differs from Generator import (2026-09-11)

`tools/test_upstream_staffing_source_contract.py::test_missing_staffing_temporal_descriptor`
now exercises synthetic SHDEM/SPDEM with valid counts and all three identity
descriptors, but missing WEEKDAY/DATE. The current identity/count contract accepts
these files. Library `get_staffing_requirements` emits `weekday=None`;
`get_special_staffing` emits `date=""`. Both API routes return HTTP 200, and team
filtering alone preserves the malformed rows. An SPDEM request with
`date=2026-09-01` instead returns an empty list because Library filters before
mapping. This is a source-integrity gap, not proof that any real table is malformed.

The downstream distinction matters:

* OSP5 `frontend/src/pages/Personalbedarf.tsx`, special-staffing `load`, passes
  `filterDate` to `api.getSpecialStaffing`; `frontend/src/api/client.ts` forwards
  it as the API date query. The filtered view can hide the malformed source row.
* Generator `api_adapter._Database.get_special_staffing` sends **only group_id**.
  `sp5_adapter.import_snapshot` checks the returned special row with `calc.to_date`
  before period filtering and records `SPDEM: Ungültiges Datum.`. Its regular
  demand mapping also rejects non-integer/out-of-range weekdays. Therefore this
  missing-DATE example does **not** demonstrate silent demand loss in Generator.
* Reusing `read_dbf(required_fields=...)` with DATE/WEEKDAY rejects missing
  descriptors as categorized HTTP 500 `structure` before filtering. The paired
  test verifies this mechanism; the activation patch is not yet expanded.

Source-contract suite: **175 passed**, two existing dependency warnings. Initial
invocation via the pytest executable failed collection (`tools` not importable);
the repository-root `python -m pytest` invocation passes. Next: verify temporal
descriptor types/values and valid empty/deleted tables before extending activation.
Do not conflate a required descriptor with a valid date or weekday value. No
runtime or release changed, so the unchanged private API baseline was not rerun.
The original 0.9.29 project/job/result remains necessary for causal reproduction.

### Temporal values: descriptor presence is not calendar validity (2026-09-11)

`test_temporal_presence_does_not_validate_value` adds 24 synthetic cases through
DBF -> actual Library -> isolated API GET, using the optional required temporal
descriptor contract. Populated, empty and deleted-only files are exercised.

* SHDEM: numeric weekday 7 survives (holiday slot); 8 also survives despite being
  outside Generator's accepted 0..7 range. A DATE-typed WEEKDAY survives as an ISO
  string. A blank numeric WEEKDAY is already rejected as `numeric_value` by strict
  `_validate_dbf_numbers`, which checks all numeric columns, not only MIN/MAX.
* SPDEM: valid D-typed 20260901 becomes 2026-09-01. Blank and impossible dates
  become null via `_parse_date`; N-typed DATE survives as an integer. Required
  descriptor presence rejects none of these three malformed date cases.
  `SP5Database.get_special_staffing(date=...)` hides them with HTTP 200 empty,
  whereas the team-only request exposes the unusable value.
* Valid empty and deleted-only sources remain empty HTTP 200; deleted values do
  not become active staffing. Structural type checking and active-row calendar
  value checking must therefore be distinguished when extending the candidate.

Downstream paths remain as documented above: OSP5 forwards a date filter;
Generator fetches team-only and validates dates/weekdays. Prioritize explicit
source field types and active-row temporal ranges before enabling a broader
strict contract. Do not synthesize replacement dates or staffing. The candidate
activation and all production runtimes remain unchanged.

Combined source-contract, partial-limit and calendar-limit suites: **356 passed**,
two known dependency warnings; Ruff passed. The first characterization run had
one incorrect expectation (blank numeric WEEKDAY was assumed to pass); inspection
of `_validate_dbf_numbers` and the observed categorized HTTP 500 corrected it.
These are synthetic source-integrity findings, not proof of corruption in real
SP5 data or a reproduction of the reported 0.9.29 plan. Exact original input,
job and result are still needed for that causal claim. No repeated private API
run was warranted for this test/documentation-only change.

### Opt-in temporal reader correction candidate (2026-09-11)

`tools/upstream-library-temporal-reader-candidate.patch` layers on the existing
strict-reader patch; it is **not activated** in Library/API or Generator runtime.
`read_dbf` and `read_dbf_buffer` accept explicit `date_fields` / `weekday_fields`:

* Required temporal descriptors must occur once. DATE must have DBF type D;
  WEEKDAY must have numeric type N/F. Structural failures also fail empty or
  deleted-only files, rather than waiting for a row to appear.
* Active dates reuse `_parse_date` calendar validation: blank or impossible
  dates raise source-free `DBFValueError("invalid_required_date")`.
* Active weekdays must decode to an actual integer in 0..7, matching Generator
  `sp5_adapter.import_snapshot` rather than silently converting integral floats.
  Holiday slot 7 remains valid. Blank numeric values still use the existing
  numeric validator. Opt-in calendar fields enable validation even when the
  general `strict` flag is omitted/false; missing files cannot become empty success.
* Valid empty and deleted-only sources remain empty. Deleted row values are not
  validated as active staffing. Calls without calendar options retain behavior.

`tools/test_upstream_temporal_reader.py` verifies file/buffer entry points,
leap dates, impossible/blank dates, weekday bounds/fractions/integral floats,
structural types and missing/duplicate descriptors with synthetic bytes only.
The combined reader/source/full-app/partial/calendar suite passes **576 tests**
(two known dependency warnings); Ruff and patch dry-run pass. An initial broader
run failed because SP5_WORK_TIME_ROUTER was missing from the test environment;
the corrected run uses `/tmp/sp5-worktime-contract/sp5api/routers/work_time_rules.py`.

**Integration gate remains open:** API `_staffing_source_error` currently calls
all DBFValueError instances `numeric_value`. Before activating temporal options,
introduce a source-free temporal error category and exercise full-app auth,
filters, factory/cache behavior and Generator diagnostics. The existing full-app
suite verifies unchanged activation compatibility, not temporal activation.
Then expand the staffing activation patch and perform the authorized private
GET audit for the relevant runtime change. No repeated unchanged private baseline
was run for this isolated candidate. No evidence here establishes malformed real
DBF dates or explains the original 0.9.29 result; its exact input/job/result is
still missing. No weekly maximum, employee obligation or duty prohibition added.

### Temporal API error category (isolated follow-up)

The source-contract API patch now maps exactly the Library error argument tuples
`invalid_required_date` and `invalid_required_weekday` to `temporal_value`, with
fixed German text. Unknown/extended argument tuples retain the numeric fallback;
no exception values or paths are returned. Structural type failures remain
`structure`; blank numeric weekdays remain `numeric_value`.

`tools/test_upstream_staffing_source_contract.py` now compares descriptor-only
and explicitly calendar-enabled reads through the actual Library mapping and API
route. Invalid active dates/weekdays fail before group/date filtering, including
an unrelated group. Valid holiday slot 7, empty and deleted sources retain their
semantics. The existing OSP5 error consumer displays the fixed temporal message;
malformed exception metadata cannot leak source content.

Validation: **453 passed**, two known dependency warnings (source contract,
temporal reader, strict reader and full-app compatibility); Ruff, diff check and
API patch dry-run passed. Four initial test failures were fixture construction
errors (DBFValueError requires one constructor argument); corrected tests mutate
synthetic exception metadata after valid construction.

This is still an isolated patch, not a runtime change or release. Full-app tests
cover existing staffing activation, not yet automatic temporal activation.
Generator currently rejects this new category with its generic HTTP-500 message;
specific Generator diagnostics and full-app temporal activation remain next.
No private baseline repetition or claim of reproducing the reported 0.9.29 plan.

### Full-app calendar activation gate (2026-09-11)

`tools/upstream-library-staffing-temporal-activation-candidate.patch` layers on
`upstream-library-staffing-activation-candidate.patch`. The isolated
`SP5Database._read` now selects `date_fields=("DATE",)` for SPDEM and
`weekday_fields=("WEEKDAY",)` for SHDEM. Other tables and the default permissive
constructor remain unchanged. This reuses the existing opt-in reader; no new
calendar parser or inferred staffing requirement is introduced.

`tools/test_upstream_staffing_full_app.py` adds a temporal activation mode using
the actual API dependency factory, middleware and both `/api` and `/api/v1`.
`tools/test_upstream_staffing_temporal_app.py` checks active/empty/deleted sources,
valid/blank/impossible/wrong-type temporal values and matching/nonmatching
team/date filters. Every source is first parsed into the permissive Library cache.
Unauthenticated requests remain 401; invalid sources remain source-free 500 even
when filters would exclude their rows. Valid holiday 7 and valid empty/deleted
sources remain successful. The actual Generator APIClient rejects failed reads
without caching them and retries successfully after synthetic source repair.
Generator's temporal diagnostic remains generic HTTP 500 (and v1 is outside its
specific diagnostic allowlist); successful error rejection is not a specific
user-facing diagnosis and does not imply a generated/validated schedule.

Run environment in addition to the earlier activation variables:

```sh
SP5_STRICT_READER=/tmp/sp5-temporal-contract/sp5lib/dbf_reader.py
SP5_STAFFING_ROUTER=/tmp/sp5-temporal-api-contract/sp5api/routers/master_data.py
SP5_TEMPORAL_DATABASE=/tmp/sp5-temporal-activation/sp5lib/database.py
```

The full-app/source/reader plus partial/calendar limits suite passes **508 tests**
(two known dependency warnings). Ruff and diff check pass. The first full-app run
used the older numeric-only API candidate and correctly failed two temporal
category assertions; selecting the temporal API candidate corrected the harness.
These paths are isolated source copies, not productive configuration or data.
The three upstream checkouts remain unchanged. No release/runtime change and no
repetition of the unchanged private baseline. Remote CI remains unverified
(`gh` unavailable). Original 0.9.29 input/job/result remains unavailable; no causal
claim about 600 seconds, 24-hour duties or weekly overruns follows from this gate.
Next: complete Generator-specific temporal diagnostics with synthetic allowlist
checks, then integrate and privately GET-audit the combined runtime candidate.

### Generator temporal diagnostic contract (2026-09-11)

`APIClient._fetch` now recognizes the exact `temporal_value` category for the
four staffing endpoints under `/api` and `/api/v1`. It displays a fixed local
German date/weekday message, never upstream bodies, reasons or arbitrary header
values. Unknown categories, other paths and other HTTP statuses remain generic.
No import mapping, staffing requirements, approvals or solver limits change.

Adapter and actual full-app temporal activation tests pass **276 tests**. The
full-app gate checks the specific diagnostic for structure/numeric/temporal
failures and retry after synthetic source repair without caching failed reads.
Another **193 partial/calendar/dated-rest tests** pass; Ruff and diff check pass.
An initial broad string edit also changed a special-staffing call and caused
219 adapter failures; that unintended edit was removed before the passing run.
The isolated Library/API temporal patches are still candidates, not deployed
upstream. Specific diagnostics do not establish malformed real source data or
reproduce the missing original 0.9.29 job.

The complete local `tests` suite also passes **1078 tests** (two known dependency
warnings). This does not replace the separate upstream candidate full-app gate
or the private API audit and is not a remote CI result.

### Rebuilt combined staffing runtime gate (2026-09-11)

`tools/test_upstream_staffing_packaged.py` rebuilds the six checked-in staffing
candidate patches in dependency order from clean tracked Library/API Python
source. It copies no DBF fixtures, credentials, configuration or state. Unlike
the earlier module-override gates, the child imports the combined package
normally and asserts that reader, database, API dependency factory and staffing
router all originate in the assembled directory. No prepared `/tmp` source
copies or `sys.modules` replacement are needed for this gate.

The existing `run_contract` / `check_temporal` assertions are reused, not
reimplemented: actual middleware authentication, dependency activation, both
API prefixes, valid/invalid temporal data, empty/deleted sources, team/date
filters, permissive cache isolation and Generator error/retry behavior. This
closes a test-integration gap: individually valid patches and injected modules
alone did not prove the combined source package imports and activates correctly.

```sh
SP5_LIBRARY_SOURCE=/path/to/libopenschichtplaner5 \
SP5_API_SOURCE=/path/to/openschichtplaner5-api \
.venv/bin/python -m pytest -q tools/test_upstream_staffing_packaged.py
```

Verified source revisions: Library `0dac4438c0be02c1ad612f54d4aba75a3e4d6335`,
API `d578f212d635b672ab277d7d29a37387145506f5`. Both prefix cases pass.
The API lifespan, credential login and a network server are deliberately outside
this in-process HTTP gate. No productive API change, release, real DBF validation
or reproduced 0.9.29 plan is implied. The existing private GET audit exercises
the deployed remote API, not this upstream package: injecting strict DBF parsing
into that remote service would require a separate deployment, not a GET request.
No such deployment was performed. Hard work-time rules, approvals, staffing and
Generator runtime remain unchanged in this step.

### Remaining staffing identity-type gap (2026-09-11)

The next independent characterization adds 30 synthetic DBF/API cases plus
three Generator cases in `tools/test_upstream_staffing_source_contract.py`:

* `required_fields` enforces descriptor presence/uniqueness, **not ID types**.
  The combined reader contract still accepts L-typed true, M-typed null and
  numeric 1.5 for GROUPID, SHIFTID and WORKPLACID. Blank/malformed N-typed
  values already fail with `numeric_value`; the first test draft incorrectly
  expected legacy zero coercion for those 12 cases, and was corrected after
  inspecting `_validate_dbf_numbers` and observing its exceptions.
* Library `SP5Database.get_staffing_requirements` exposes these parsed values
  without identity validation. API `get_staffing_requirements` treats null as
  unscoped and uses Python equality for team matching: true equals integer 1.
  Library `get_special_staffing` instead filters null out for selected team 1,
  but also matches true to 1. Fractional team 1.5 is filtered out by both.
* OSP5 `frontend/src/pages/Personalbedarf.tsx`, regular-demand `reqMap`
  construction, uses `r.group_id !== filterGroup`; unlike Python it rejects
  boolean true when the selected team is numeric 1. TypeScript annotations
  alone do not validate JSON received at runtime.
* Generator `APISource.get_staffing_requirements` fetches regular demands
  **without a team filter**. In `import_snapshot`, the initial
  `gid not in (*scope, 0, None)` check accepts true for team 1 and drops 1.5
  before reporting an unresolved requirement. The synthetic fixture creates
  one demand for true with no unresolved regular requirement, no demand and
  no unresolved regular requirement for 1.5, and correctly records null as
  unresolved. This is a demonstrated local mapping gap, not proof that the
  user's real DBF has any of these values. SPDEM is fetched with a team filter,
  so a Generator-only fix cannot recover upstream-filtered malformed rows.

Prioritized correction: validate identity types before filtering at the source
boundary and at Generator import, keeping existing explicit zero/null semantics
separate from malformed types. Do not infer new approvals, staffing, positive-ID
ranges or a weekly maximum. Verify normal integer IDs and any supported integral
DBF float representation, plus existing workplace-zero interpretation. Follow
with the combined package gate and a private GET audit for Generator runtime
changes. Original 0.9.29 input/job/result remains unavailable; this finding does
not establish the cause of the 600-second plan, 24-hour duties or weekly overruns.

### Opt-in staffing identity correction candidate (2026-09-11)

The new `upstream-library-identity-reader-candidate.patch` extends the existing
strict/temporal reader with explicit `identity_fields`. Numeric N/F descriptors
are required; boolean/logical and memo descriptors fail structurally, including
empty/deleted-only tables. Active fractional, blank and malformed IDs fail rather
than being coerced into a team. Integral numeric representations normalize to int;
zero and negative values remain unchanged (no invented positive-ID range).
Without opt-in, legacy reader behavior remains unchanged.

`upstream-library-staffing-identity-activation-candidate.patch` opts SHDEM/SPDEM
into this contract at `SP5Database._read`, before Library/API filtering and outside
the permissive shared cache. Existing source-safe API error categories are reused.
The combined packaged gate now rebuilds eight patches from tracked source and
checks both API prefixes: each identity column, boolean/memo/fractional failures,
integral float compatibility, unmatched team filters, warmed permissive cache,
and successful reread after source repair. The reader suite also covers file
forwarding/missing files, duplicate/missing descriptors and opt-in compatibility.
**95 tests pass**, including both full-app package cases; Ruff passes. During
integration a context-short patch and an overbroad test insertion failed; both
were corrected before the passing run.

This is an isolated upstream correction candidate, not a productive API change.
Generator's independent JSON import identity check remains next; the remote API
cannot gain this reader behavior through GET-only auditing. No Generator runtime
change, release, real-data claim or repeat of the unchanged private baseline.
Original 0.9.29 project/job/result remains unavailable. Very large decimal ID
precision and Generator-side prefilter validation remain explicit follow-ups;
this gate is not proof of arbitrary-width exact numeric decoding.

### Exact decimal identity follow-up (2026-09-11)

The previous candidate's `float.is_integer()` check demonstrably lost source
precision: synthetic N/F `9007199254740993.0` became `9007199254740992`, while
`1.0000000000000001` and `9007199254740992.5` passed as integral identities.
Eight of twelve added cases failed before correction. These are numeric edge
fixtures, not observed real staffing values or an explanation of the 0.9.29 plan.

The existing opt-in reader now uses standard-library `Decimal` on original field
bytes after strict numeric validation, checks exact integrality and only then
converts to Python int. Compiled field offsets are reused; legacy numeric decoding
and zero/negative sentinels are unchanged. No dependency or parallel parser is
introduced. The combined reader/package gate passes **107 tests**, with the two
existing deprecation warnings. N/F signs, negative zero, tiny fractions and large
decimal integers are covered alongside both full-app API prefixes.

This guarantees the tested Library identity decoding, not arbitrary end-to-end
JavaScript number precision: large JSON numbers can still lose precision in a
browser. The candidate is not deployed; Generator runtime and private baseline
remain unchanged. Next source boundary is `sp5_adapter.import_snapshot`, where
the `gid not in (*scope, 0, None)` filter still runs before identity validation.
That independent boolean/fractional JSON gap needs its own correction and private
GET audit. Original project/job/result for the user's 0.9.29 run remains missing.

### Generator prefilter identity validation (2026-09-11)

`sp5_adapter.import_snapshot.checked_staffing_rows` now checks SHDEM identifiers
before team filtering and SPDEM identifiers before date/cell grouping. Boolean,
fractional, string, container and nonfinite group/service/workplace identifiers
become explicit unresolved source rows rather than Python-equality matches,
silent exclusions or unhashable-key crashes. Integral numeric representations
normalize to int **before** constructing canonical IDs: previously `1.0` matched
team 1 but produced `sp5:group:1.0`, inconsistent with employee membership.
Existing null/zero handling remains downstream; this introduces no positive-ID
range or inferred approvals. Malformed source values are retained only in the
local snapshot metadata; diagnostics contain field names, not original values.

44 synthetic SHDEM/SPDEM cases in `tests/test_sp5_adapter.py` failed before the
fix and pass after it. The focused import/partial-plan/calendar-limit suite
passes 292 tests. The previous three Generator characterizations in
`tools/test_upstream_staffing_source_contract.py` now assert the corrected
unresolved behavior. No new parser or dependency: existing Python numeric type
checks and the import's unresolved-source mechanism are reused.

The upstream package candidates remain necessary: SPDEM is fetched with a team
filter, so the Generator cannot diagnose malformed rows already removed by the
remote Library/API. Nor can it reconstruct decimal precision lost before JSON
arrives. These tests do not establish occurrence in real data or the cause of the
user's original 0.9.29 plan; that exact project/job/result is still unavailable.

Follow-up checks preserve null/global and out-of-scope integer handling and
prove that a malformed boolean SPDEM team cannot replace a regular SHDEM cell
with zero capacity. The original regular demand remains visible, but the
unresolved source still blocks partial solving (`MODEL_INVALID`); this is not
an automatic fallback authorization. Full default suite: 1122 passed, followed
by five additional passing sentinel/cell tests. Three corrected Generator
characterizations and both clean upstream package reconstructions also pass.
Two existing dependency deprecation warnings remain. Ruff/diff checks pass.


### Daily staffing prerequisite loss before team filtering (2026-09-11)

Source chain: `sp5lib.database.SP5Database.get_staffing_requirements` reads
DADEM and returns raw uppercase rows; unlike SHDEM it does not normalize them.
API `routers/master_data.get_staffing_requirements` filters only SHDEM, leaving
DADEM intact. OSP5 `api/client.ts` declares `daily_requirements: unknown[]`;
`Schedule.tsx` loads only `data.shift_requirements`, and the daily staffing view
in `Personalbedarf.tsx` also iterates `reqs.shift_requirements`. These consumers
do not establish an equivalence between a raw daily total and shift headcount.

Generator `sp5_adapter.import_snapshot` previously filtered DADEM by raw
`GROUPID` (lowercase fallback) before validation: a fractional/string/container
team silently disappeared, while booleans matched integer scope/global values.
Fourteen synthetic cases fail before the correction. It now preserves malformed
rows privately as unresolved native input and emits a value-free identity
diagnostic. Valid out-of-scope integer rows remain excluded; null/zero keep
existing unresolved global semantics. No daily total is converted into shift
demand, no rule/profile/approval is confirmed, and no employee is forced into a
plan. Existing unresolved-source validation remains the planning gate.

The focused adapter/partial/calendar suite passes 311 tests. This is a proven
input-diagnostic defect, not evidence that malformed DADEM existed in the user's
0.9.29 input or caused a working-time violation. The original 600-second
project/job/result remains unavailable. Existing partial regressions cover
real versus paid duration, ISO weeks/DST/context, and UNKNOWN quality-phase
fallback; this patch changes none of those constraints.

Next person-flow boundary: Library `get_group_members` reads GRASG EMPLOYEEID
using GROUPID equality; API `routers/employees.get_group_members` joins these
IDs against EMPL, then Generator `api_adapter.get_group_members` extracts ID.
`sp5_adapter.import_snapshot` intersects EMPL with the scoped membership set and
deduplicates by raw ID before constructing employees, their nominal targets and
unconfirmed profile links. Existing `test_hierarchy` and
`test_api_adapter.test_parent_team_imports_nested_people_without_duplicates`
cover legitimate nested memberships, not malformed or conflicting EMPL/GRASG
identities. This merits a separate end-to-end reproduction before any fix;
missing membership is not evidence of missing personal service approval, and
membership must not be synthesized from historical duties.

Full default regression suite after this correction: **1141 passed**, two
existing dependency deprecation warnings. Ruff and diff checks pass.

### Missing-person pipeline: reproduced loss, not a solver exclusion (2026-09-11)

`tools/test_upstream_person_flow.py` executes the actual Library method and the
unmodified API membership GET function/decorator in an isolated FastAPI app,
then the Generator adapter/import using synthetic records only. Four
characterization tests establish the current defects (passing is not approval
of the defective behavior):

1. **GRASG -> Library:** `database.SP5Database.get_group_members` returns both
   valid and orphan EMPLOYEEID values for the selected GROUPID.
2. **Library -> API:** `routers/employees.get_group_members` builds an EMPL
   dictionary and returns only membership IDs found in it. A missing EMPL row
   disappears with HTTP 200. Conflicting EMPL rows sharing an ID are last-wins;
   the synthetic conflict changes both employment end and nominal weekly hours.
3. **API -> Generator:** `_Database.get_group_members` receives only surviving
   IDs. The `import_from_api` subset check therefore succeeds even when the
   Library originally reported an orphan. It checks agreement between two
   already-lossy views, not completeness against GRASG.
4. **Direct Library -> Generator:** `sp5_adapter.import_snapshot` also silently
   intersects memberships with EMPL and deduplicates by ID. A synthetic orphan
   produces exactly the baseline snapshot, including its diagnostics (excluding
   only the creation timestamp). Conflicting rows produce exactly the same
   snapshot as the last row alone. Thus employment/target selection depends on
   row order without an explicit conflict diagnostic.
5. **API -> OSP5:** `frontend/src/api/client.ts: getGroupMembers` reads the same
   members resource via the v1 prefix. `pages/Groups.tsx` and
   `pages/Jahresuebersicht.tsx` use those returned members; the latter builds an
   ID set. Neither this consumer path nor the Generator can reconstruct orphan
   membership from a response that already removed it.

Repeated *valid membership* for the same person remains benign: the fourth
boundary's deduplication correctly yields one Generator employee. It must not
be confused with conflicting personal master records. Existing hierarchy and
API nested-membership tests plus the four characterizations: **297 passed**, two
existing dependency warnings. Test invocation:

```sh
SP5_API_SOURCE=/path/to/openschichtplaner5-api .venv/bin/python -m pytest -q tools/test_upstream_person_flow.py tests/test_hierarchy.py tests/test_api_adapter.py
```

Prioritized correction: preserve a sanitized source-integrity failure at the
API membership join for orphan memberships/conflicting master records; add the
equivalent direct-import guard before EMPL scope filtering/deduplication. Do not
invent missing people, memberships, employment dates, approvals or hour values.
Keep identical repeated membership valid. The Generator-only guard cannot fix
records already removed upstream. Use existing import/source-error mechanisms,
not a new identity framework. Verify the candidate through the established
synthetic packaged-API gate and private GET-only audit before deployment.

This explains a demonstrated class of **persons absent from input**, separate
from `solver` eligibility diagnostics for **present but unassigned persons**.
It does not establish that these source defects occurred in the original 0.9.29
project, nor that they caused its reported 24h/week-limit outcomes. The exact
600-second input/result is still unavailable. No runtime change or release is
part of this characterization; the last private audit remains applicable to
the unchanged runtime and is not presented as a successful real plan.

### Person-join correction candidate (2026-09-11)

`tools/upstream-api-person-integrity-candidate.patch` now replaces the lossy
join in `sp5api/routers/employees.get_group_members`. An orphan membership
returns HTTP 500 with `employee_source_unresolved` / `orphan_membership`;
conflicting EMPL records return the same code / `conflicting_employee`, before
row order can select employment dates or nominal hours. Error bodies contain
neither IDs, names, dates nor filesystem paths. Identical repeated master rows
and repeated valid memberships retain the existing successful response shape.
No missing person or approval is synthesized. Conflicts anywhere in the loaded
master list block this candidate, including outside the requested group.

The candidate is **not deployed**. Its six synthetic cases apply the actual
patch to a temporary source-only router and execute its GET function through
FastAPI. Together with the previous characterization and hierarchy/API tests:
**303 passed**, two known dependency warnings; Ruff and diff checks pass.
This is a router-level test, not a packaged full-app/authentication or live API
acceptance. The unchanged published Docker baseline was not redundantly tested.

Next: equivalent direct-import guard (still vulnerable), packaged middleware
and Generator error propagation coverage, then private GET-only acceptance
before activating changes. The API fix cannot by itself protect direct Library
imports, nor establish the cause of the unavailable original 0.9.29 plan.

### Direct Generator person-join protection (2026-09-11)

`sp5generator.sp5_adapter.import_snapshot` now validates the employee index
before membership scope filtering and deduplication. Conflicting master rows
raise sanitized `ValueError` category `conflicting_employee`; selected memberships
without a master record raise `orphan_membership`. Identical master rows and
repeated valid memberships still import once. Like the API candidate, conflicting
records anywhere in the loaded master list block import. Existing source-error
handling is reused; no people, dates, approvals or hour limits are inferred.

`tests/test_sp5_adapter.py` covers conflicts in both nominal weekly hours and
employment end dates, orphan memberships, and valid duplicates.
`tools/test_upstream_person_flow.py` retains characterization of the unpatched
API's loss but now asserts rejection at the direct Generator join. This guard
cannot discover memberships the remote API has already dropped. Malformed ID
semantics and full-app API candidate propagation remain separate follow-ups.

The packaged combined-candidate gate now includes the person-join patch and
`tools/person_full_app_contract.py` through the actual API app middleware for
both `/api` and `/api/v1`. It checks unauthenticated rejection, sanitized orphan
and conflict responses/headers, valid response preservation, and Generator
`APIClient` import failure without caching the error. Both packaged cases pass;
API deployment/login/startup background tasks remain outside this source-only
synthetic gate. Generator currently displays the generic sanitized HTTP 500
message for this contract; category-specific presentation is not claimed.

### Malformed person identities before the join (2026-09-11)

Eight additional synthetic characterizations in
`tools/test_upstream_person_flow.py` locate remaining failures before the new
orphan/conflict checks; these tests describe defects, not desired behavior:

| Source value | Library/API path | Direct Generator path |
| --- | --- | --- |
| GRASG.GROUPID `True`, requested group `1` | `SP5Database.get_group_members` accepts Python equality and returns the person; API preserves the false membership | Cannot reconstruct the original group field from returned member IDs |
| GRASG.EMPLOYEEID `True`, EMPL.ID `1` | API `employees.get_group_members` dictionary lookup aliases the IDs | `import_snapshot` set/index lookup also accepts the false match |
| EMPLOYEEID list/dict | Library returns it; API join raises raw `TypeError` | Membership set creation raises raw `TypeError` before source diagnostics |
| EMPLOYEEID fraction, string, null | Unpatched API silently drops the membership | Existing guard rejects it as `orphan_membership`, not a malformed identity |
| Missing EMPLOYEEID | Library raises `KeyError` while reading selected membership | No membership list reaches the Generator |

OSP5 `frontend/src/api/client.ts:getGroupMembers` consumes the same resource;
`pages/Jahresuebersicht.tsx` constructs a JavaScript ID set from the returned
records. Neither can recover the original malformed membership field after
the API join. This is a person-source integrity defect, not evidence that the
solver ignored a valid person or relaxed a hard work-time rule.

The staged API orphan/conflict patch also uses raw dictionary keys, so its
existing guard does not resolve boolean aliasing or unhashable keys. Next
correction must validate native identity shape **before** Library group
equality, API dictionary joining, and Generator membership set construction.
Reuse the existing strict native-identity reader mechanisms where applicable;
do not coerce booleans/strings/fractions into IDs or invent absent people.
Compatibility for integral DBF numeric IDs needs explicit regression coverage.

Focused characterization/candidate/hierarchy/API gate: **311 passed**, two
known dependency warnings; Ruff and diff checks pass. No runtime code, deployed
API, or published Docker image changed. The unchanged private baseline is not
retested or claimed as a successful plan. These synthetic defects are not yet
linked to the unavailable original 0.9.29 project/job/result.


### Native person DBF identities before equality/join (2026-09-11)

The combined opt-in candidate now applies
`tools/upstream-library-person-identity-activation-candidate.patch` after the
existing strict/temporal/exact-identity reader patches. In
`SP5Database._read`, `strict_staffing=True` also reads `GRASG` with required
numeric identities `GROUPID, EMPLOYEEID`, and `EMPL` with `ID`. This happens
before `get_group_members` / `get_all_group_members` group equality and before
`get_employees` can feed the API dictionary join. The permissive source cache
is bypassed; no second parser or inferred replacement person is introduced.

`tools/person_reader_contract.py:check_person_reader`, executed inside the
rebuilt package, checks all three fields with integer N, integral decimal N/F,
fractional N, logical L, character C, blank and malformed numeric values.
Integral `1.0` remains an integer ID; fractions, boolean-typed and character
IDs fail. Missing descriptors fail, preloaded permissive cache entries cannot
bypass the checks, and a corrected source succeeds after a failed read.

`tools/person_full_app_contract.py:check_native_person_source` additionally
runs synthetic native DBF files through the actual Library, employees router,
API middleware and Generator `APIClient`, under both `/api` and `/api/v1`.
Nine malformed table/field/type cases per prefix return HTTP 500, not a 200
empty membership list; Generator raises `APIImportError` without caching the
failure. Unauthenticated access remains 401 and valid integral-decimal source
recovers to a successful person join. The current middleware response is still
**generic**: this does not yet provide the category-specific employee-source
headers for DBF read errors. That propagation remains a concrete follow-up.

This closes the native DBF entry point only in the staged candidate. Direct
Generator Python/API rows and arbitrary API database implementations still need
identity-shape checks before set/dictionary construction. Existing upstream
checkouts and deployed services are untouched. No claim is made that these
synthetic cases caused the user's missing persons, 24-hour duties or weekly
excesses; the exact 0.9.29 input/job/result is still needed for that attribution.

Verification: combined packaged/reader/person/API gate **395 passed**, two
known dependency warnings; Ruff and diff checks pass. The initial new patch
had an incorrect hunk length; corrected before the successful rebuilt gate.
No Generator runtime or released image changed, so the unchanged private
baseline was not redundantly rerun. Remote CI remains unverified (`gh` absent).

### Direct Generator native person-key guard (2026-09-11)

The Library candidate above does not protect arbitrary database facades passed to
Generator `sp5_adapter.import_snapshot`. That importer now validates membership
and EMPL keys **before** constructing a set/index. Boolean, fractional,
string, null, nonfinite and container keys raise a sanitized
`invalid_person_identity` error instead of aliasing a person, disappearing, or
leaking an unhashable-key exception. Integral DBF float keys remain supported
and normalize to integers before deduplication and public employee IDs.

Evidence: `tests/test_sp5_adapter.py::test_person_identity_checked_before_native_join`
(18 malformed-source cases) and
`test_person_integral_dbf_float_identity_normalizes_without_losing_person`.
The upstream characterization `tools/test_upstream_person_flow.py` still
demonstrates the unpatched API loss/aliasing but now expects the direct Generator
guard. This does not reconstruct people already discarded upstream, infer
approvals, impose assignment of every employee, or establish the cause of the
unavailable original 0.9.29 600-second input/result.

The staged API person-integrity candidate independently validates native keys,
including missing/non-object employee rows, before its own join. This covers
alternative database implementations that bypass the strict Library reader.
Router tests cover malformed member/employee identities and valid float IDs;
the packaged real middleware contract checks sanitized error headers,
Generator APIImportError and an empty error cache under both API prefixes.
The API candidate remains undeployed.


### Sanitized employee-source errors through Generator transport (2026-09-11)

`APIClient._read` now recognizes the staged employees router's three fixed
`employee_source_unresolved` categories: `orphan_membership`,
`conflicting_employee`, and `invalid_person_identity`. Interpretation requires
HTTP 500 and an exact numeric `/api[/v1]/groups/{id}/members` path. Only local
German messages are displayed; upstream bodies/reasons/unknown header values
remain excluded. Other statuses, paths and categories retain the generic error.
Failures are not cached, so a corrected source can be retried.

This completes the prepared chain GRASG/EMPL -> Library readers -> API
`employees.get_group_members` -> Generator `_Database.get_group_members` /
`APIClient._read`. OSP5's `frontend/src/api/client.ts:getGroupMembers` uses the
same versioned membership endpoint; its UI is unchanged. The API candidate
remains **undeployed**, and native Library read exceptions still reach the
middleware as generic failures. A successful transport check is not proof of
a valid plan or of the original 0.9.29 missing-person cause.

Evidence: 14 additional synthetic transport cases in `tests/test_api_adapter.py`
cover allowlisting, rejection, privacy and repeat requests. The rebuilt-package
`tools/person_full_app_contract.py:check_person_join` now requires the precise
local diagnostic after the real API middleware under both prefixes.

### Distinct upstream cycle-generation weekly-hours policy: follow-up

A separate source path must not be conflated with Generator hard profiles:
Library `database.py:generate_schedule_from_cycle` reads EMPL.HRSWEEK directly
into `emp_weekly_hours` (around line 1986), uses weekday `SHIFT.DURATION*`
as hours and rejects a candidate when tracked ISO-week hours plus that duration
exceed HRSWEEK (around line 2216). API `routers/schedule.py:generate_schedule`
exposes this via POST `/api/schedule/generate`, returning `skipped_hours_limit`.
This is **not** Generator's read-only import / CP-SAT planning path and does not
authorize importing nominal hours as a hard weekly cap.

Existing Library `tests/test_cycle_day_unit.py` exercises cycle dates using an
optional golden database, not synthetic weekly-limit/paid-vs-elapsed contracts.
Next bounded analysis: characterize this separate path with synthetic fixtures,
including CALCBASE month/hour targets and month-boundary context, then trace the
OSP5 caller. No productive generation endpoint was called; this source finding
is not yet a reproduced bug or an explanation of the user's 600-second result.


Synthetic follow-through: `tools/test_upstream_cycle_hours.py` executes the
actual Library method with a synthetic table facade, isolated optional sidecar
paths and a write trap (`dry_run=True`). Six passing cases prove:

* CALCBASE=2 / HRSMONTH=160 does not affect this branch: HRSWEEK=7 rejects an
  eight-hour candidate, HRSWEEK=8 accepts it, HRSWEEK=0 disables that check.
* For a September 2, 2026 candidate, an eight-hour September 1 duty exhausts
  the eight-hour week cap; an identical August 31 duty is ignored, although
  all three dates belong to ISO week 36. The existing-duty map filters to the
  requested month before initializing the tracker. This is a reproduced
  **month-boundary omission in this upstream cycle-generation path**.
* DURATION=8 with STARTEND=00:00-24:00 consumes eight, not 24 tracker hours.
  This proves the accounting basis, not that every 24-hour duty is forbidden.

OSP5 `frontend/src/pages/Schedule.tsx` invokes
`api.generateSchedule` in both preview and generation handlers (around lines
3001 and 3024); `frontend/src/api/client.ts:generateSchedule` calls the versioned
API endpoint. Thus this upstream policy is user-visible, but is not the
Generator CP-SAT path. No frontend save was exercised and no API POST occurred.
Next: stage a synthetic-tested upstream month-boundary correction preserving
its existing paid-duration/HRSWEEK policy, and explicitly keep that policy
separate from Generator configured elapsed-time caps. Do not silently promote
HRSWEEK to a new Generator hard rule or attribute this finding to the unavailable
0.9.29 job.

### Staged cycle-generator ISO-week context correction

`tools/upstream-library-cycle-week-context-candidate.patch` separates the
month-local overwrite/skip set from the normal-duty hours map. The latter now
includes all MASHI dates in ISO weeks touched by the requested month, including
both adjacent month tails and ISO-year transitions. This preserves the upstream
HRSWEEK / weekday DURATION policy; it does **not** introduce a Generator cap,
count elapsed duration instead of paid duration, or change source data.

`tools/test_upstream_cycle_week_context_candidate.py` applies the patch to a
throwaway copy and exercises the actual method with synthetic tables and a
write trap. Together with the baseline characterization, **25 tests pass**
against both the installed Library and the source checkout. Coverage includes
both month edges, adjacent nonmatching weeks, the ISO-year boundary, force
on/off, disabled/positive limits, and the existing eight-hour paid / 24-hour
elapsed distinction. Candidate is undeployed; no API POST was performed.

Separate reproduced issue, intentionally not hidden by that bounded patch:
`generate_schedule_from_cycle` checks accumulated hours plus a proposed duty
**before** testing whether that same person/day will be skipped or replaced.
An existing eight-hour duty with an eight-hour cap is reported as
`hours_exceeded` even for a no-op skip; `force=True` also counts old plus new
before replacement. Two characterization tests preserve this finding. Correct
replacement accounting needs its own write-failure/rollback and dry-run tests;
multiple normal duties per person/day and special-duty accounting are likewise
not resolved by the month-context correction.

### Approved service is not the same as requested positive-capacity demand

Generator `domain.eligibility` requires an approval matching
`Position.function_id`, workplace (or wildcard), and the complete duty date
range. A saved approval can remain valid while its service has no demand in the
selected period/team scope, or only demands with `maximum=0`. The existence of
a position or a nominal hours target does not create a staffing requirement.
A person may therefore have approvals yet zero eligible positive-capacity
candidates. Existing `planning_diagnostics` reports this as
`individually_ineligible`; its exclusion counts concern candidate combinations,
not distinct people, and multiple reasons can apply to the same candidate.

Synthetic evidence:
`tests/test_partial_limits.py::test_approved_service_without_positive_demand_does_not_create_assignments`
covers both a registered position without a demand and an explicit zero-capacity
demand. Another worker can fully cover the actual requirement while the worker
approved only for the unrequested service remains unassigned, even with a
positive hours target. No approval, demand, or mandatory assignment is invented.
This distinguishes missing input capacity from a solver choosing not to use an
otherwise eligible person; the latter has reason
`not_selected_with_candidates`, as covered by
`test_no_rule_requires_every_eligible_employee_to_receive_a_duty`.

### Time-budget bottleneck: coverage before hours and blocks

`solver.solve` builds the existing weighted terms, but initially minimizes only
`sum(vacancies)` for partial planning. Before the zero-vacancy correction, its final phase transition
required `phase == "vacancies" and status == cp_model.OPTIMAL`. A first-phase
`FEASIBLE` result returned without running the hours/block objective. Computing
and reporting weighted contributions does not mean those terms were optimized.
This is separate from hard-rule validation and from missing approvals.

The earlier characterization (now updated as
`tests/test_partial_limits.py::test_equal_coverage_feasible_incumbent_reaches_conditional_quality`)
quantifies the consequence using two synthetic eligible workers, one eight-hour
demand, and targets of zero and eight hours. A controlled first-phase incumbent
assigns the zero-target worker: total absolute target deviation is 960 minutes.
The unconstrained quality search assigns the other worker with deviation zero,
at **identical coverage**. Both independently validate. The test covers both
full coverage and one additional unfillable demand, and reports the unused
eligible worker as `not_selected_with_candidates`. The controlled timeout is a
branch characterization, not a wall-clock benchmark or a reproduction of the
user's original job. No rule requires assigning both workers.

Prioritized follow-up for the existing CP-SAT implementation (no new optimizer
dependency needed):

1. Assess bounded incumbent-quality search while maintaining an explicit
   coverage constraint and preserving the best independently valid incumbent.
   Do not replace lexicographic coverage priority with arbitrary weighted
   vacancy penalties or claim proven global quality at an unproven coverage.
2. Zero vacancies already attains the mathematical lower bound, even if the
   solver reports only FEASIBLE; assess that early phase transition separately.
3. Verify fresh-process and HTTP/Worker timeout persistence, quality-phase
   objective/bound identity, and non-worsening coverage before any runtime
   change. Compare same-input timed replays; a different search trajectory is
   not itself proof of improved quality or employee distribution.

Merely increasing hours weights cannot address a search that never reaches
the weighted phase. Neither turning nominal hours into hard weekly caps nor
inventing approvals is an acceptable remedy.

### Zero-vacancy coverage certificate and remaining quality budget (prior step)

`solver.solve` now also transitions from coverage to quality when an independently
validated FEASIBLE incumbent has exactly zero vacancies. Vacancy variables are
nonnegative and exact, so this reaches a known global lower bound without relying
on CP-SAT's termination status. The existing equality fixes coverage at zero;
only the existing weighted objective changes. No hard constraint, approval,
profile, hours target, or time budget is relaxed. A subsequent OPTIMAL quality
result is globally justified because coverage was already proven optimal.

The updated equal-coverage regression forces the same 960-minute-deviation
incumbent as before. With zero vacancies, remaining quality search now reduces
the deviation to zero; with one unfillable demand and no coverage proof, the
existing conservative FEASIBLE behavior remains. Three test cases failed on the
previous implementation and pass after this branch correction.
`test_objective_and_bound_remain_in_their_search_phase` additionally checks
FEASIBLE coverage followed by successful or UNKNOWN quality search, for full and
partial planning, including JSON round-trip and independent validation. UNKNOWN
retains the valid incumbent and its coverage-phase objective/bound, never a
fabricated quality gap or OPTIMAL claim.

This is a narrowly bounded fix, **not** an anytime optimizer for incomplete
coverage. It does not interrupt an ongoing coverage search and cannot recover
budget already consumed there. The measured configured 600-second case with
hundreds of vacancies therefore still needs the separately prioritized bounded
incumbent-quality strategy. Merely proving this zero-vacancy branch correct does
not establish improved performance on that real case.

### Bounded-quality design: three synthetic phase-isolation counterexamples

`tests/test_anytime_quality_contract.py` captures and clones the **actual generated
CP model** before search, using one eligible employee, two eight-hour demands,
and an eight-hour period target. There is no weekly cap inferred from that target.
All examined assignments independently validate. Three native CP-SAT OPTIMAL
results establish concrete hazards for a future anytime strategy:

- Switching to the hours objective without a coverage constraint chooses one
  duty (zero target deviation) instead of two (zero vacancies).
- Fixing an incumbent at one vacancy allows a quality OPTIMAL result, but the
  untouched primary model proves zero vacancies. That quality result is only
  conditional, not global lexicographic OPTIMAL.
- Retaining a quality non-worsening bound when resuming coverage still blocks
  the second duty, even without a fixed-vacancy equality. Coverage search must
  not inherit quality-phase bounds.

The existing `CpModel.clone()` mechanism is sufficient for phase isolation; no
new optimizer/library is needed. A future bounded quality attempt should run on
a clone constrained to incumbent coverage, retain its own objective/bound scope,
and preserve the independently valid fallback. If coverage is not proven, its
public overall status must remain FEASIBLE even when that clone returns OPTIMAL.
Any resumed primary coverage search must use the primary constraints, not the
clone's quality restrictions. Compare candidates lexicographically, rather than
comparing vacancy objectives against weighted quality objectives. Preserve
independent validation/separation in both searches and a shared wall-clock
deadline. Budget allocation and actual same-input performance remain open;
these counterexamples are contract evidence, not a delivered anytime strategy.

The same production-model clone contract now additionally exercises four
configured restrictions: an eight-hour weekly cap, an eight-hour daily cap
against a nine-hour duty, eleven-hour inter-duty rest against a ten-hour gap,
and an approval expiring before the second duty. Both primary and fixed-coverage
quality models choose one valid eight-hour duty; forcing zero vacancies remains
INFEASIBLE in both. In the approval case, the forbidden assignment variable is
absent entirely (candidate filtering), rather than merely penalized. These are
synthetic explicit configurations, not inferred limits for the user's project.
`test_quality_clone_preserves_configured_hard_constraints` independently validates
each chosen plan. This evidence covers cloning these constraints, not the future
scheduler's deadline handling or its validator-driven separation loop; those
still require runtime integration and timeout tests before enabling anytime search.

Four further clone contracts isolate elapsed-time semantics: overlapping duties
remain incompatible even with zero configured inter-duty rest; two duties paying
only one hour each still cannot exceed an explicit eight-hour daily or weekly
elapsed-time cap. Both the coverage model and its fixed-coverage quality clone
reject forced full coverage and independently validate their one-duty solution.
Conversely, a single 24-hour duty paying eight hours remains feasible in both
models when no daily/weekly maximum forbids it. This is a synthetic configuration,
not evidence that any particular customer duty is permitted. These tests prevent
an hours-quality objective from being mistaken for an elapsed-time limit and
avoid inventing a blanket 24-hour ban. No search-runtime behavior changed.

### Bounded conditional quality search (candidate, 2026-09-11)

`solver.solve` now reserves 20% of the budget remaining after model construction
and warm-plan certification for a conditional quality search. The production
CP-SAT model is cloned after an independently validated coverage incumbent is
found; its exact vacancy count is fixed, and its weighted cost is an upper bound
for the second phase. Complete solution hints reuse the existing CP-SAT path.
No new dependencies, business limits, approvals or mandatory employee assignments
are introduced. Both phases use the original shared deadline and independent
validator/separation loop. This is a bounded two-phase policy, not an alternating
search that resumes primary coverage later.

The allocation is a heuristic, not evidence that 80/20 is optimal: it may miss
coverage improvements that a longer first phase would find. It never accepts
worse coverage or weighted quality than the validated incumbent used to start
the quality phase. If coverage is unproven, even native conditional OPTIMAL is
reported as FEASIBLE, with `quality_scope` and `parameters.coverage_proven=false`.
The quality objective and bound concern only the fixed-coverage subproblem.
UNKNOWN in quality retains the previous result and its vacancy objective/bound.
If the first coverage search returns UNKNOWN, this candidate retains the existing
validated warm fallback (if any); it does not yet start quality from that fallback.

Updated synthetic regressions in `tests/test_partial_limits.py` demonstrate
960→0 minutes of avoidable target deviation at unchanged nonzero vacancies;
this is not a timed performance benchmark or a hard maximum-hours violation.
`tests/test_anytime_quality_contract.py` checks UNKNOWN fallback, allocated first
phase budget and the existing hard-rule clone contracts.
`tests/test_api_adapter.py::test_imported_fixed_replacement_timeout_preserves_only_valid_incumbent`
now also exercises conditional quality while preserving imported fixed duties
and rejecting a stricter configured elapsed-time weekly maximum independently.
The configured private 600-second Worker gate must establish practical behavior
before this candidate is described as an improvement on the real project.

### Per-search evidence for the bounded strategy

`solver.solve` records `parameters.search_trace`, an identifier-free list of
search attempts in this run. Each entry records its phase, elapsed start time,
allocated budget, actual search duration, native status, independent-validation
state and whether it became the accepted incumbent. Only accepted, independently
checked candidates include actual vacancy count, weighted quality cost and the
phase-local objective and bound. A native OPTIMAL candidate rejected by validation
is **not** an incumbent. UNKNOWN has no fabricated objective or quality cost.
The warm-plan certificate is still reported separately by the existing
`warm_start_certificate_*` parameters; it is not a search-trace entry.

These measurements do not change budget allocation, constraints or selection.
They allow comparison of coverage and weighted costs **within the same run**,
including quality UNKNOWN returning the earlier coverage incumbent. Native
conditional OPTIMAL remains distinct from the public overall FEASIBLE status.
`test_conditional_quality_shares_original_deadline` checks timings, budgets and
JSON round-trip; the UNKNOWN and rejected-candidate tests check that failed
attempts cannot masquerade as improvements. The two
`test_equal_coverage_feasible_incumbent_reaches_conditional_quality` cases now
verify the actual 960-to-0 quality change in the trace at unchanged coverage.
These are deterministic synthetic assertions, not evidence of improved coverage
or runtime on the private project. The fixed 80/20 policy remains a candidate;
phase-level measurements on the private 600-second case are still needed before
choosing a better coverage/quality scheduling policy.

### Reproduced outer context overnight mismatch (2026-09-11)

`sp5_adapter.import_snapshot` sets both the queried schedule-date interval and
`Snapshot.context_end` to `period_end + 31 days`. Its monthly schedule loop
includes rows starting on that final day. The boundary branch parses
`SHIFT.STARTEND{day_index}`, carries overnight ends to the following day, and
preserves the entire interval in `BoundaryWork`. However, the generated profile's
`valid_until` and snapshot context still end on the starting day.
`domain.input_diagnostics` correctly rejects work ending after midnight following
`context_end`. Thus a normal 20:00–08:00 duty on the last queried date produces
`context` and can block model construction even though the imported interval
itself is valid. A 20:00–00:00 control is accepted by that specific check.

`test_final_context_day_overnight_import_exposes_extent_mismatch` characterizes
both outcomes at two calendar dates (including a context end on the Vienna DST
transition date): four synthetic cases, with duties preserved, no invented
approvals and context completeness still false. These passing characterization
tests document an **unfixed importer extent defect**, not a corrected runtime or
evidence that overnight/24-hour work is categorically forbidden. The existing
181 adapter cases pass. An initial test-only attribute typo (`rule_profiles`
instead of `profiles`) was corrected before obtaining this result.

The next correction must distinguish the source **start-date query window**
from the extent of the actual imported intervals, cover profile applicability,
and preserve explicit incomplete-context diagnostics. Simply fetching one more
day recreates the same issue at the new outer edge; merely extending a declared
complete context would claim unqueried coverage. No validator relaxation or
removal/truncation of boundary work is justified. This evidence concerns the
fresh-import MODEL_INVALID path, not proof of the original 0.9.29 report's cause.

### Corrected source-window versus interval envelope (candidate, 2026-09-11)

The previously characterized outer-edge defect is now corrected in
`sp5_adapter.import_snapshot`. Monthly reads and row filtering use a fixed
`source_start`/`source_end` window. `metadata.context_source_window` records its
inclusive start dates, `selection=schedule_start_date`, and `complete=false`.
After importing work, the snapshot context and the **unconfirmed** generated
profile cover the actual interval envelope using the existing UTC-minute
`timeutils.bounds`/`local_day` helpers. Half-open intervals ending exactly at
midnight do not add an extra occupied day. No recursive next-day fetch, duty
truncation, invented hours, new approval or validator relaxation is involved.
`context_complete=false` and the explicit unresolved context-confirmation notice
remain in place; an expanded envelope is not proof of unqueried source coverage.
Existing saved projects and explicitly configured profiles are not rewritten.

The API path is `api_adapter._Database.get_schedule` (`/api/schedule`, year/month/group/plan)
→ `import_api` → the same `import_snapshot` implementation. Upstream Library
`SP5Database.get_schedule` and API `routers/schedule.py::get_schedule` expose
calendar-dated rows, not a guarantee that all intervals finish inside that
calendar selection. The importer constructs the overnight intervals from
`SHIFT.STARTEND{day_index}`; therefore the envelope correction belongs here,
not in OSP5's display or an invented maximum duty duration.

`test_final_context_day_overnight_preserves_extent_and_source_window` replaces
the prior characterization with six regressions: midnight/overnight controls,
Vienna DST-date context and a month-end context edge. It checks unchanged query
month limits, complete preserved work, profile extent, absent approvals and
unconfirmed context. Deliberately shortening the corrected envelope still
produces the validator's `context` error. These tests address one fresh-import
MODEL_INVALID cause, not the unverified original 0.9.29 input/result pair.

### Explicit special-duty boundary intervals (candidate, 2026-09-11)

A separate nominal-only normalization defect is now reproduced and corrected for
**out-of-period personal work**. Source data flows from `5SPSHI.STARTEND` and
`DURATION` through Library `SP5Database.get_spshi_entries_for_day` (database.py),
API `sp5api/routers/schedule.py::get_einsatzplan` (`GET /api/einsatzplan`), and
Generator `sp5_adapter._scope_schedule`'s unique person/service/workplace/type
join into `import_snapshot`. OSP5 `SonderdiensteModal` in
`frontend/src/pages/Einsatzplan.tsx` maintains `startend` and `duration` as
separate inputs and submits both. They are not required to equal the nominal
`SHIFT.STARTEND{day_index}` / `DURATION{day_index}` fields.

Previously the importer accepted a TYPE-0 special row only when both its actual
windows and paid minutes exactly matched the nominal service. This rejected
known overnight/split work, known times with different pay, and valid actual
work whose nominal slot was empty. The normal person-day replacement had already
been removed; a generic blocking unresolved notice remained. This was **not**
silent successful planning with missing work, but a concrete fresh-import
MODEL_INVALID cause. Four synthetic cases fail before the correction because
no `BoundaryWork` is produced; their four in-period controls correctly remain
blocked.

The boundary branch now uses the existing `BoundaryWork` contract with explicit
SPSHI intervals for known-service TYPE-0 rows with valid nonnegative paid details.
It never substitutes nominal windows. `provenance` separately retains
`time_source=sp5:SPSHI.STARTEND`, `paid_source=sp5:SPSHI.DURATION`, paid minutes,
unique detail ID where available and replaced normal rows. Paid values do not
become worked duration, period target credit or a staffing requirement. Distinct
explicit windows at the same person/date/service/workplace get distinct stable
boundary identities; duplicate identical source rows still count once.

No source row, employee approval, profile confirmation, day/night confirmation,
context completeness flag or in-period special-work blocker is invented or
cleared. Unsupported types/services and missing/invalid details remain blocking.
Within the planning period only the existing exact nominal mapping is supported:
`BoundaryWork` cannot be used to hide such work because `domain.input_diagnostics`
rejects it with `boundary_period`. The established solver/validator consume
boundary intervals for elapsed daily/weekly limits, overlaps and rest, not paid
period targets (see `tests/test_boundary_work.py`, particularly
`test_boundary_context_preserves_hard_rules_without_staffing` and
`test_elapsed_limits_target_and_roundtrip`).

New adapter regressions cover actual-versus-nominal intervals, split work,
paid-only differences, empty nominal slots, missing/invalid/negative/nonfinite
details, distinct same-service duties and Vienna DST (9/11 real hours with
2 paid hours retained separately). Existing Ist/Soll API replacement tests now
verify actual six-hour boundary work instead of the old blanket rejection,
while unsupported TYPE/service and in-period cases remain strict. This correction
addresses a supported subset of the fresh-import blocker, not the unestablished
original 0.9.29 input/result pair, nor a claim that every employee must be assigned
or 24-hour duties violate an unspecified maximum.

`test_imported_special_boundary_enforces_actual_time_in_solver_and_validator`
additionally connects the actual importer output to an explicitly configured
synthetic project: twelve elapsed context hours versus four paid source hours,
followed by four proposed work hours. Both solver modes reject the proposal at
959 weekly minutes, 719 daily minutes or a 241-minute rest requirement (the actual
gap is 240). Empty new work is valid; deleting the imported context in a test-only
counterfactual incorrectly admits the duty. This proves the safety effect without
conflating it with missing import confirmations. A separate 24-hour actual-window
case is preserved rather than categorically prohibited.

### Import notices versus native solver invalidity (2026-09-12)

`Snapshot.unresolved` mixes specific source/mapping failures with explicit
review/confirmation notices. `sp5_adapter.import_snapshot` seeds profile/kind/
approval review, source consistency and boundary-context notices; it separately
adds period credit/balance review and conditionally team-scope/staffing
interpretation notices. `api_adapter.import_api` appends API mapping, visibility/
cache/completeness and out-of-selection membership review notices. These entries
are strings, not dynamically resolved predicates linked to the current profile,
approval or source-record state.

Consequently, applying offered approvals and confirming the imported profile or
duty kinds does not itself remove those notice strings. This is distinct from
still-missing actual source windows or unsupported in-period special work.
`domain.input_diagnostics` emits `unresolved` for **every** remaining string;
`solver.solve` returns public `MODEL_INVALID` on these input diagnostics **before
constructing `cp_model.CpModel`**. The later native CP-SAT `MODEL_INVALID` branch
is a different failure path. A successful HTTP/Worker job carrying this public
status proves neither native solver execution nor a generated plan.

The existing UI's `app.js::renderUnresolved` has an explicit per-notice
"Nach fachlicher Korrektur als geklärt markieren" action. This audit does not
invoke it on private data or treat accepting history proposals as blanket
permission to erase notices about source completeness, balances, missing work,
team scope or unsupported mappings. Neither should a report label every remaining
notice as a missing source row or as a hard-time-limit violation. Future issue
lifecycle work should distinguish the already-existing confirmation requirement
from a concrete unresolved mapping, without inferring either one is satisfied
from successful import, elapsed search time or a profile checkbox alone.


### Controlled quality-gain counterexample (2026-09-12)

`tests/test_anytime_quality_contract.py::test_certified_hint_allows_real_fixed_coverage_quality_gain`
now exercises the production `solver.solve` certificate → coverage → conditional
quality path with **real CP-SAT statuses and solutions**, not a mocked improving
result. Two approved employees each target eight hours; the saved, mutable plan
assigns both eight-hour duties to one employee. The only active soft objective is
absolute target deviation. The test stops coverage at its first incumbent, then
allows actual quality optimization at exactly that coverage. A second variant
adds an unfillable demand whose function neither employee is approved for.

All four combinations (zero/one unavoidable vacancy × quality presolve off/on)
reduce weighted hours deviation from 960 to zero while retaining exactly the same
vacancy count. The independent validator accepts both phase results. The final
plan has eight paid hours per employee. The test checks that quality receives a
complete hint and does **not** fix variables to their hinted values. The saved
assignments stay mutable; no approval, staffing or time rule is relaxed.

This disproves a universal claim that complete certified hints, or disabled
presolve alone, prevent the quality phase from changing assignments. It does not
explain the zero improvement observed in the large private 108-second quality
phase, establish that enabling presolve improves that instance, or validate the
80/20 split as a generally better policy. That requires a controlled same-input,
same-incumbent fixed-coverage comparison with native search statistics. Production
parameters remain unchanged; this is a synthetic search-regression addition, not
a new runtime or release. The existing zero-gain private trace remains the latest
large-instance evidence.

### Fixed-coverage quality includes configured change costs (2026-09-12)

The controlled certified-hint test above additionally varies the configured
`changes` weight (0, 100, 600). `solver.solve` builds the `changes` component
against the original saved `(employee_id, demand_id)` pairs: transferring one
duty removes one pair and adds another. Both changes count. The quality phase
retains this original baseline; it does not rebase change costs onto the latest
coverage incumbent.

With the same two eight-hour duties and two eight-hour targets, a transfer reduces
absolute hours deviation from 960 to zero but costs twice the change weight.
Actual CP-SAT quality search therefore reaches costs 0 and 200 for the first two
weights, and retains the original cost 960 when the weight is 600 (a transfer
would cost 1200). This is checked for both presolve settings and both zero/one
unfillable vacancy. Independent arithmetic from the final assignment-pair
symmetric difference and paid hours verifies the full active weighted objective;
the independent validator verifies the hard rules. The synthetic high-weight
case is a concrete reason that an unchanged personnel distribution need not be a
solver defect. It is not evidence that change costs explain any specific private
plan, nor permission to change the user's objective weights or require every
employee to be assigned.

`test_fixed_coverage_quality_can_add_only_configured_optional_staffing` covers
another distinct mechanism with real production CP-SAT phases: a demand with
minimum one and maximum two already has its minimum filled by the saved plan.
Both approved employees target eight hours. Adding the second employee preserves
zero vacancies and reduces the complete active cost from 480 to 100 (hours plus
one added assignment). The paired maximum-one case retains the original single
assignment and cost 480. Both results independently validate. Thus fixed coverage
means fixed *missing minimum staffing*, not a fixed assignment count; optional
staffing may improve configured quality only within the existing maximum. Neither
an employee target nor a quality weight creates additional demand capacity.

### Local neighbourhood optimality is not quality optimality (2026-09-12)

Before promoting a bounded neighbourhood search, the production-model regression
`test_neighbourhood_optimal_does_not_prove_fixed_coverage_quality` establishes a
second proof-scope boundary. Four optional duties, each with 120 paid minutes,
can meet a 480-minute target at zero vacancies. Starting from the independently
valid empty plan, a clone restricted to two assignment additions proves native
`OPTIMAL` with 240 minutes of target deviation. The unrestricted quality clone
also proves native `OPTIMAL`, but reaches zero deviation at identical coverage.
Both plans independently validate; all configured hard constraints are retained.

Thus even **proven coverage** does not permit a neighbourhood's native optimal
status or bound to stand in for unrestricted quality optimality. A future local
candidate mechanism must preserve the incumbent on failure, independently validate
accepted candidates, compare the original full weighted objective, share the
original deadline, and expose the narrower proof scope. The restriction must not
leak into subsequent general search or become a new staffing rule.

Existing-solution preflight: OR-Tools already provides LNS and RINS neighbourhood
generators; `use_lns_only` is explicitly experimental in the
[version 9.15 parameter definitions](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto).
Their availability alone is not evidence of a gain for this application's worker
configuration or a reason to change production parameters. This change adds a
synthetic proof-scope regression only, not a new production search policy.

The native dispatch also matters: in the tagged
[9.15 `cp_model_solver.cc`](https://github.com/google/or-tools/blob/v9.15/ortools/sat/cp_model_solver.cc),
`SolveCpModel` enters `SolveCpModelParallel` for multiple workers, interleaved
search, explicit/filter subsolvers, or `use_ls_only`. Merely setting
`use_lns_only` is not one of those dispatch conditions. Generator
`solver.SEARCH_WORKERS = 1` and the solver parameter setup do not enable the
other conditions. Therefore the existence/default availability of native LNS
generators must not be mistaken for evidence that this production sequential
path already runs an LNS portfolio. A native comparison would need a deliberately
configured, separately verified dispatch (potentially one-worker interleaving),
not an untested increase in worker count: the single-worker policy preserves a
previously established process-safety workaround.


### Native one-worker interleaved LNS safety probe (2026-09-12)

`test_native_single_worker_lns_preserves_hard_weekly_cap` exercises the existing
OR-Tools portfolio with both `interleave_search=True` and `use_lns_only=True`,
keeping one worker. On a synthetic two-duty production model, both coverage and
fixed-coverage quality retain the configured eight-hour weekly maximum. Forcing
both eight-hour duties makes the quality clone infeasible. Returned assignments
also pass the independent validator. This is a narrow safety probe, not proof of
process safety for all instances, a performance benchmark, or permission to infer
weekly maxima from nominal targets.

Production search parameters remain unchanged. Before adoption, this alternative
needs integrated shared-deadline, incumbent fallback, status/proof-scope and Worker
checks. Native LNS keeps the model's original feasible region; unlike an explicit
two-addition restriction, no application-level neighbourhood constraint is added.
Its mere use still does not establish optimal quality or maximum contiguous rest.

### Quality-only native LNS integration contracts (2026-09-12)

The candidate portfolio is now exercised inside the actual `solver.solve` phase
loop by test-local parameter injection, without changing production defaults.
`test_conditional_quality_shares_original_deadline` runs real native quality
search after a controlled FEASIBLE coverage phase: the budgets remain 2.4 and
0.45 seconds for a three-second request (including the existing finalization
allowance). Native quality OPTIMAL still returns overall FEASIBLE when global
coverage is unproven. The companion UNKNOWN regression injects a no-result
quality status and verifies preservation of the independently valid coverage
incumbent; it tests fallback handling, not native timeout frequency.

`test_certified_hint_allows_real_fixed_coverage_quality_gain` additionally runs
the native one-worker interleaved portfolio for both presolve settings, with and
without an unfillable demand, and change weights 0/100/600. Full objective costs
remain 0/200/960: the last case correctly retains the original personnel
allocation because transferring a duty costs more than its hours-deviation gain.
Only quality receives candidate parameters; coverage and hint certification keep
their production settings. These deterministic small cases establish contracts,
not a large-instance performance improvement or a requirement to staff everyone.

The hard-constraint clone matrix also runs with native interleaving for all seven
cases: paid weekly/daily limits, elapsed weekly/daily limits, inter-duty rest,
overlap and dated personal approval. Forcing full coverage remains infeasible
where those configured constraints prohibit it. The fresh-process demo regression
runs three native-portfolio and three unchanged sequential searches on the
12-person, 14-day demo; all exit cleanly with independently complete validation.
This extends the known crash regression, but is not a guarantee against native
failures on other data. Controlled private full-Worker/deadline comparison and
relevant API gates remain prerequisites for runtime promotion.

### Rejected quality candidate followed by timeout (2026-09-12)

`test_rejected_quality_then_timeout_retains_certified_incumbent` closes a distinct
fallback gap in the integration evidence: a real quality search improves the
synthetic hours cost from 960 to zero, but test-local validator fault injection
rejects that candidate. Subsequent UNKNOWN or shared-deadline exhaustion must
return exactly the previously certified personnel allocation and its original
cost, never the rejected improvement. All four combinations of sequential/native
quality and UNKNOWN/deadline pass, including result JSON round-trip. The search
trace marks the candidate independently invalid and unaccepted and does not
publish its quality cost as an accepted result. The injected rejection is not an
observed native constraint violation. No runtime parameters or rules changed;
private full-Worker comparison remains required before promotion.
