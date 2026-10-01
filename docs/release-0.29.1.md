# Version 0.29.1 – Korrekturen an Prüfung, Daten und Bedienung

Diese Hinweise beschreiben die Änderungen gegenüber 0.29.0 und den zugehörigen
Prüfvertrag. Den tatsächlichen Veröffentlichungsstand belegen das GitHub-Release
und die erfolgreichen CI-Läufe für dessen exakten Commit, nicht dieses Dokument.

0.29.1 ist ein Patch für Korrektheit, Sicherheit und bestehende UI-Abläufe.
Der Schnellstart und die bisherigen Arbeitsbereiche bleiben erhalten; ein
umfassender UX-Neuentwurf ist nicht Teil dieses Stands. Die Zuordnung zu den
Originalbefunden und den zusätzlichen Randfällen steht in
[Reviewkorrekturen](review-fixes.md).

## Planung und unabhängige Prüfung

- Persönliche harte Minutengrenzen gelten auch bei der unabhängigen Prüfung
  manuell bearbeiteter oder extern eingereichter Einteilungen. Maßgeblich sind
  bezahlte Arbeitsminuten einschließlich persönlicher Periodenarbeit, nicht
  ein durch Guthaben oder Anfangssaldo verrechneter Wert.
- Nachtblock-Nachbarn werden nach tatsächlichem UTC-Anfang geprüft, unabhängig
  von der Reihenfolge der Einteilungen und mehrdeutigen lokalen Uhrzeiten bei
  der Zeitumstellung. Persönliche Arbeit ohne Uhrzeiten behält ihren Tag und
  ihre Minuten, erhält aber kein erfundenes Intervall.
- Leere `alternative_group`-Kennungen bedeuten unabhängige Bedarfe. Nichtleere
  gemeinsame Alternativen zählen in Solver, Validator, zertifizierten
  Warmstart-Rückfallplänen und Belegungsanzeigen übereinstimmend. Offene
  Mindeststellen werden nicht als vollständiger Plan ausgegeben.
- Auch späte Teile ausgewählter mehrteiliger Dienste aktivieren die betroffenen
  Arbeitstagsserien und Kontextprüfungen. Ungewählte Kandidaten aktivieren
  diese zusätzlichen Prüfbereiche nicht.

## Arbeitsminuten, Import, Export und Ersatzsuche

- Bezahlte Periodenarbeit richtet sich nach dem lokalen Anfangstag des Dienstes
  beziehungsweise `day` bei Arbeit ohne Uhrzeiten. Das Importkennzeichen
  `in_period` allein verschiebt keine Minuten in den Planungszeitraum.
  Solverkennzahlen, erreichbare Ziele, Sollerfüllung, Startplanlast und
  zertifizierte Rückfallpläne verwenden diese Rechnung ebenso wie die Exporte.
  Die Bestätigung zeitbehafteter persönlicher Periodenarbeit bleibt erforderlich.
- CSV und XLSX enthalten persönliche Arbeit in den Details; XLSX berücksichtigt
  sie auch im Kalender und in der Stundenübersicht. Zeitlose Arbeit ist
  ausdrücklich erkennbar; Randdienste
  erhalten keine zweite Periodengutschrift, nur weil ihr Ende in die Periode
  hineinragt. Unbrauchbare optionale Provenienz verliert keine Arbeit und
  verändert keine Kennungen. Namen und Funktionsbeschriftungen übernehmen nur
  unveränderte, nichtleere, tabellengeeignete Zeichenketten; optionale
  Arbeitsplatzbeschriftungen zusätzlich ganze Zahlen im verlustfrei darstellbaren
  15-stelligen Bereich. Container, Booleans, Fließkommazahlen, unzulässige
  Steuerzeichen und zu lange Texte verwenden sichere Ersatzbeschriftungen.
  Zusammengesetzte Kalenderzellen und der Formelschutz zählen beim Textlimit mit.
  Diese Prüfung betrifft optionale Anzeigewerte, nicht die tatsächlichen Arbeit-IDs.
- CSV-Dateien ersetzen das Ziel erst nach vollständiger Erzeugung und Schließen
  einer temporären Datei im selben Verzeichnis. Fehler beim Erzeugen, Kodieren
  oder Ersetzen beschädigen den bisherigen Export nicht und hinterlassen keine
  teilweise neue Zieldatei. Dies ist keine allgemeine Atomaritätszusage für XLSX.
- Der SP5-Import entfernt ersetzte Ist-Tageszeilen vor der Ableitung historischer
  Freigabevorschläge und Bedarfe. Getrennte Soll-Daten bleiben erhalten; die
  Herkunft bleibt bei gemischter Auswertung unterscheidbar. Historie ersetzt
  weiterhin keinen Qualifikationsnachweis und keine erforderliche Bestätigung.
- Ersatzempfehlungen prüfen den hypothetischen Gesamtplan einschließlich
  kumulierter Grenzen. Die Übernahme einer ganzen Abwesenheit wird gemeinsam
  geprüft, unabhängig von den Einzelkandidatenlisten: Eine erst gemeinsam
  zulässige Nachtblockfolge bleibt so auffindbar. Zeitlose persönliche Arbeit
  verursacht keinen Absturz und behält ihre Tagessperre. Die Suche selbst
  verändert keine Einteilung.

## Oberfläche und Freigaben

- Speichern, Importieren und Berechnen sind an die konkrete Projektinstanz und
  Änderungsversion gebunden. Überlappende Datei-/Speicheraktionen verlieren
  weder ihre laufende Sperre noch hinterlassen sie eine dauerhafte Sperre.
  Veraltete Ersatz- und Freigabeanalysen werden nicht im neuen Stand angezeigt.
- Benutzerdefinierte JSON-Zusatzdaten behalten beim Öffnen, Prüfen, Speichern
  und Sichern ihre großen Ganzzahlen, endlichen Fließkommawerte, Zahlentypen und
  das Vorzeichen einer Fließkomma-Null. Die gemeinsame Browserkodierung wandelt
  sie weder in Zeichenketten um noch setzt sie nach Bearbeitungen auf alte Werte
  zurück. Die ursprüngliche Schreibweise einer Dezimalzahl ist kein eigener
  Datenvertrag; maßgeblich sind die Zahlenwerte und Typen des Python-JSON-Modells.
- Nicht darstellbare lokale Eingaben werden vor Projektwechsel oder Übermittlung
  abgewiesen und erhalten den bisherigen Entwurf und die Eingabefelder. Späte
  Antworten bestätigen keinen inzwischen geänderten Entwurf als gespeichert.
  Ein Browserfehler nach einer bereits erfolgreichen Servertransaktion kann
  deren Bestätigung verhindern, aber diese Speicherung nicht rückgängig machen.
- Einstellungsübernahme erhält Planungsausschlüsse und persönliche Grenzen,
  einschließlich null Minuten. Bei geändertem Zeitraum bleibt eine bestehende
  Grenze konservativ erhalten und wird zur ausdrücklichen Überprüfung vorgelegt.
- Familienfreigaben erhalten die Begleitpflicht, auch bei historischen
  Vorschlägen, ausgeschalteter Matrixgruppierung und einer aktiven
  arbeitsplatzübergreifenden Freigabe (`*`). Ein konkreter Arbeitsplatz umgeht
  diese Pflicht nicht; Entfernen erweitert den Entzug nicht auf andere Bereiche.
- Familiensuche findet auch einzelne Zeitlagen und Kennungen. Das Entfernen
  einer Person bereinigt ihre persönliche Arbeit und zugehörige Verweise.
  Browser-CSV-Exporte schützen Text vor Formelinterpretation. Dateiimporte
  bleiben nativ per Tastatur erreichbar; Abmelden bleibt in schmalen Ansichten
  sichtbar und widerruft weiterhin die tatsächliche Sitzung.
- Gekürzte Diagnoseanzeigen nennen Gesamtzahl, angezeigte und ausgelassene
  Meldungen. Eine leere Anzeige wird nicht als bestanden ausgelegt, wenn der
  vollständige Bericht Fehler enthält; widersprüchliche Bereitschaftszahlen
  geben die Planung nicht frei.

## Sicherheit und Betrieb

Der vom Webdienst gestartete Worker bleibt an seinen Elternprozess gebunden.
Unter Linux endet auch sein Berechnungsprozess nach abruptem Elternende, sodass
ein Neustart dieselbe Zustandssperre wieder erwerben kann. Der separat gestartete
CLI-Worker bleibt unabhängig. Unterbrochene Aufträge werden nicht automatisch
fortgesetzt. Grenzen des anderen POSIX-Ersatzwegs und Hinweise zu Lockdateien
stehen im [Webbetrieb](web-operation.md).

Parsebudgets greifen vor der Expansion verschachtelter Schemafehler, auch für
neben dem Snapshot übermittelte Einteilungen in Validierung, Ersatzsuche und
Export. Mapping-Einträge, unbekannte Felder, Listenplätze und leere Container
zählen mit; die Vorprüfung begrenzt die Arbeit vor der Fehlererzeugung, nicht
nur die Antwortgröße. Diagnoseerzeugung
und angezeigte Diagnosen haben getrennte Budgets; ein Erzeugungsabbruch ist
kein gültiger Teilbericht. Schemafehler geben begrenzte Feldpfade und Fehlertypen
statt der vollständigen Eingabewerte zurück, auch bei Importfehlern.

## Kompatibilität und Aktualisierung

- **JSON-Struktur:** `schema_version: "1.0"` bleibt bestehen. Optionale Felder
  behalten ihre Defaults; vorhandene Projekte werden weder migriert noch
  stillschweigend fachlich umgedeutet. Die eingecheckten Eingabe- und
  Ergebnisschemata entsprechen den Laufzeitmodellen. Integrationen müssen das
  Schema des eingesetzten Paketstands verwenden, nicht ein älteres Schema mit
  `additionalProperties: false`. Details: [Architektur](architecture.md).
- **Striktere Eingaben:** Kennungen sind auf 200 Zeichen begrenzt; unter anderem
  Freigaben, Verfügbarkeiten und `unresolved` auf jeweils 1000 Einträge. Das
  gemeinsame Parsebudget beträgt 50.000 Einheiten: eine für die Wurzel, danach
  eine je Mapping-Eintrag oder Listen-/Tupelplatz, auch für skalare Werte und
  unbekannte Felder. Container zählen beim Abstieg nicht nochmals. Damit
  verbrauchen auch Felder gültiger Datensätze Einheiten; dies garantiert nicht
  Platz für 50.000 vollständige Datensätze. Nur der Inhalt des tatsächlichen
  `snapshot.metadata` ist ausgenommen, sein Eintrag zählt mit. Das unveränderte
  HTTP-Bodylimit von 16 MiB gilt einschließlich dieser Metadaten. Das
  Planungsbudget wird getrennt an der ursprünglichen Eingabe und am vollständig
  normalisierten Modell geprüft. Beide müssen jeweils hineinpassen; durch
  Defaults übergroß gewordene Projekte werden vor einer Erfolgsantwort oder
  Speicherung abgewiesen. Auch die kompakte UTF-8-JSON-Darstellung eines über
  HTTP ausgegebenen oder dauerhaft gespeicherten Snapshots muss in die 16 MiB
  passen, damit sie wieder eingelesen werden kann. Dies garantiert keinen Platz
  für zusätzliche Felder eines größeren Anfrageumschlags. Abgewiesene Änderungen
  erhalten den bisherigen gespeicherten Zustand; unlesbare Bestände werden
  weder stillschweigend repariert noch als neuer Job angenommen. Zuvor parsebare,
  übergroße Projekte können deshalb ausdrücklich abgewiesen werden. Kennungen
  werden niemals gekürzt oder normalisiert; die einzelnen Sammlungsgrenzen
  stehen im [Eingabeschema](input.schema.json).
- **Additive HTTP-Metadaten:** Bereitschaftsprüfung und Validierung liefern
  zusätzlich `diagnostics_total`, `diagnostics_omitted` und
  `diagnostics_by_code`. Die Anzeigeliste enthält höchstens 100 Datensätze und
  48 KiB serialisierte Diagnosen. Zu große Einzelmeldungen werden ausgelassen,
  spätere passende Meldungen aber weiter berücksichtigt. `ready`, `valid` und
  `complete` stammen aus dem vollständigen Ergebnis; weder Länge noch Inhalt
  der Stichprobe ersetzen diese Flags. Schemafehler ergänzen `fields_total`
  und `fields_omitted`; Abbrüche der Diagnoseerzeugung liefern HTTP 422 mit
  `code: "diagnostic_limit"`.
- **Tabellenexport:** CSV und das XLSX-Detailblatt verwenden die Spalte
  `Bedarf / Arbeit-ID` statt `Bedarf` und ergänzen `Arbeitsart` und `Datum`.
  Zeitlose Arbeit hat leere Beginn-/Endefelder. Verbraucher mit festen
  Spaltenpositionen oder der Annahme „jede Zeile ist eine Bedarfseinteilung“
  müssen diese zusätzlichen Arbeitszeilen berücksichtigen.
- **Team-CSV:** Neue Dateien enthalten die zusätzliche Spalte `text_encoding`
  mit `apostrophe-v1` für reversible Textabsicherung. Alte sechs-spaltige
  Dateien werden weiterhin wörtlich gelesen, ohne unmarkierte Apostrophe oder
  Leerzeichen aus Kennungen zu entfernen. Beim Bearbeiten im Tabellenprogramm
  Textspalten als Text behandeln, die Kodierungsspalte erhalten und vor der
  Übernahme die Importvorschau prüfen.

Vor einem Update Projektdateien und persistenten Zustand sichern. Überlange
Kennungen oder Datensammlungen müssen bewusst bereinigt werden, nicht durch
stilles Abschneiden. Bereits importierte Historie wird nicht rückwirkend neu
abgeleitet; betroffene Quellen bei Bedarf neu importieren und Freigaben sowie
Bedarf fachlich prüfen. Bestehende Pläne erneut validieren und Exporte neu
erzeugen, bevor korrigierte Stundenwerte weiterverwendet werden. Direkte
Schreibzugriffe auf originale SP5-Dienstpläne sind weiterhin nicht implementiert.

## Prüf- und Veröffentlichungsstand

`tests/test_review_contract.py` prüft Paket-/Laufzeitversion, README-Wheelbeispiel,
Releaseverweis sowie die Gleichheit von CLI-, Laufzeit- und Dateischemata.
Die fachlichen und Browserregressionen sind unter
[Reviewkorrekturen](review-fixes.md) zugeordnet.

Eine Veröffentlichung setzt vollständige Python-, Node- und Browserprüfungen,
Paketbau und saubere Installation, Datenschutzprüfung sowie den unabhängigen
Schlussreview desselben Stands voraus. Erfolgreiche einzelne Vertragschecks
belegen diese Gesamtfreigabe nicht. Ein Release ist erst mit überprüftem Tag,
exaktem CI-Commit und zurückgelesenen Paket-/Containerartefakten abgeschlossen.

Prüfdaten sind synthetisch. Es wird weder ein produktiver SP5-Bestand noch
Rechtskonformität, Screenreader-/Mobilgeräteabnahme oder die Ausführung in
Excel/LibreOffice behauptet. Zertifizierte Warmstart-Rückfalltests mit injiziertem
`UNKNOWN` prüfen einen Programmzweig, keine gemessenen Produktions-Timeouts.
