# Belegte Quellsemantik für Import und Planung

Lesestand der drei unveränderten Checkouts am 11.09.2026:
Library `0dac4438c0be02c1ad612f54d4aba75a3e4d6335`, API
`d578f212d635b672ab277d7d29a37387145506f5`, OSP5
`addf5c2d1e40b4f266bacf1cd41f40ef70edbeb8`.
Dies ist eine eingegrenzte Datenflussanalyse, keine vollständige fachliche
Abnahme aller Originaltabellen. Keine realen Datensätze sind enthalten.

## Aktueller Korrekturstand gegenüber 0.9.29

Konsolidierter Code-/Teststand: `9581f28` (11.09.2026). Die nachfolgenden
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
- Die private Abnahme des veröffentlichten Stands 0.9.30 (`56cf7cf`) sowie
  die spätere Abnahme mit vollständigem Runtime-Overlay `9581f28` belegen
  Import/Speicherung, nicht erfolgreiche Neuplanung: beide Plansichten bleiben
  wegen fehlender Einrichtung MODEL_INVALID, ohne generierte Einteilungen.
  Das Overlay ist kein veröffentlichtes Image. Kein unabhängig gültiger realer
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
