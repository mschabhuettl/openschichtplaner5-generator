# Architektur

`sp5generator.models` ist der versionierte JSON-Vertrag (1.0). Schemaausgabe und Beispiele verwenden dieselben Pydantic-Modelle wie CLI, Jobs und Adapter. IDs sind Referenzen, Namen nur Anzeige. Ein Snapshot enthält Zeitraum, Kontext, Zeitzone, Revision, Regelversion, Herkunft und bestätigte bzw. noch ungeklärte Eingaben. Sein kanonischer SHA-256-Hash bindet das Ergebnis an alle Eingabewerte.

## Schemata und Kompatibilität

`docs/input.schema.json` und `docs/result.schema.json` werden ausschließlich aus
den Laufzeitmodellen erzeugt (ohne manuelle Ergänzungen):

```sh
python -m sp5generator.cli schema input -o docs/input.schema.json
python -m sp5generator.cli schema result -o docs/result.schema.json
```

`tests/test_review_contract.py` vergleicht beide Dateien mit der CLI und den
Modellen. Dieser Test läuft mit den normalen Python-Tests in CI. Die gepinnten
Pydantic-Versionen aus `requirements-web.lock` bestimmen die Schemaausgabe.

`schema_version: "1.0"` bleibt für die vorhandene Dokumentstruktur erhalten:
später ergänzte Optionen sind weiterhin optional und haben explizite Defaults.
Ältere Projekte ohne persönliche Grenze, Planungsausschluss oder
Bedarfsalternativen behalten diese Defaults. Bestehende Dateiinhalte werden
weder migriert noch stillschweigend umgeschrieben. Integrationen sollen das
Schema des tatsächlich eingesetzten Paketstands verwenden; ein älteres Schema
mit `additionalProperties: false` kann neue optionale Felder nicht kennen.

Sicherheitsbedingte Eingabegrößenlimits können zuvor technisch parsebare,
übermäßig große Werte ausdrücklich zurückweisen. Kennungen werden dabei nie
gekürzt oder normalisiert. Vor einem Update solche Projekte exportieren und
mit dem neuen Eingabeschema prüfen; ein zurückgewiesener Bestand muss bewusst
bereinigt werden, nicht automatisch verändert. Änderungen der Bedeutung oder
Form erforderlicher Felder benötigen dagegen eine neue Schemaversion und eine
explizite Migrationsstrategie.

## Annahme, Normalisierung und Wiederverwendung

Größenprüfung ist ein Vertrag über den gesamten Datenweg, nicht nur über die
ursprüngliche HTTP-Anfrage. Das Planungsbudget wird getrennt vor der
Schemaexpansion und am vollständig normalisierten Modell geprüft. Beide Formen
müssen jeweils in 50.000 Einheiten passen; ihre Zählungen werden nicht addiert.
Eine knappe Eingabe ohne optionale Felder kann durch ergänzte Defaults die zweite
Grenze überschreiten und wird dann vor einer Erfolgsantwort zurückgewiesen.
Nur der Inhalt des tatsächlichen Snapshot-Metadatenfelds bleibt von diesem
Planungsbudget ausgenommen.

Ein Snapshot und eine vollständige Plan-/Ersatzanfrage sind verschiedene Wurzeln.
Ein Snapshot an seiner Grenze garantiert nicht, dass zusätzliche Einteilungen
oder andere Anfragefelder ebenfalls noch hineinpassen. Interne Solveraufrufe
erhalten dagegen keinen künstlichen HTTP-Umschlag.

Vor Ausgabe über HTTP oder dauerhafter JSON-Speicherung muss auch die kompakte
UTF-8-Darstellung des normalisierten Snapshots in das unveränderte Bodylimit von
16 MiB passen, einschließlich Metadaten. Diese Zusage betrifft die kompakte
Snapshot-Darstellung, nicht beliebige zusätzliche Leerzeichen oder größere
Anfrageumschläge. Das Bytebudget ersetzt weder die Vorprüfung noch die Prüfung
des normalisierten Planungsmodells. Reine In-Memory-Tabellenexporte behalten ihren
eigenen Vertrag für unbrauchbare optionale Beschriftungen.

Frühere Validierung, Modellidentität und `model_copy` sind keine dauerhaften
Freigaben: Importergänzungen, Historienfreigaben und andere Mutationen können
die Größe verändern. Deshalb werden endgültige Übergaben erneut geprüft. Eine
abgewiesene Speicherung darf weder Nutzdaten noch Revision, Zusammenfassung
oder bestehende Zustände verändern. Ein unlesbarer gespeicherter Snapshot darf
keinen neuen Job erzeugen. Bestehende ungültige Daten werden nicht stillschweigend
umgeschrieben; `exclude_unset` ist kein Ersatz für diesen Vertrag, da nachträglich
an eine ursprünglich ausgelassene Liste angehängte Freigaben sonst verloren gehen
könnten. Grenzwerte und Fehlerbehandlung beschreibt der [Webbetrieb](web-operation.md).

## Zahlentreuer Browsertransport

`static/project-json.js` ist die gemeinsame Grenze für vollständiges Projekt-JSON,
Antworten, Eingabebindungen, technische Berichte und JSON-Sicherungen. Der native
Parser liest `context.source`: sichere ganzzahlige Tokens werden `Number`, größere
Integer werden direkt aus dem Quelltoken `BigInt` (auch oberhalb des endlichen
Number-Bereichs). Endliche nichtganzzahlige Floats bleiben primitive Numbers;
integralwertige Float-Tokens tragen ihren Typ in echten nativen Number-Objekten.
So bleiben Python-Integerwerte, Float-Kategorie, binärer Floatwert und das Vorzeichen
von `-0.0` erhalten. Ursprüngliche Dezimalschreibweise und Formatierung sind kein
Vertrag. Insbesondere darf `60.0` nicht vor strenger Backendvalidierung zu `60` werden.

Der Encoder erzeugt einen kurzlebigen, geprüften Wire-Baum mit `JSON.rawJSON` für
numerische Tokens. Diese Wrapper gehören niemals in Anwendungszustand oder Klone.
Metadaten mit Schlüsseln wie `rawJSON`, `$number` oder `__proto__` sind gewöhnliche
Daten. Keine Quellkopie, Pfad-Sidecar, globale Prototypänderung oder Parserabhängigkeit
wird verwendet. Aktuelle Änderungen, Löschungen und Arrayumordnungen bestimmen die
Ausgabe. Zyklen, nichtendliche Werte, unsicher große primitive Ganzzahl-Numbers ohne
bekannten Typ, Getter, Klasseninstanzen und andere nicht unterstützte JS-Werte werden
vor Transport zurückgewiesen, nicht still ausgelassen oder durch `null` ersetzt.
Mehrfache azyklische Referenzen bleiben erlaubt.

`ProjectJSON.clone` prüft vor dem nativen `structuredClone`; übrige geprüfte
feldspezifische Klone bleiben nativ. `ProjectJSON.number` ist ausschließlich eine
lesende native Number-Brand-Sicht, keine String-/BigInt-Konvertierung. Verbraucher
mit `typeof`, Wahrheitswertprüfung, strikter Gleichheit oder Number-Prädikaten müssen
diese Repräsentation ausdrücklich berücksichtigen. Die strenge Prüfung ganzzahliger
Diagnosesummen bleibt unverändert. Neue Vollprojekt-JSON-Grenzen dürfen weder
`response.json()` noch natives `JSON.stringify` verwenden; reine Identifier-/CSV-
Feldkonversionen bleiben davon getrennt.

Laden prüft und klont vor dem Zurücksetzen des bisherigen Projekts. Serialisierung
liegt vor dem Netzwerk-Catch. Speichern und asynchrone Ergebnisse sind an die
konkrete Eingabe gebunden; neuere Text-, Personen- oder Projektänderungen dürfen
nicht als gespeichert bestätigt oder durch eine alte Antwort ersetzt werden.
Die bestehenden Backendbudgets und Metadatenausnahme bleiben unverändert; eine
Antwort mit Snapshot-Umschlag erhält kein künstliches Snapshot-Bytebudget.

## Komponenten

- **openschichtplaner5-generator:** allgemeine Modelle, zeitliche Domänenfunktionen, CP-SAT-Optimierung, unabhängige arithmetische Prüfung, Export, optionale Jobverwaltung und lesender Adapter. Der reine Solver erhält nur einen Snapshot und Parameter.
- **libopenschichtplaner5:** native Tabellenformate, Datenzugriff und bestehende Sollstundenberechnung. Der Adapter importiert diese Library erst bei Verwendung; der Kern benötigt sie nicht.
- **openschichtplaner5-api:** Anmeldung, Rechte, Sichtbarkeit, HTTP-Endpunkte, persistente Vorschläge und ausdrückliche Übernahmeaktion. Generatorinstallation und Aktivierung sind optional.
- **openschichtplaner5:** integrierte Generatoransicht mit bestehenden Navigationselementen und authentifiziertem HTTP-Client.

Der HTTP-Prozess führt keine langen Solverläufe aus. Er schreibt Jobs in einen privaten SQLite-Store. Ein separat gestarteter Worker mit exklusiver Betriebssystem-Dateisperre führt jeweils einen Berechnungs-Unterprozess aus. Sessionzustände werden nicht an diesen Prozess übertragen. Die Identität ist beim Enqueue bereits geprüft; Übernahme erfordert eine neue Rechteprüfung.

Der Validator erzeugt sein Urteil aus Snapshot und Einteilungen neu, ohne Variablenwerte oder Status des Solvers zu übernehmen. Reine Zeit-/Eignungsfunktionen werden geteilt. Komplexe Ruheprüfungen können ungültige Kandidaten während der Optimierung ausschließen; nur unabhängig geprüfte Kandidaten werden als Lösung ausgegeben.

Bei einer Teilplanung können bereits gespeicherte, nicht fixierte Einteilungen
als Ausgangslösung dienen. Dafür rekonstruiert der Solver die aktuellen
Dienstintervalle, prüft den Vorschlag unabhängig und lässt alle
Einteilungsvariablen in einem separaten CP-SAT-Zertifikatslauf auf diesen
Vorschlag setzen. Nur ein erfolgreich zertifizierter Vorschlag wird zum
Rückfallplan bei späterem Zeitablauf. Das fixiert die Einteilungen nicht in der
anschließenden Suche: Sie darf weiterhin verschieben und offene Besetzungen
reduzieren. Die Zahl offener Besetzungen darf gegenüber dem zertifizierten
Ausgangsplan nicht steigen. Ein Zertifikat mit festgehaltenen Variablen beweist
keine optimale Abdeckung; ein Rückfall bleibt `FEASIBLE`, nicht `OPTIMAL`.
Ohne erfolgreiche Prüfung entsteht dadurch kein ausgebbarer Plan. Reiner
Fix-/Randkontext aktiviert diesen Vorschlagsmechanismus nicht.

Die Unterbesetzungsvariable je Bedarf ist exakt
`max(0, Mindestbesetzung - ausgewählte Einteilungen)`. Eine reine Untergrenze
reicht nicht: Bei einem zeitbegrenzten `FEASIBLE`-Ergebnis könnte die
Hilfsvariable sonst größer als die wirkliche Unterbesetzung bleiben und damit
Zielfunktionswert und Ergebniszählung auseinanderlaufen. Überbesetzung innerhalb
eines konfigurierten Maximums ergibt weiterhin null offene Stellen, keine
negative Unterbesetzung.

Native SP5-Gesamtübernahme ist nicht implementiert: Die existierenden Writer teilen keine durchgehende Transaktion mit zusätzlich dateibasierten Regeln. Das Experiment ersetzt diese Grenze nicht durch einzelne Tabellenlocks oder einen frühen Versionsvergleich.
