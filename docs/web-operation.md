# Eigenständiger Webbetrieb

## Browser und numerische Projektdaten

Die Oberfläche benötigt quelltextbewusstes natives JSON-Parsen, `BigInt`,
`JSON.rawJSON` und `structuredClone` mit Erhalt nativer Number-Objekte einschließlich
negativer Null. Diese Fähigkeiten werden gemeinsam geprüft. Fehlen sie, erscheint
eine begrenzte Fehlermeldung vor Projektwechsel oder Schreibanfrage; es gibt keinen
verlustbehafteten Fallback. Gemessen wurden Node 22.23.3 für Modultests und Chromium
145.0.7632.6 für Browserabläufe. Andere Browser und Versionen sind damit nicht als
geprüft ausgewiesen.

Große ganze Metadatenzahlen bleiben exakt, endliche Floats behalten ihren binären
Wert, Integer-/Float-Kategorie und das Vorzeichen von `-0.0`. Die Schreibweise darf
sich ändern; zusätzliche ursprüngliche Dezimalstellen sind keine beliebige
Dezimalpräzision. Ungültige oder nicht darstellbare Daten werden nicht bereinigt.
Bei Abweisung bleiben der aktuelle Entwurf, noch offene JSON-/Personenbearbeitung
und Datei-/Assistenteneingaben erhalten. Eine fehlgeschlagene Darstellung ist kein
Verbindungsfehler. Backend, native Exporte, Schemata und Größenlimits werden dadurch
nicht eingeschränkt oder angehoben. Formatierte Sicherungen und zusätzliche
Anfragefelder zählen weiterhin mit ihren tatsächlichen Bytes zur Eingabegrenze.

## Betriebsstatus

`GET /healthz` liefert ausschließlich `ok` oder `unavailable`. Ein fehlender
Berechnungsprozess oder nicht erreichbarer Zustandsspeicher erzeugt HTTP 503.
Das Container-Image verwendet diesen Endpunkt als Docker-Healthcheck. Docker
markiert einen fehlerhaften Container als `unhealthy`; die Restart-Policy allein
startet einen noch laufenden ungesunden Container nicht automatisch neu.

## Optionaler Zugriffsschutz

Für einen gemeinsam erreichbaren Generator `SP5_WEB_PASSWORD_FILE` auf eine
nur lokal lesbare Passwortdatei setzen. Die Datei schreibgeschützt einbinden
und für Container-UID 10001 lesbar bereitstellen. Kein Passwort in die
Compose-Datei oder in ein Repository schreiben.

Die Oberfläche zeigt dann eine Anmeldung. Die Sitzung wird in einem
HttpOnly-/SameSite-Cookie geführt und verfällt nach acht Stunden; beim Serverneustart verlieren
bestehende Sitzungen ihre Gültigkeit. Abmelden beendet die aktuelle Sitzung.
Der Passwortschutz ist ein gemeinsamer Zugang für eine einzelne lokale
Planungsinstanz, keine Benutzerverwaltung mit getrennten Mandanten.

Ohne diese Konfiguration bleibt der ausdrücklich gewählte lokale Testbetrieb
anmeldungsfrei. Der Zugriff auf die SP5-API wird davon getrennt über deren
konfigurierte Anmeldung beziehungsweise bestätigten Dev-Modus gesteuert.
Für Zugriffe außerhalb einer vertrauenswürdigen lokalen Umgebung HTTPS an
einem kontrollierten Reverse-Proxy verwenden. Der Generator ist nicht als
öffentlich erreichbarer Mehrbenutzerdienst konzipiert.

## Aktualisieren und zurückwechseln

Neben `latest` und dem Commit-Tag `sha-…` werden neue Images mit der
Produktversion veröffentlicht, beispielsweise `:0.8.0`. Da Versions-Tags bei
erneuten Builds derselben Version ersetzt werden können, für reproduzierbare
Installationen den getesteten Commit-Tag oder einen Image-Digest festhalten.
Vor Updates eines persistenten Betriebs das Zustandsvolume sichern. Beim
temporären Stack ist keine Wiederherstellung vorgesehen: Importe und Entwürfe
werden beim Neustart verworfen. Ein Imagewechsel kann diesen Verlust nicht
rückgängig machen.

Version 0.8.0 ergänzt Spalten in der SQLite-Datenbank. Ein Zurückwechseln auf
0.7.0 erfordert die Wiederherstellung der vollständigen Datenbanksicherung von
vor dem Update zusammen mit dem alten Image. Die alte Version kann die
migrierte Datenbank nicht unverändert weiterverwenden. Vor dem Zurückwechseln
neuere Entwürfe als Projektdatei sichern; sie fehlen in der älteren Sicherung.

Nach Update Versionsanzeige und Containerzustand prüfen, dann zunächst den
synthetischen Demoablauf berechnen und validieren. Alte SP5-Importe mit
arbeitsplatzbasierten Freigaben erneut importieren; keine automatische
fachliche Umdeutung durchführen.

## Fachlicher Freigabestand

Die Anwendung erzeugt und exportiert Vorschläge. Sie schreibt weiterhin nicht
in originale SP5-Dienstpläne zurück. Ungeklärte Sonderbedarfssemantik und
unvollständige Quellregeln bleiben sichtbar und verhindern eine unberechtigte
vollständige Validierung. Technisch bestandene Tests ersetzen die lokale
fachliche Bestätigung dieser Angaben nicht.

## Ausführungsgrenzen

HTTP-Schreibanfragen sind auf 16 MiB begrenzt, auch bei Übertragung in Blöcken.
Die fachliche Vorprüfung begrenzt Planung auf 366 Tage, Kontext auf 1096 Tage,
Personen auf 1000, Einteilungen auf 5000 und Kombinationen aus Personen und
Bedarfen auf zwei Millionen. Zusätzlich gelten Grenzen für verschachtelte
Datensätze und minutengenaue Wochenruhefenster. Überschreitungen ergeben eine
Eingabediagnose; sie werden nicht als bewiesene Unlösbarkeit ausgegeben.
Diese Grenzen garantieren keine feste Rechenzeit für beliebige Instanzen.

Kennungen sind unveränderte Referenzen und dürfen höchstens 200 Zeichen lang
sein. Überlange Kennungen werden ausdrücklich abgewiesen, niemals gekürzt oder
normalisiert. Personenbezogene Listen wie Freigaben und Verfügbarkeiten sowie
`unresolved` sind auf jeweils 1000 Einträge begrenzt. Die dokumentierten
JSON-Schemata enthalten die einzelnen Sammlungsgrenzen.

Vor der Pydantic-Modellvalidierung gilt zusätzlich ein **Parsebudget von 50.000
Einheiten** pro Snapshot bzw. gesamter Plananfrage (Prüfung, Freigabevorschau,
Ersatzsuche und alle Exporte). Es zählt eine Einheit für das Wurzelobjekt und
je eine für jeden Mapping-Eintrag (Schlüssel/Wert-Paar) und jeden Listenplatz;
Python-Tupel und bereits geparste Modellfelder werden entsprechend gezählt.
Skalare Werte, unbekannte Schlüssel und leere Container zählen ebenfalls.
Beim Abstieg wird ein Container nicht nochmals gezählt, seine Einträge aber
schon. Beispiel: `{"a": [null, {}, []]}` benötigt fünf Einheiten.
Snapshot, externe Einteilungen und alle weiteren Anfragefelder teilen dieses
Budget; mehrfach vorkommende Objekte werden pro Vorkommen gezählt.

Nur der **Inhalt des tatsächlichen `snapshot.metadata`** ist ausgenommen
(bei einem allein eingereichten Snapshot dessen eigenes `metadata`). Der
Metadateneintrag selbst zählt eine Einheit. Andere Felder namens `metadata`,
etwa in einer Person, Einteilung oder neben `snapshot`, sind nicht ausgenommen.
Die Vorprüfung bricht beim ersten Überschreiten mit einem einzelnen Schemafehler
(HTTP 422) ab, bevor Pydantic die einzelnen Eingabefehler erzeugt. Sie kopiert
oder serialisiert dazu weder das Eingabeobjekt noch vollständige Modelle.

Dies ist strenger als die frühere Zählung von 50.000 verschachtelten
**Datensätzen**: Auch die Felder eines gültigen Datensatzes verbrauchen nun
Parseeinheiten. Die Grenze garantiert daher **nicht** Platz für 50.000
vollständige Datensätze oder die gleichzeitige Ausschöpfung aller Listenlimits.
Exakt 50.000 rohe Einheiten passieren die Vorprüfung, versprechen aber noch
keine Annahme: **Nach Typnormalisierung und Einfügen aller Modellstandardwerte
gilt separat dieselbe Grenze von 50.000 Einheiten.** Beide Zählungen werden
nicht addiert; Metadatenausnahme und Zählweise bleiben gleich. Ein sparsames
Projekt kann deshalb vor jeder Erfolgsantwort mit HTTP 422 abgewiesen werden,
obwohl seine Rohdaten passen. Synthetisches Kapazitätsbeispiel: 1000 Personen
mit je vier Freigaben benötigen roh 30.049, normalisiert 55.090 Einheiten und
passen nicht; mit je zwei Freigaben sind es 20.049 bzw. 43.090 und sie passen.
Auch roh exakt 50.000 kann nach Standardwerten 50.063 ergeben und wird abgewiesen.

Snapshot und gesamte Plan-/Ersatzanfrage haben jeweils ihre eigene Wurzel.
Ein Snapshot mit 50.000 normalisierten Einheiten passt, aber seine Einbettung
in `{"snapshot": …, "assignments": []}` braucht bereits 50.002 Einheiten.
Interne Solver-/Validatorarbeit bekommt keinen fiktiven HTTP-Umschlag berechnet.
Bei späterem Zusammenführen eines Ergebnisses mit dem Projekt gelten die
Grenzen erneut. Eine zu große interne Reparaturvariante wird verworfen, ohne
einen bereits unabhängig gültigen Ergebnisplan zu verlieren.

Vor HTTP-Antworten mit Snapshots und dauerhaften JSON-Schreibvorgängen muss
das **vollständige kanonische kompakte UTF-8-JSON einschließlich Metadaten**
zusätzlich in die unveränderten **16 MiB** passen. Zu große normalisierte
Darstellungen werden vor Bestätigung/Speicherung mit HTTP 413 abgewiesen;
nicht verlustfrei darstellbare JSON-Werte mit begrenzter HTTP-422-Meldung.
Die Zusage betrifft die kompakte Snapshot-Wiedereingabe, nicht beliebige
Leerzeichen/Pretty-JSON oder größere Anfrageumschläge. Der HTTP-Body selbst
bleibt unabhängig davon auf 16 MiB begrenzt. Metadaten bleiben vom
Planungseinheitenbudget ausgenommen, nicht vom Bytebudget. Kennungen und
akzeptierte benutzerdefinierte JSON-Metadaten bleiben unverändert; es gibt
keine Kürzung, stille Bereinigung oder Speicherung nur explizit gesetzter Felder.

Modellidentität, frühere Validierung, Mutation und `model_copy` ersetzen keine
Endprüfung. Speichern, Kopieren und Archivieren/Wiederherstellen prüfen den
exakten endgültigen JSON-Inhalt vor Übersichten und SQL-Schreibvorgängen und
geben den dazu passenden validierten Wert zurück. Fehler lassen alte Payloads,
Revisionen, Übersichten, Archivzustand und Aufträge unverändert. Beim Einreihen
wird auch ein historischer Bestandsdatensatz innerhalb derselben Transaktion
geprüft; ungültige Altdaten werden weder still repariert noch in einen neuen
Auftrag übernommen. Native Import-/Historien- und Solver-/Validatorübergaben
prüfen Planungseinheiten ohne vorherigen vollständigen Dump/Deepcopy.
Die zusätzliche JSON-Prüfung gilt nur an Transport-/Speichergrenzen, nicht
pauschal im nativen Snapshot-Konstruktor: Die bestehenden optionalen
Provenienz-Fallbacks nativer CSV-/XLSX-Exporte bleiben davon unberührt.

Das Planungseinheitenbudget begrenzt nicht die vorgelagerte JSON-Dekodierung
und ist keine exakte Obergrenze für die Anzahl einzelner Schemafehler
unterhalb des Limits (ein fehlerhafter Eintrag kann mehrere Schemafehler
verursachen). Weitere Schema- und fachliche Grenzen gelten unabhängig davon.

`POST /api/readiness` und `POST /api/validate` liefern höchstens 100 Diagnosen
mit zusammen höchstens 48 KiB serialisiertem Diagnosetext. Zusätzlich enthalten
die Antworten `diagnostics_total`, `diagnostics_omitted` und
`diagnostics_by_code`. `ready`, `valid` und `complete` werden **vor** der
Anzeigeauswahl aus dem vollständigen Ergebnis bestimmt. Harte Fehler werden
vor Vakanz- und Kontexthinweisen angezeigt. Integrationen dürfen eine leere
oder gekürzte Diagnoseliste daher nicht als bestanden interpretieren.

Bei zu aufwendiger Diagnoseerzeugung wird die gesamte HTTP-Prüfung mit Status
422 und `code: "diagnostic_limit"` abgebrochen; ein abgebrochener Check ist kein
gültiger Plan. Das Arbeitsbudget beträgt 10.000 erzeugte Diagnosen bzw. eine
Million Zeichen in Diagnosewerten. Schemafehler nennen begrenzt Feldpfade und
Fehlertypen statt Eingabewerte; `fields_total` und `fields_omitted` zeigen eine
gekürzte Fehlerliste an. Diese Schutzmaßnahmen sind keine allgemeine
Byteobergrenze für vollständige Projekt- oder Exportdateien.

## Worker nach einem Prozessabsturz

Der vom Webdienst gestartete Worker ist an dessen Elternprozess gebunden.
Unter Linux beendet ein Parent-Death-Signal den Worker auch nach `SIGKILL` des
Webprozesses; sein Berechnungsprozess hat denselben Schutz. Beim erneuten Start
wird die Betriebssystem-Dateisperre neu erworben. Unter anderen POSIX-Systemen
wird der Elternprozess an den Worker-Prüfpunkten kontrolliert; dieser Ersatzweg
ist nicht als Linux-äquivalente Absturzgarantie getestet.

Eine noch gehaltene Lockdatei nicht löschen. Unterbrochene Aufträge werden beim
Neustart als fehlgeschlagen gekennzeichnet und müssen ausdrücklich neu
beauftragt werden. Ein separat über `sp5-generator worker --store …`
gestarteter CLI-Worker bleibt dagegen absichtlich unabhängig von seinem
aufrufenden Prozess.
