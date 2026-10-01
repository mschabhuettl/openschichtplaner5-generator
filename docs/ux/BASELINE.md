> Historisches UX-01-Dokument, unverändert aus der abgenommenen Ausgangsmessung.
> Die genannten Logs, Bilder und absoluten Runnerpfade gehören zum getrennten
> lokalen Abnahmearchiv und sind nicht Bestandteil dieser Distribution.
> Für den umgesetzten Umfang siehe [Version 0.30.0](../release-0.30.0.md).

# UX-01 — gemessene Ausgangslage

## Stand und Geltungsbereich

- Datum: 1. Oktober 2026. Beobachteter Commit: `165c3a003acc1a11ede023e43f75dff28489fc3a` (Version 0.29.1).
- Worktree: `/home/hermes/projects/openschichtplaner5-generator-autonomous`, Branch `develop/autonomous-ux`. Fast-Forward auf den Handoff erneut ausgeführt: bereits aktuell. Alle 16 im Handoff gebundenen Nachweisdateien und alle 311 getrackten Quelldateien geprüft.
- Dies ist die UX-Ausgangsmessung und ein Entwurfsauftrag, **kein bereits implementierter UX-Umbau und keine neue Veröffentlichung**. Der Projektquellcode blieb unverändert. Der zugehörige Entwurf steht in `TARGET-WORKFLOW.md`.
- Verbindliche Messung: `baseline-e/result.json`; reproduzierbares vollständiges Skript: `baseline-e/measure.cjs`. Maschinenlesbare Aggregation und Exportprüfung: `verification.json`. Screenshots/DOM-Protokolle: `baseline-e/`.

## Methode und Grenzen

Reales Headless-Chromium, unveränderte ausgelieferte HTML-/JS-/CSS-Dateien, echte Python-Anwendung, SQLite, Worker, Solver, Validierung und Export. Die SP5-Quell-API besteht ausschließlich aus frisch erzeugten Testpersonen/-diensten in `tests/browser/server.py`. Alle Prozesse liefen über den dauerhaften isolierten Runner, ausschließlich mit Loopback im privaten Netzwerk-Namespace; keine Produktionsdaten, Anmeldedaten oder öffentliche Listener.

Das Skript bedient sichtbare Controls (Klick, Eingabe, Auswahl, Checkbox, Tastatur, Dateiauswahl). `evaluate` liest Zustände und Geometrie bzw. wartet auf Rendering; es ersetzt keine Produktaktion durch einen internen Handler. Der Navigationsevent-Listener beobachtet nur. Backend-GETs prüfen tatsächlich gespeicherte Daten. Einmal wird eine Speicherung verzögert und einmal HTTP 503 eingespritzt; beide sind explizit gekennzeichnete Zustandsprüfungen, keine beobachteten realen Netzausfälle.

Eine **Operation** ist genau ein protokollierter Aufruf; Text eintragen zählt einmal, Tab zum Übernehmen gesondert einmal, Dateidialog öffnen und Datei wählen getrennt. Automatisches Scrollen durch Playwright, Screenshotaufnahme, Viewportwechsel, Abwarten und lesende Orakel sind nicht eingerechnet. Somit sind die Zahlen **keine Mindestklickzahlen, keine gemessene menschliche Arbeitszeit und kein Nutzertest**. Die Navigationstelemetrie enthält automatische Wechsel; wiederholte Events desselben Panels werden in `verification.json` dedupliziert.

Layoutaufnahme 1440×1000 und 390×1000; zusätzliche Importaufnahme 320×1000. Nicht jeder Ablauf wurde vollständig mobil oder ausschließlich per Tastatur wiederholt. Geprüft wurden insbesondere Tastaturöffnung/-schließung des Dialogs, Fokusrückgabe und Importfokus. Ein nativer Chromium-Dateiauswahl-Event wurde bedient; kein vollständiger Betriebssystem-Dateidialog oder Excel-GUI-Test. Für Vorher/Nachher müssen dieselben Zustände und Viewports verwendet werden, nicht bloß andere schönere Screenshots.

Sichtbare Controls: ohne `hidden`, ohne Inhalt geschlossener `details`, ohne Hintergrund eines offenen modalen Dialogs; offscreen, aber layout-sichtbare Controls sind separat von im Viewport liegenden Controls gezählt. Große Tabellen dürfen innerhalb ihrer Region horizontal scrollen. Dokumentüberlauf wird davon getrennt erfasst.

## Tatsächlich bediente Aufgaben

Insgesamt 63 protokollierte Operationen, 33 Screenshots. Die Aufgaben bauen aufeinander auf; nicht als voneinander unabhängige Erstnutzerszenarien summieren.

| Aufgabe | Operationen | Konkreter Pfad und geprüfter Endzustand |
|---|---:|---|
| Neues Projekt | 12 | Neues Projekt → Name, 05.–09.10.2026, Europe/Vienna → drei synthetische Personen → Tagvorlage/Funktion A und gewählte Regeln prüfen → drei ausdrückliche, für diese Testdaten wahre Bestätigungen → Erstellen. Drei Personen, fünf Bedarfe. |
| Persönliches Soll ändern | 3 | In der Teamtabelle erste Sollstunden auf 32 setzen → Tab → Speichern. Backend-Readback: 1920 Minuten. |
| Regeln ansehen, Bedarf anpassen | 5 | Regeln → Regelprofile → Bedarf → 05.10. auf zwei Personen setzen → Tab. Summe Mindestbesetzung sechs. Dies ist ein bewusst gewählter Prüfpfad, nicht der kürzeste reine Bedarfspfad. |
| Plan erzeugen | 3 | Planen → Rechenzeit fünf Sekunden → Speichern und berechnen. Echter Worker: OPTIMAL, valid=true, complete=true, sechs Einteilungen. Die zusätzliche Rechenzeiteingabe gehört zum Skript, ist kein Pflichtschritt der UI. |
| Einteilung fixieren und prüfen | 4 | Kalenderdienst anklicken → Fixieren → Entwurf prüfen → Entwurf dauerhaft speichern. Backend enthält die Fixierung; Prüfung gültig und vollständig. |
| Export | 3 | CSV, XLSX, vollständige Projekt-JSON herunterladen. CSV/XLSX jeweils sechs Einteilungen, Identitäten/Fixierungen stimmen mit Backup überein; 2880 angerechnete Minuten. Keine Excel-GUI-Ausführung. |
| Gespeicherten Entwurf fortsetzen | 3 | Browser neu laden → Projektkarte → Dienstplan. Landet zunächst in Team, obwohl ein gespeicherter Plan vorhanden ist; sechs Einteilungen und Fixierung erhalten. Ohne Reload sind es zwei Benutzeraktionen von der Projektübersicht zum Plan. |
| Synthetische SP5-API importieren | 9 | Projekte → SP5 importieren → API → Teams laden → nur Team B → Datum ab/bis, Zeitzone → Daten importieren. Genau zwei Personen und Gruppe 2, Profil bleibt unbestätigt. Nach automatischem Team-Zwischenschritt landet der Import bei Regeln. |
| Problem gezielt korrigieren | 6 | Planen → Regelprofile prüfen → Profil aufklappen → für diese Testdaten ausdrücklich bestätigen → Planen → Speichern. Hinweise 12 → 10; Mitarbeiter, Freigaben und offene Importangaben unverändert. Kein vollständiger Importabschluss behauptet. |
| Laden/Sperren | 1 | Speichern bei angehaltener echter PUT-Anfrage: Speichern und Neues Projekt gesperrt; nach Freigabe wieder nutzbar. |
| Speicherfehler und Wiederholung | 4 | Name ändern → Tab → Speichern mit eingespritztem 503 → erneut speichern gegen echten Server. Änderung bleibt dirty, danach dauerhaft per GET nachgewiesen. |
| Tastatur/Fokus | 4 | Projekte → Neues Projekt per Enter → Escape → Import per Enter. Fokus jeweils Name, zurück zum Auslöser, dann Datenquelle. |
| Projektdatei fortsetzen | 2 | Aus bereits geöffnetem Import: echte Dateiauswahl öffnen → heruntergeladenes Backup auswählen. Vollständiger Snapshot exakt gleich. Vorbereitender Importzugang gehört zur vorherigen Aufgabe. |
| Fehlerhafte Datei | 4 | Projekte → Import → Dateiauswahl → syntaktisch ungültige Datei. Aktuelles Projekt unverändert, Fehler sichtbar im DOM. |

## Priorisierte Beobachtungen

### UX-B01 · Hoch · Der Plan liegt unter der Erklärung

Nach erfolgreicher Berechnung beginnt der erste Kalenderdienst bei y=1046 (Desktop, 1000 px Höhe), mobil bei y=1716. Vor ihm stehen Kennzahlen und der standardmäßig offene Abschnitt „Wie der Plan entstanden ist“. Screenshot: `solved-1440.png`, `solved-390.png`; zugehörige JSONs enthalten Kontrollkoordinaten. Der Plan ist nach dem Berechnen nicht unmittelbar als Arbeitsobjekt sichtbar. Subjektive Wertung: Suchdetails dominieren die eigentliche Aufgabe.

Ziel: Kalender vor ausführliche Analyse; kompakte Ergebniszeile, vollständige Details weiterhin erreichbar. Vollständigkeit, Gültigkeit, Eingabeprüfung und Speicherstand bleiben verschiedene Aussagen.

### UX-B02 · Hoch · Häufige Teamänderung folgt auf Gruppen-/Expertenwerkzeuge

Bei nur drei Personen liegen die Sollstundenfelder in der Teamtabelle bei y=1952, 2021 und 2089. Vorher stehen Freigabematrix, Gruppenausschluss, Ausbildungs-/Begleitgruppen und persönliche Höchstarbeitszeit-Sammelaktionen. Die Teamseite hat 2422 px Desktop-/3526 px Mobilhöhe und 55/54 layout-sichtbare Controls. Screenshot: `created-team-1440.png`, `created-team-390.png`.

Ziel: Personenliste mit Planen/Soll/Bearbeiten zuerst, Freigaben als klar erreichbare zweite Ansicht, Gruppen-/Massenänderungen nur bei Bedarf aufklappen. Bestehende Regeln werden dadurch nicht deaktiviert.

### UX-B03 · Hoch · Diagnose führt aus dem Arbeitskontext heraus

Eine gezielte Profilbestätigung benötigt im aufgezeichneten Pfad Planen → Regeln → Planen; drei Panelwechsel einschließlich erstem Öffnen von Planen. Das erweiterte Regelpanel erreicht 4253 px Desktop-/7009 px Mobilhöhe. Das einzelne Profil lässt sich zwar bereits gezielt ansteuern, davor bleiben aber Import-, Zeitmuster- und Kontextblöcke vorhanden. `import-diagnosis-*`, `profile-expanded-*`, `diagnosis-after-1440.png`. Die schmale Profilaufnahme behält die vorherige Scrollposition nach Viewportwechsel; sie ist **keine** Behauptung, die Bestätigung sei darin schon sichtbar.

Ziel: Problem mit betroffener Person/Dienst, Entscheidung und Rückkehrpunkt bearbeiten; nach Korrektur dieselbe Problemgruppe wieder zeigen. Keine automatische Sammelbestätigung und kein „alles gut“ bei nur gekürzten Diagnosen.

### UX-B04 · Mittel · Vorhandenen Plan erneut suchen

Die Projektkarte öffnet einen gespeicherten Entwurf immer in Team; erst ein weiterer Klick führt zum Dienstplan. Belegt durch `resume-projects-1440.json`, `resumed-default-1440.json` und Navigationstelemetrie. Auch der neu erzeugte, schon vollständig eingerichtete Testplan startet in Team.

Ziel: Projekt mit gespeichertem Entwurf direkt im Plan öffnen, ohne dessen Prüfung als aktuell auszugeben. Neues/unvollständiges Projekt zeigt seine nächsten Einrichtungsschritte.

### UX-B05 · Mittel · Einrichtung konzentriert zu viel im dritten Dialogschritt

„Schichten & Regeln“ enthält 27 gleichzeitig layout-sichtbare Controls; mobiler Dialog: 960 px Innenhöhe bei 2717 px Scrollinhalt. Fachlich wichtige Bestätigungen und Abschluss liegen weit unter Schichtzeiten und Wochentagen. Screenshot: `wizard-rules-390.png`, DOM mit Dialogmaßen.

Ziel: Diensteinrichtung und bewusste Regelprüfung klar gruppieren, seltene Parameter separat; weiterhin ausdrückliche, nicht vorbelegte Bestätigungen. Weniger Information pro Entscheidung ist wichtiger als die kleinste Zahl von „Weiter“-Klicks.

### UX-B06 · Mittel · Zwei konkurrierende Importeinstiege und verstreute Rückmeldungen

Im Import stehen Schnellstart mit „Monat vorbereiten“ und der ausführliche Quell-/Zeitraumweg nebeneinander. Die primäre Aktion „Daten importieren“ liegt darunter; der Direktdatei-Import ebenfalls. Formular im vorhandenen Arbeitsbereich: 2243 px Desktop-/3634 px Mobilhöhe. Ein Datei-Syntaxfehler wird mit generischem Hinweis zu „JSON-Zahlen oder Daten“ gemeldet. Es gibt im Test keinen Datenverlust; die Verständlichkeit und Platzierung sind das Problem. `import-form-*`, `invalid-file-1440.json`.

Ziel: zuerst Weg wählen (SP5 / Projektdatei / neu); Quelle, Team und Zeitraum in einer zusammenhängenden Aufgabe; optionale Historie/Übernahme separat; Fehler an der betroffenen Aktion mit Wiederholungsmöglichkeit.

### UX-B07 · Mittel · Schmaler Import hat dokumentierten Seitenüberlauf

Bei 320 px Viewport misst die geladene Importansicht 338 px Dokumentbreite. Die 390-px-Aufnahmen weisen keinen Dokumentüberlauf auf. `keyboard-import-320.json` und Screenshot. Ursache noch nicht isoliert; nicht allein der absichtlich horizontalen Hauptnavigation zuschreiben. Als gezielte RED-Regression in UX-02 aufnehmen.

### UX-B08 · Niedrig · Favicon wird durch die bestehende CSP blockiert

Zwei echte Browser-Konsolenmeldungen beim Laden/Reload blockieren das eingebettete data:-SVG. Keine JavaScript-Seitenfehler. Die dritte Konsolenmeldung stammt ausschließlich aus dem absichtlich eingespritzten HTTP 503. Nicht als saubere Browserkonsole darstellen. Lösungskandidat: gleichursprüngliche statische Icon-Datei, **nicht** Abschwächen der CSP.

## Verifikation

`verification.json` wird aus JUnit, TAP, echten Ausführungsprotokollen, DOM-Belegen und Exportdateien berechnet:
- Python: 2549 bestanden, 0 Fehler/Fehlschläge/übersprungen. 63 Warnungen, darunter die hier versehentlich verwendete xunit2/record_property-Kombination und Abhängigkeits-Deprecations; keine „warnungsfreie“ Suite behaupten. Künftige Läufe mit `-o junit_family=legacy` wie im ursprünglichen Runner-Aufruf.
- Node: 299 Unit-/Handlerfälle und 78 Browserregressionen bestanden, zusätzlich der vollständige `check.cjs`-Produktablauf.
- Ruff und 12 Release-Provenienztests bestanden.
- Offline-Paketbau, sdist-Neubau, saubere Core-/Web-Installationen, echter installierter Worker und Exporte bestanden. Keine lokale Docker-Ausführung und keine Veröffentlichung.
- CSV-/XLSX-Readback stimmt bei Identitäten, Fixierungen und Minuten mit dem heruntergeladenen Snapshot überein; Backup wurde zusätzlich über Browser-Dateiauswahl wieder geöffnet.

## Erhaltene Vorversuche

- `exploration-a`: erfolgreiches erstes Teilstück, aber die ursprüngliche DOM-Messmethode zählte Nachfahren geschlossener details mit. Nur zur Entstehungsgeschichte; Messzahlen nicht verwenden.
- `exploration-b`: Exit 1, falsche Harness-Annahme, Import müsse in Team statt Regeln landen. Produkt importierte tatsächlich; Fehlerprotokoll nicht umgeschrieben.
- `exploration-c`: erfolgreiches längeres Teilstück bis Importdiagnose.
- `baseline-d`: Exit 1 am letzten Wait, Harness erwartete die CSS-Klasse `bad` statt des echten `error`. Kein Produktfehler; alles erhalten.
- `baseline-e`: vollständiger erfolgreicher Referenzlauf, korrigierte Sichtbarkeits-/Modalzählung mit Positivkontrollen.

## Reproduktion

Neues, noch nicht vorhandenes Label einsetzen; Nachweise nie überschreiben:

```sh
sh /home/hermes/projects/.automation/openschichtplaner5-generator/run-isolated.sh \
  /home/hermes/projects/openschichtplaner5-generator-autonomous \
  python /home/hermes/projects/.automation/openschichtplaner5-generator/evidence/ux-01/run-check.py \
  reviewer-replay node /home/hermes/projects/.automation/openschichtplaner5-generator/evidence/ux-01/measure.cjs reviewer-replay
```

Der Runner prüft vor/nachher sämtliche getrackten Quellen gegen den Freeze, protokolliert Exit und Loghash, räumt seine Kindprozesse und synthetischen temporären Daten auf. Browserdownloads und Screenshots verbleiben dauerhaft beim Lauf. Unabhängige Abnahme des Mess-/Entwurfsumfangs ist gesondert zu dokumentieren; dieser Bericht erteilt sie nicht selbst.
