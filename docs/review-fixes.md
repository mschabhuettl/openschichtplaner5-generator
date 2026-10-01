# Reviewkorrekturen für 0.29.1

Basis: Version 0.29.0, Commit `ee8f442c7d35dee6fbe7f2a3bf4cd5abd16e7010`.
Ziel ist der Patchstand [0.29.1](release-0.29.1.md), nicht der spätere UX-Umbau.
Diese Übersicht beschreibt den umgesetzten Reparaturumfang, keine abgeschlossene
unabhängige Gesamtabnahme und kein veröffentlichtes Release. Bestehende Projekte
werden nicht automatisch migriert. Tests und Beispiele verwenden ausschließlich
synthetische Daten.

## Fachliche Prüfung und Planung

- **CORE-001:** Der unabhängige Validator prüft persönliche Grenzen anhand
  bezahlter Periodenminuten einschließlich persönlicher Arbeit. Guthaben
  oder Anfangssalden vermindern die geleistete Arbeit nicht.
- **CORE-002:** Zeitbehaftete Nachtblock-Nachbarn werden nach UTC-Anfang
  bestimmt. Reihenfolge der Einteilungen und DST-Folds ändern das Urteil nicht.
- **CORE-003:** Persönliche Arbeit ohne Uhrzeiten wird nicht als Zeitintervall
  behandelt; ihre Tagessperre und Minuten bleiben wirksam.
- **CORE-004:** Leere Alternativkennungen bedeuten unabhängigen Bedarf.
  Gruppierung und Deckungszählung sind konsistent; Vollpläne mit offenen
  Mindeststellen werden nicht als gültige Incumbents übernommen.
- **CORE-005:** Zertifizierte Warmstart-Rückfallpläne zählen gemeinsame
  Bedarfsalternativen wie der normale Ergebnisweg.
- **CORE-006:** Späte Teile ausgewählter Dienste aktivieren die betroffenen
  Arbeitstagsserien und Kontextprüfungen; ungewählte Kandidaten nicht.

## Import, Export und Ersatzsuche

- **DATA-01:** Historische Ist-Dienste werden vor Nachweis- und Bedarfsableitung
  um ersetzte personenbezogene Tageszeilen bereinigt. Soll bleibt getrennt.
- **DATA-02:** CSV und XLSX verwenden dieselbe vollständige Arbeitsliste für
  Details, Kalender und Salden. Persönliche Arbeit ohne Zeiten bleibt als
  solche erkennbar; Randkontext erhält keine zweite Periodengutschrift.
- **DATA-03:** Ersatzkandidaten werden mit dem hypothetischen Gesamtplan
  validiert. Eine Übernahme der ganzen Abwesenheit wird gemeinsam geprüft,
  nicht aus der Schnittmenge isolierter Empfehlungen behauptet.
- **DATA-04:** Die Ersatzsuche erhält das Datum zeitloser persönlicher Arbeit
  und prüft die Tagessperre ohne erfundene Uhrzeiten.

## Runde 6: Zahlentreue (unabhängige Abnahme ausstehend)

Der lokale `ProjectJSON`-Codec schließt den nachgewiesenen Verlust beim tatsächlichen
Öffnen → Prüfen → Speichern: große Integer, integralwertige Floats und negative
Float-Null behalten ihre Bedeutung. Die gemeinsame Transportgrenze, Datei-/JSON-
Editor, Assistent, native Klone, JSON-Sicherung, Export und numerische Anzeige-
Verbraucher wurden angepasst. Nicht unterstützte Werte werden vor Zustandswechsel
oder Transport ausdrücklich zurückgewiesen. Verzögerte Antworten bleiben an den
ursprünglichen Eingabestand gebunden.

Regressionen: `tests/review_json_numeric_codec.test.cjs` mit unabhängigem
`tests/json_numeric_oracle.py`, vollständige UI-Handler-/Modultests und
`tests/browser/review-numeric-fidelity.cjs` mit synthetischem realem HTTP/SQLite-
Nachweis und Python-Orakel. Die neuen Tests laufen in `npm test --prefix tests/browser`.
Die Implementierungsnachweise ersetzen keine neue unabhängige Prüfung des eingefrorenen
Kandidaten. Runde 6, Gesamtabnahme und Veröffentlichung von 0.29.1 sind hiermit
**nicht** abgeschlossen.

## Oberfläche

- **UI-001:** Mutierende Aktionen sind zentral gesperrt, solange ein
  schreibender Vorgang läuft. Speicherbestätigung und Berechnungsergebnis
  gehören zur konkreten Projektinstanz und Änderungsversion.
- **UI-002:** Einstellungsübernahme erhält Ausschluss und persönliche Grenze,
  auch null Minuten. Bei anderem Zeitraum bleibt eine bestehende Grenze
  konservativ erhalten und wird zur ausdrücklichen Überprüfung vorgelegt.
- **UI-003:** Familienerweiterungen erhalten Begleitpflichten, auch im
  historischen Sammelpfad.
- **UI-004:** Veraltete Ersatz- und Freigabeanalysen werden verworfen;
  projektbezogene Suchauswahl und Berichte werden passend zurückgesetzt.
- **UI-005:** Gemeinsame Bedarfsalternativen zählen in Kopfzeile, Kalender
  und Mindeststundenabschätzung nicht als zusätzliche Pflichtstellen.
- **UI-006:** Die Familiensuche berücksichtigt auch Namen und Kennungen
  ihrer einzelnen Zeitlagen.
- **UI-007:** Beim Entfernen einer Person werden persönliche Arbeit und
  zugehörige Verweise konsistent entfernt.
- **UI-008:** Beide Browser-CSV-Exporte schützen Text vor Formelinterpretation.
  Team-CSV kennzeichnet die reversible Textkodierung; ältere sechs-spaltige
  Dateien bleiben wörtlich lesbar. Kennungen werden nicht still getrimmt.
- **UI-009:** Dateiinputs bleiben nativ tastaturbedienbar und erhalten einen
  sichtbaren Fokusrahmen.
- **UI-010:** Abmelden bleibt in schmalen Ansichten erreichbar. Das native
  Formular übermittelt weiterhin einen zulässigen Same-Origin-Header und
  widerruft die tatsächliche Sitzung; die Backend-Originprüfung bleibt bestehen.

## Betrieb und Verträge

- **SEC-03:** Web-Worker werden an ihren Elternprozess gebunden. Der separate
  CLI-Worker bleibt unabhängig. Absturz und Wiederanlauf werden mit echten
  Prozessen, Dateisperren und einem anschließenden Auftrag geprüft.
- **SEC-04:** Begrenzte Kennungen, Sammlungen, Parse- und Diagnosebudgets
  verhindern die reproduzierte Antwortverstärkung. Gekürzte Anzeigen erhalten
  vollständige Fehlerzahlen; ein Budgetabbruch ist kein gültiges Prüfergebnis.
  Details und Kompatibilitätsgrenzen stehen in [Webbetrieb](web-operation.md).
- **CONTRACT-01:** Beide eingecheckten Schemata entsprechen den Laufzeitmodellen
  und der CLI. Ein CI-Test verhindert erneutes Auseinanderlaufen.
- **DOC-01:** README-Version, Wheelbeispiel und Releaseverweis entsprechen dem
  Paketstand. Die [Schema-Kompatibilitätsstrategie](architecture.md) ist dokumentiert.

## Zusätzliche Randfälle aus den Nachprüfungen

### Arbeitsminuten, Ersatzsuche und Export

- **DATA-03:** Die gemeinsame Ersatzprüfung betrachtet alle anderen Personen,
  unabhängig von den Einzelkandidatenlisten. So bleibt auch eine zulässige
  gemeinsame Übernahme sichtbar, wenn erst ein zusätzlicher Nachtdienst zwei
  Nachtblöcke verbindet und die isolierte Übernahme noch unzulässig wäre.
  Maßgeblich ist die Gültigkeit des vollständigen hypothetischen Plans; offene
  Stellen allein werden nicht zu einem persönlichen Ausschlussgrund.
- **DATA-02 / CORE-001:** Für bezahlte Periodenminuten zählt der lokale Anfangstag
  der Arbeit beziehungsweise `day` bei Arbeit ohne Uhrzeiten, nicht allein das
  Importkennzeichen `in_period`. Normale Solverkennzahlen, zertifizierte
  Rückfallpläne, erreichbare Ziele, aggregierte Sollerfüllung und die Last des
  Startplans folgen jetzt dieser Rechnung. Persönliche harte Grenzen hatten im
  Solver bereits diese Semantik; ihre Grenzfälle bleiben eigens geprüft.
  Die erforderliche Bestätigung zeitbehafteter persönlicher Periodenarbeit
  entfällt dadurch nicht. Randdienste mit hineinragendem Ende erhalten keine
  erneute Periodengutschrift.
- **DATA-02 / DATA-R2-01:** Optionale Provenienz wird bis zu den einzelnen
  Feldwerten geprüft. Unbrauchbare Container, Typen oder Texte verwenden
  Ersatzbeschriftungen. Verwendbare Zeichenketten bleiben exakt; optionale
  Arbeitsplatzwerte unterstützen auch verlustfrei darstellbare native Ganzzahlen.
  Formelschutz und zusammengesetzte Kalenderzellen sind im Textbudget enthalten.
  Arbeitsdaten, Minuten und exakte Arbeit-IDs bleiben beim CSV-/XLSX-Export erhalten.
- **DATA-02:** Der CSV-Dateiexport erzeugt zunächst eine temporäre Datei im
  Zielverzeichnis, schließt sie und ersetzt erst danach das Ziel atomar. Fehler
  bei Zeilenerzeugung, UTF-8-Kodierung oder Ersetzen hinterlassen weder einen
  überschriebenen bisherigen Export noch eine teilweise neue Zieldatei;
  temporäre Dateien werden bei diesen Fehlern entfernt. Diese Zusage betrifft
  CSV, nicht eine allgemeine Transaktion über mehrere Exporte.

Quellbezug: `replacement.py`, `solver.py`, `export_work.py` und `export.py` in
`sp5generator/`. Regressionsvertrag:
[`tests/test_review_data_followup.py`](../tests/test_review_data_followup.py),
[`tests/test_review_provenance_values.py`](../tests/test_review_provenance_values.py),
ergänzend [`tests/test_review_data.py`](../tests/test_review_data.py).

### Parsebudgets und Diagnoseauswahl

- **SEC-04 / SEC-R2-MAPPING-PARSE-BUDGET:** Das gemeinsame Parsebudget erfasst
  die vollständige Anfrage einschließlich externer Einteilungen, unbekannter
  Felder und abgeleiteter Anfrageformen für Ersatzsuche und Export. Es zählt
  eine Wurzeleinheit und je einen Mapping-Eintrag oder Listen-/Tupelplatz;
  skalare Werte und leere Container umgehen die Vorprüfung nicht. Die Grenze
  von 50.000 Einheiten ist keine Zusage für 50.000 vollständige Datensätze.
  Nur der Inhalt des tatsächlichen Snapshot-Metadatenfelds ist ausgenommen,
  nicht beliebige gleichnamige Felder. Die gesamte HTTP-Anfrage unterliegt
  weiterhin dem Bodylimit. Schemafehler werden erst nach der Vorprüfung erzeugt.
- **SEC-04:** Eine einzelne zu große Diagnose beendet die Anzeigeauswahl nicht.
  Spätere kleinere Meldungen können noch erscheinen, auch bei UTF-8-Expansion
  oder nur noch knappem Restbudget. Vollständige Statusflags, Gesamtzahlen,
  ausgelassene Zahlen und Zählungen nach Fehlercode bleiben maßgeblich. Ein
  Abbruch der Diagnoseerzeugung bleibt ein fehlgeschlagener Check, kein Teilurteil.

Quellbezug: `sp5generator/security_limits.py` und `sp5generator/webapp.py`.
Reale synthetische ASGI-Regressionsanfragen stehen in
[`tests/test_review_security.py`](../tests/test_review_security.py) und
[`tests/test_review_mapping_budget.py`](../tests/test_review_mapping_budget.py).

### Normalisierung, Speicherung und erneutes Einlesen

- **SEC-R3-BUDGET-ROUNDTRIP:** Eine Eingabe unter dem Vorprüfungsbudget kann durch
  ergänzte Modell-Defaults größer werden. Der Reparaturvertrag prüft deshalb
  zusätzlich das normalisierte Modell gegen dieselbe Grenze, vor Erfolgsantwort
  und Speicherung. Die vollständige Plan-/Ersatzanfrage hat ein gemeinsames
  Budget; ein maximaler Snapshot allein garantiert keinen Platz für zusätzliche
  Anfragefelder. Frühere Validierung, `model_copy` und native Mutationen dürfen
  die endgültige Übergabeprüfung nicht umgehen.
- **SEC-R4-WIRE-ROUNDTRIP:** Das Planungsbudget allein sichert nicht das erneute
  Einlesen der HTTP-Ausgabe. Die kompakte UTF-8-JSON-Darstellung des endgültigen
  Snapshots muss vor HTTP-Ausgabe oder dauerhafter Speicherung ebenfalls in die
  unveränderten 16 MiB passen. Metadaten bleiben vom Planungsbudget ausgenommen,
  nicht vom Bytebudget. In-Memory-Tabellenexport und optionaler Beschriftungsfallback
  sind keine JSON-Transportgrenze.
- **Prüfvertrag:** Grenz- und gewöhnliche sparse Eingaben werden über
  Normalisierung, Speicherung, Lesen, Kopieren, Archivieren, Wiederherstellen und
  echte CLI-Worker geprüft. Abgewiesene Überschreibungen müssen den vorherigen
  Datenbankzustand vollständig erhalten; unlesbare Bestände dürfen keinen neuen
  Job erhalten. Post-Import-/Historienänderungen, neue Projekte und native
  Modelländerungen gehören ebenso zum Umfang wie Bytegrenzen und UTF-8-Zeichen.
  Einzelne bestandene Annahmeprüfungen ersetzen diesen Lebenszyklusnachweis nicht.

Die [Architektur](architecture.md) beschreibt den gemeinsamen Annahmevertrag.
Portable Regressionen stehen in
[`tests/test_review_budget_roundtrip.py`](../tests/test_review_budget_roundtrip.py),
[`tests/test_review_native_admission.py`](../tests/test_review_native_admission.py)
und [`tests/test_review_wire_admission.py`](../tests/test_review_wire_admission.py).
Diese Zuordnung beschreibt die Abnahmekriterien, nicht eine bereits erfolgte
Gesamtfreigabe des Kandidaten.

### Überlappende Bedienung, Begleitung und Berichte

- **UI-001:** Projekt- und Aktionssperren bleiben bei überlappendem CSV-Einlesen
  und Speichern in beiden Abschlussreihenfolgen wirksam. Eine vorübergehende
  Sperre wird nicht als dauerhafter Disabled-Zustand wiederhergestellt.
- **UI-003 / UI-R2-003:** Eine aktive arbeitsplatzübergreifende Begleitpflicht (`*`) bleibt
  beim Ergänzen einer konkreten Arbeitsplatzfreigabe erhalten. Die Vererbung
  innerhalb einer Tätigkeitsfamilie hängt nicht vom Gruppierungsschalter der
  Matrix ab, auch nicht bei konkreten historischen Arbeitsplatzvorschlägen.
  Familienzugehörigkeit und Geltungsbereich der Freigabe werden getrennt
  bestimmt; eine konkrete Freigabe wird nicht zu `*` erweitert. Der Entzug
  wird nicht auf zusätzliche Bereiche erweitert.
- **SEC-04 / UI:** Automatische und manuelle Bereitschaftsprüfung sowie
  Planvalidierung zeigen Gesamtzahl, angezeigte und ausgelassene Diagnosen.
  Eine zulässige leere oder gekürzte Anzeige wird weder als Transportfehler noch
  als bestandene Prüfung fehlinterpretiert. Widersprüchliche
  Bereitschaftszahlen führen nicht zur Planungsfreigabe.
- Die Browserregressionen verwenden getrennte synthetische Stores, vom Kernel
  gewählte Ports und begrenzte Warte-/Aufräumzeiten. `WEB_TEST_CHROMIUM` bleibt
  als explizite Browserauswahl nutzbar; Fehlstarts und parallele Fixtures haben
  eigene Aufräumprüfungen.

Quellbezug: `sp5generator/static/app.js`. Regressionen:
[`tests/review_ui_app.test.cjs`](../tests/review_ui_app.test.cjs) und
[`tests/browser/review-state.cjs`](../tests/browser/review-state.cjs).

## Kompatibilität und Aktualisierung

Die [Releasehinweise für 0.29.1](release-0.29.1.md) erläutern die strikteren
Eingabegrenzen, additive Diagnosemetadaten, die erweiterten CSV-/XLSX-Detailspalten
und die reversible Team-CSV-Textkodierung. `schema_version: "1.0"` bleibt erhalten;
es gibt weder stilles Kürzen von Kennungen noch eine automatische fachliche
Umdeutung gespeicherter Projekte. Bereits importierte Historie wird durch den
Patch nicht rückwirkend neu abgeleitet.

## Reproduzierbare Prüfungen

```sh
python -m pytest -q
python -m ruff check sp5generator tests tools
node --test tests/release_source.test.cjs
npm ci --prefix tests/browser
npm exec --prefix tests/browser -- playwright install --with-deps chromium
npm test --prefix tests/browser
python -m build
python tools/check_distribution.py
```

Der normale Browserbefehl führt auch die neuen Handler- und Browserregressionen
aus; derselbe Befehl ist bereits Bestandteil der Container-CI. Python-Regressionen
stehen in `tests/test_review_{core,data,data_followup,provenance_values,security,mapping_budget,contract}.py`.
Die Befehle beschreiben den Abnahmeumfang, nicht dessen bereits erfolgreichen
Abschluss. Vollständige Tests, Paketbau, saubere Installation, Datenschutzprüfung
und unabhängiger Schlussreview müssen für denselben Veröffentlichungsstand
abgeschlossen sein; einzelne bestandene Vertragschecks reichen dafür nicht.

Der große bestehende Browser-Warnlistentest verwendet jetzt den akzeptierten
Grenzwert von 1000 Einträgen statt einer übergroßen 1001-Einträge-Datei; Suche,
Scrollen, Duplikate und gezieltes Entfernen bleiben geprüft. Die Ablehnung
überlanger Listen wird separat durch HTTP-Sicherheitstests abgesichert.
Zwei ältere Ersatztests wurden auf gültige Ausgangspläne und den vollständigen
Validierungsvertrag angepasst, nicht durch Abschalten der Prüfung umgangen.

Grenzen der Abnahme: kein produktiver Personalbestand, keine tatsächliche
SP5-Installation, keine Rechtskonformitätszusage, kein Screenreader oder
physisches Mobilgerät und kein Excel-/LibreOffice-Lauf. Die Browsertests prüfen
native Tastatur-/Dateiauswahlereignisse, reale HTTP-Speicherung und tatsächlichen
Sitzungswiderruf in Chromium. Warmstart-Tests injizieren den zweiten
`UNKNOWN`-Status nach einem echten Zertifikat; dies ist keine Zeitmessung eines
Produktions-Timeouts.
