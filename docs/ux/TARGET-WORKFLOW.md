> Historisches UX-01-Dokument, unverändert aus der abgenommenen Ausgangsmessung.
> Die genannten Logs, Bilder und absoluten Runnerpfade gehören zum getrennten
> lokalen Abnahmearchiv und sind nicht Bestandteil dieser Distribution.
> Für den umgesetzten Umfang siehe [Version 0.32.0](../release-0.32.0.md).

# UX-01 — Zielablauf und kleines Designsystem

Entwurfsentscheidung auf der gemessenen Basis `165c3a003acc1a11ede023e43f75dff28489fc3a`; Nachweise in `BASELINE.md` und `verification.json`. **Noch keine Implementierung, keine gemessene Verbesserung.** Alle folgenden Werte sind Abnahmekriterien/Hypothesen für nachfolgende Slices, keine bereits erzielten Ergebnisse.

## 1. Produktentscheidung: Der Dienstplan ist der Arbeitsbereich

Keine kosmetische Neufärbung der sechs bestehenden Hauptbereiche. Die spätere Navigation besteht aus:

- **Projekte**: zuletzt bearbeitete Projekte, „Neu“, „Importieren“, ausdrücklich getrennte Projektdatei-Wiederaufnahme. Berechnungshistorie ist sekundär, nicht ein zweiter gleichgewichtiger Projekteinstieg.
- **Plan**: Zeitraum, Kalender, Eingabe-/Ergebnisstatus, „Berechnen“, „Prüfen“, „Exportieren“. Bisheriges Planen und Dienstplan werden zu einem Arbeitsablauf zusammengeführt. Rechenfortschritt bleibt dort; der Kontext springt nicht zwischen zwei Seiten.
- **Team**: zuerst Personen mit Planen/Soll/Bearbeiten; zweite lokale Ansicht „Freigaben“. Gruppenaktionen, Mentoring, CSV und Herkunft aufklappbar, ohne ihre Regeln oder Daten zu ändern.
- **Einrichtung**: lokale Unterbereiche „Dienste & Bedarf“, „Regeln“, „Daten & Herkunft“. Gewöhnlicher Bedarf gehört zu den Diensten und ist keine konkurrierende Einzelbedarfs-Hauptnavigation. Vollständiger JSON-Vertrag bleibt als ausdrücklich erweiterte Funktion erhalten.

Desktop: kompakte dauerhafte Navigation; schmal: vier lesbare, in die Breite passende Einträge, keine unbeschrifteten Icons und kein nur durch horizontales Hauptnavigationsscrollen erreichbarer Plan. Tabellen behalten eigene beschriftete Scrollregionen und feste Personen-/Datumsbezüge.

Projektname, tatsächlicher inklusiver Zeitraum und Zeitzone stehen beständig im Kopf. Lange Namen umbrechen oder erhalten eine explizite Vollanzeige, statt die einzige sichtbare Projektidentität kommentarlos abzuschneiden. „Projekt gespeichert“ und „Entwurf gespeichert“ dürfen keine unterschiedlichen unerklärten Speicherorte suggerieren: eine gemeinsame Projekt-Speicheraktion verwendet die bestehenden sicheren Handler.

## 2. Ablauf je Einstieg

### Bestehenden Plan fortsetzen

Projektkarte → Plan, wenn gespeicherte Einteilungen vorhanden sind. Anzeige zunächst „Gespeicherter Entwurf · Prüfung noch nicht aktuell“, bis die für den aktuellen Stand gültige Prüfung vorliegt. Karte ohne Entwurf → Plan mit einer kompakten Einrichtungsliste und dem konkreten nächsten offenen Schritt. Die Liste verweist direkt auf Team/Bedarf/Regeln, keine neue verpflichtende Tour.

Der frühere Job und der aktuelle manuell bearbeitete Entwurf bleiben unterscheidbar. „Berechnung öffnen“ darf keinen neueren Entwurf ohne bestehende Dirty-/Versionsprüfung verdrängen. Reopen, Backup und Jobwiederaufnahme bleiben getrennte fachliche Operationen.

### Neues Projekt

Name und Monat/Zeitraum → Personen und Sollmodell → Dienste mit wiederholten Tagen → Regeln bewusst prüfen. Die aktuelle Drei-Schritt-Struktur darf dafür geändert werden: eine zusätzliche klare Entscheidung ist besser als 27 gleichzeitige Controls im letzten Schritt. Kein Zwang, Freigaben oder Randkontext beim Einstieg als bestätigt zu setzen. Auch ein unvollständiger Entwurf ist sichtbar speicherbar, nicht angeblich fertig.

Gängige Felder zuerst, seltene Grenzen in „Weitere Regeln“. Die Zusammenfassung zeigt Annahmen mit ihrem Bestätigungsstand. Bestehende Wochen-/Periodenstundenformeln nicht umdeuten oder im Hintergrund neu berechnen. Veränderung bestätigungsrelevanter Angaben setzt die bestehenden Bestätigungen korrekt zurück.

### SP5/Datei importieren

Vor Beginn den Weg wählen: **SP5 importieren** oder **Projektdatei öffnen**. Beim SP5-Weg bilden Quelle → Teams → Zeitraum einen zusammenhängenden Bereich. Monatsauswahl kann Datumsfelder vorbelegen, ohne Import oder fachliche Freigaben heimlich auszulösen. Vergleichsplan (Ist/Soll), Bedarfherkunft und Historienübernahme bleiben nachvollziehbar; historische Freigaben sind ausdrücklich opt-in.

Nach Import kompakter Bericht: ausgewählte Teams/Personen, Zeitraum, Datenherkunft, noch offene Entscheidungen. Primär „Offene Angaben prüfen“, sonst „Zum Plan“. Nicht mit einer langen Standardseite beginnen, die Null-Vergleichsdienste und sämtliche Sonderfälle gleich stark gewichtet.

### Plan erzeugen, prüfen, korrigieren

Oben Kalender und ein kurzer Statusbereich. „Berechnen“ startet die bestehende save-and-solve-Operation; bei offenen Angaben führt die primäre Aktion zum ersten konkreten Problem. Nicht allein anhand von Hinweisanzahl oder sichtbarer Auswahl entscheiden, ob gerechnet werden darf; die echten Serverregeln bleiben maßgeblich. Wenn eine Eingabeprüfung nicht vollständig vorliegt, offen „noch nicht geprüft“/„Prüfung fehlgeschlagen“ anzeigen.

Diagnosebereich zeigt Kategorie, fachliche Ursache, betroffene Person/Dienst und **eine** konkrete Korrekturaktion. Personenname/Dienstzeit zuerst, genaue ID bei Bedarf weiterhin kopierbar. Detailnavigation merkt Problemfilter und Rückkehrziel. Wo risikoarm möglich, kurze lokale Bearbeitung statt Seitenwechsel; vollständiger Profileditor bleibt erreichbar. Eine gezielte Korrektur bestätigt keine benachbarten Hinweise.

Kalenderauswahl → kontextnaher Einteilungseditor mit Person, Datum, Dienst, Fixierung und Prüfstatus; Schließen/Escape stellt Fokus auf die auslösende Kalenderzelle zurück. Kein unkontrolliertes Springen zu einer zweiten weit entfernten Kompletttabelle. Ersatzsuche bleibt eine Vorschlagsprüfung, bis eine ausdrücklich gewählte Änderung übernommen und erneut validiert wird.

Nach erfolgreicher Berechnung kurze Statuszeile, Kalender sichtbar. Suchspur, Zielerreichung, Freizeitstatistik und technische Auswertung sekundär aufklappbar. Export am Plan sichtbar; ungültige Entwürfe weiterhin serverseitig ablehnen, nachvollziehbaren Grund anzeigen. Projekt-JSON-Backup ist nicht mit Prüfergebnis-JSON zu verwechseln.

## 3. Zustandsmodell für sichtbare Aktionen

Eine zentrale Ableitung aus bestehendem Projekt-/Job-/Dirty-/Versionszustand; kein zweiter Schattenzustand, der Sperren zurücksetzt.

- **Kein Projekt**: nur Erstellen/Import/Öffnen; keine falschen Null-Belegungsmetriken.
- **Unbestätigte Eingaben**: „Einrichtung prüfen“; notwendige fachliche Zustimmung bleibt manuell.
- **Dirty**: „Ungespeicherte Änderungen“, Speichern erreichbar, Wechsel verwendet vorhandene Schutzdialoge.
- **Speichern/Datei lesen/Import pending**: konkrete laufende Aktion nennen; alle mutierenden Wege über bestehende zentrale Sperre. Unabhängig überlappende Aktionen erhalten ihre eigenen Sperrursachen bis beide abgeschlossen sind.
- **Berechnung läuft**: Verlauf und Abbrechen im Planbereich; gespeicherter Eingabestand/Job-ID bleiben gebunden. Kein neuer unbestätigter Entwurf als aktuelles Ergebnis.
- **Berechnung ohne brauchbares Ergebnis**: vorhandene Einteilungen erhalten; UNKNOWN/INFEASIBLE/MODEL_INVALID und Prozessende nicht als vollständigen Plan ausgeben.
- **Gültiger vollständiger Entwurf**: „Vollständig geprüft“, Speicherstand getrennt.
- **Gültiger Teilplan**: offene Plätze ausdrücklich, keine vollständige Belegungsbehauptung.
- **Ungültiger/geänderter Entwurf**: „Erneut prüfen“, Fehler-/Auslassungszahlen aus vollständigen Reportflags, Export bleibt geschützt.
- **Serverfehler vor Speicherung**: lokale Eingaben behalten, Wiederholen; nicht als gespeichert quittieren.
- **Quittierungsfehler nach erfolgreicher Speicherung**: nicht behaupten, der Server habe nichts geändert; bestehendes Follow-up `UI-POSTCOMMIT-RECOVERY-MESSAGE` beachten.

## 4. Kleines lokales Designsystem

Orientierung: funktionale Dichte und semantische Tokens aus dem geladenen IBM/Carbon-Referenzmaterial, **keine IBM-Kopie**, kein zusätzliches Framework, keine extern geladenen Fonts/Icons, kein CDN oder Tunnel. Die lokale Nutzung und bestehende Markenfarbe bleiben Ausgangspunkt. Tokens sind eigene Entwurfswerte; Kontrast und Fokus werden vor Abnahme im tatsächlich gerenderten Produkt gemessen, nicht hier als standardkonform behauptet.

```css
:root {
  --page: #f5f7f8;
  --surface: #ffffff;
  --text: #1f2933;
  --text-muted: #53616e;
  --border: #b5bec5;
  --accent: #9a3f23;
  --accent-hover: #7b311b;
  --focus: #005fcc;
  --success: #21633e;
  --warning: #8a4b00;
  --danger: #a32020;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --radius: 6px;
}
```

- Schrift: `system-ui, -apple-system, "Segoe UI", sans-serif`; 16 px Grundtext, 14 px kompakte Tabellen-/Metainformation, 20/24 px Überschriften. Ziffern tabellarisch. Keine Versalienketten für wichtige Anweisungen.
- Ein Hauptbutton pro Aufgabe; sekundäre Umnavigation ruhiger. Ein alleiniger Speicherzustand im Projektkopf, keine optisch konkurrierenden Speicheraufforderungen ohne Kontext.
- Normale Inputs/Buttons mindestens 44 px Höhe; kompakte Datentabellen nur mit nachgewiesener Tastatur- und Touchbedienbarkeit. Fokus sichtbar 2 px mit Abstand; nicht nur Farbe oder Hover.
- Formulare: Label oberhalb, Einheit direkt am Feld, fachlicher Zusatz erklärbar aufklappen. Fehler neben dem Feld/der Aktion plus zusammenfassende Meldung; nicht lediglich am fernen Seitenanfang.
- Status immer Text plus Symbol, Farbe ergänzend. Neue asynchrone Meldungen über geeignete Live-Region; nicht den ganzen Kalender ständig neu ansagen.
- `details`/Dialoge verwenden native Tastatursemantik. Öffnen mit bewusstem Fokusziel, Schließen zum Auslöser. Der Dialogabschluss darf den letzten Inhalt nicht überdecken; sticky Footer nur mit reserviertem Platz und Fokusprüfung.
- Weißraum unterstützt Gruppierung, erzeugt aber keine kilometerlangen Leer-/Hinweisblöcke. Maximal drei Kennzahlen, die zur aktuellen Aufgabe gehören; lange Fachtexte und Suchspur nicht vor dem Kalender.
- 320/390/768/1440/2560 px prüfen. Dokument kein horizontaler Überlauf; breite Tabellen in beschrifteten lokalen Scrollregionen. Reduzierte Bewegung respektieren. Kein Animationszwang für Fortschritt.

## 5. Vergleichbare Abnahmekriterien

Diese Kriterien müssen mit einer neuen, versionierten Referenzmessung gegen dieselben Testdaten belegt werden. Keine Prozentersparnis vor realem Nachherlauf behaupten.

1. **Fortsetzen**: aus derselben Projektübersicht gespeicherten Plan mit einer statt zwei Aktivierungen erreichen; Modell, Fixierungen und Dirty-Semantik unverändert. Reload wird in beiden Messungen separat gezählt.
2. **Ergebnis sichtbar**: erster Dienst auf dem 1440×1000-Referenzscreen ohne Scrollen sichtbar; auf 390×1000 zumindest Kalenderbeginn und erste relevante Zeile sichtbar. Ergebnisdetails dürfen weiterhin aufklappbar vollständig gelesen werden. Ausgangs-y erster Dienst: 1046/1716.
3. **Persönliches Soll**: erste Personenzeile/Soll direkt im Team-Viewport auf Desktop, mobil ohne vorheriges Durchlaufen der Gruppenadministration. Ausgangswert erste Sollzelle y=1952 (Desktop). Anzahl der standardmäßig layout-sichtbaren Controls unter dem bisherigen 55/54-Wert; finale Grenze nach tatsächlicher Gestaltung festlegen, nicht Felder blind verstecken.
4. **Gezielte Diagnose**: ein konkretes Problem kann mit klarem Rückkehrpunkt korrigiert werden, ohne erneut die Kategorie zu suchen. Profilbestätigung bleibt ausdrücklich; dasselbe 12→10-Hinweise-Szenario muss unveränderte Mitarbeiter/Freigaben/offene Angaben nachweisen. Falls für vollständige Profile weiterhin ein Seitenwechsel nötig ist, darf Rückkehr den Filter/Fokus nicht verlieren.
5. **Mobile Navigation/Import**: alle vier Hauptwege lesbar erreichbar, keine Dokumentbreite > Viewport in der dokumentierten 320-px-Importsituation. Eigene Tabellen dürfen weiter scrollen; Daten/IDs nicht abschneiden oder ändern.
6. **Datei-/Speicherfehler**: dieselben Dirty-/503-/Invalid-JSON-Szenarien erhalten Daten und Wiederholung. Syntaxfehler erhält verständlichen Hinweis statt ausschließlich generischem Numeric-Fidelity-Text. Die numerische Sicherheit bleibt vollständig wirksam.
7. **Unveränderter Datenvertrag**: CSV/XLSX je sechs Referenzeinteilungen und 2880 Minuten, exakte Person-/Bedarfs-IDs, Fixierungen, Projektbackup und Wiederaufnahme. Umfangreichere Rand-/Numerik-/Supervisionsfälle bleiben durch komplette bestehende Suiten geschützt.
8. **Bedienqualität**: echter Enter/Escape/Tab-Pfad, benannte Inputs, Fokus bei lokalen Editoren, Dateiauswahl-Event, leere/dirty/pending/disabled/error-Ansichten; keine Behauptung allgemeiner Barrierefreiheit allein aus DOM-Checks.

## 6. Umsetzung in getrennten, überprüfbaren Slices

### UX-02A — Oberfläche und Kontinuität

Zuerst RED-Browserregression für Fortsetzen zum Plan und Sichtbarkeit des ersten Dienstes. Dann die bestehende Ausgabe so neu ordnen, dass Kalender/Projektkontext zuerst stehen und technische Suchdetails zugeklappt bleiben; kein Solver/API-Wechsel. Parallel gedachte Navigation erst nach erwiesenen Lebenszyklus-/Busy-Regeln zusammenführen. Betroffene Dateien voraussichtlich `static/index.html`, `workspace.js`, `app.js`, `design.css`, passende Browser-/Handlerregressionen. Nur ein Koordinator schreibt.

### UX-02B — Navigation und schmale Ansichten

Planen und Dienstplan in einer konsistenten Planoberfläche; Dienste/Bedarf unter Einrichtung. Legacy-Selektoren/Navigationstests nicht bloß löschen: gleiche Fachaufgaben über neue öffentliche Controls beweisen. 320-px-Überlauf als authentische RED-Reproduktion zuerst isolieren. Favicon als separate kleine Regression mit eigener lokaler Ressource, CSP unverändert.

### UX-03 — Häufige Eingaben vor Gruppen-/Expertenaktionen

Teamtabellen anheben, Freigaben bewusst erreichbar lassen, Gruppenaktionen offenlegbar machen; Einrichtung und Import getrennt führen. Datenkopien/Bestätigungen und zentrale Operationssperren nicht duplizieren. Bestehende JSON-Erweiterung und CSV bleiben erreichbar.

### UX-04 — Aufgabenbezogene Diagnose und Plankorrektur

Konkrete Problemroute und Rückkehrpunkt; kontextnaher Assignment-Editor; vollständige Invalid/Incomplete-Flags und Ersatzvalidierung erhalten. Post-Commit-Quittierungsfehler als separates, bereits bekanntes Robustheitsproblem mit gezielter Regression bearbeiten.

### UX-05 / Integration

Denselben `baseline-e`-Aufgabenumfang mit neuer Bedienung wiederholen und Messmethoden sauber konstant halten. Echte Verbesserungen statt Screenshots behaupten. Vollständige Python-/Node-/Browsersuiten, Schema-Parität, Offline-Build/Clean-Install, Datenschutz und unabhängiges Review des eingefrorenen Quellstands. Erst danach passende unbenutzte Version wählen/prüfen bzw. vor Main-Push im eingefrorenen Stand integrieren und ohne zusätzliche Feature-CI-Stufe direkt nach main veröffentlichen. Exakte main-CI, OCI-Revision/Digest, Tags und Releaseassets nach dem Mandat verifizieren; ein lokales UX-Dokument allein begründet keine erneute Veröffentlichung von 0.29.1.

## 7. Bewusste Nichtziele

Keine neue Authentifizierung, keine externe Telemetrie, keine produktive SP5-Verbindung, keine Quellenmigration, keine automatische fachliche Zustimmung, kein Wechsel von Planungs-/Kontingentregeln, kein UI-Framework-Ersatz. Kein öffentlicher Previewserver. Der aktuelle Slice verändert weder Produktquellcode noch veröffentlichte Versionen; diese Entwurfsdatei wird bei der ersten Implementierungsveröffentlichung in die Projektdokumentation übernommen und mit tatsächlichen Ergebnissen ergänzt.
