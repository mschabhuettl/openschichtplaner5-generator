# Betrieb und Datenhaltung

## Aktivierung

Generator und API aus den Integrationscheckouts installieren. Für die API explizit setzen:

```sh
export SP5_GENERATOR_ENABLED=1
export SP5_STATE_DIR=/tmp/sp5-generator-state
sp5-generator worker --store /tmp/sp5-generator-state/generator.sqlite
```

Den Worker separat zum bestehenden API-Start ausführen. Exakt dasselbe Zustandsverzeichnis verwenden. Ohne Worker bleiben Jobs sichtbar in der Warteschlange; es werden keine Fortschrittsprozente erfunden. Das API-Paket startet auch ohne Generatorinstallation; die Capability-Antwort meldet ihn dann als deaktiviert.

Ein Worker je Store, ein Berechnungsprozess gleichzeitig, maximal 20 wartende/laufende Jobs und maximal 600 Sekunden konfiguriertes Solverlimit. Die Initialisierung des Modells und nachgelagerte Prüfung können zusätzliche Zeit kosten; der Worker hat eine zusätzliche endliche Laufzeitgrenze. Der Store ist lokal; kein Netzlaufwerk und keine zwischen Hosts geteilte SQLite-Datei verwenden.

Zustände: `queued`, `running`, `succeeded`, `cancelled`, `failed`. Solverstatus und Jobstatus sind getrennt: Ein erfolgreich ausgeführter Job kann Unlösbarkeit melden. Abbruch beendet den Prozess und verhindert spätes Überschreiben des Abbruchzustands. Nach Worker-Neustart werden unterbrochene laufende Jobs als fehlgeschlagen markiert; erneute Berechnung wird ausdrücklich gestartet. Ergebnisse und Warteschlange überleben einen Neustart.

Snapshots und Ergebnisse enthalten lokale Planungsdaten. Der Store wird mit Dateimodus 0600 angelegt; das übergeordnete Verzeichnis sollte nur dem Betreiber zugänglich sein. Betriebssystemzugriff, Sicherung, Aufbewahrung und Löschung liegen beim Betreiber. Keine Dateninhalte in Fehlermeldungen oder externe Protokolldienste übernehmen. Die reine Berechnung benötigt nach Installation keinen Netzwerkzugriff.

## Entwürfe und Versionen

Speichern ersetzt nur einen Entwurf desselben Benutzers mit passender Revision und erhöht die Revision. Jobs enthalten einen unveränderlichen Eingabesnapshot. Eine nachträgliche Bearbeitung verändert nicht laufende Berechnungen. Für Neuberechnung aktuelle Einteilungen als vorherigen Entwurf übergeben und ausgewählte Einteilungen fixieren.

## Übernahme

Native SP5-Übernahme liefert einen ausdrücklichen Nicht-unterstützt-Fehler; DBF- oder einzelne PostgreSQL-Schreibaufrufe werden nicht verwendet. Read-only und Benutzerrechte bleiben wirksam. Rein lesende SP5-Quellen können separat gespeicherte Vorschläge liefern; die Ausnahme umfasst ausschließlich definierte Vorschlagsendpunkte und niemals Übernahme.

Für einen isolierten synthetischen Testbestand kann `SP5_GENERATOR_SYNTHETIC_APPLY=1` gesetzt werden. Dieser Modus akzeptiert nur Snapshots mit Quelle `synthetic` und schreibt ausschließlich die `accepted`-Tabelle des Generator-Stores. Er ist kein Ersatz für eine Originaldatenübernahme.

Die Testübernahme prüft Rolle, Dienstschreibrecht und Read-only erneut. Innerhalb einer einzigen `BEGIN IMMEDIATE`-Transaktion prüft sie Snapshot-Hash, zuvor akzeptierte Revision und den unabhängigen Validator. Ergebnis, Idempotenzbeleg und Auditprotokoll werden zusammen geschrieben. Ein Fehler beim Audit rollt alles zurück. Derselbe Idempotenzschlüssel und Job liefern denselben Beleg; Wiederverwendung für andere Jobs wird abgelehnt. Parallele Änderungen können den Prüf-/Schreibabschnitt nicht überholen.

Die angenommenen Einteilungen überschreiben keine Originalabwesenheiten oder Sonderdienste, da der Teststore überhaupt nicht mit ihnen schreibt. Für eine spätere native Integration müssen alle relevanten Writer einschließlich Zusatzregeländerungen an derselben Versions-/Transaktionsgrenze teilnehmen.

## Eigenständige synthetische Webdemo

Mit benachbarten Generator-/API-/Frontend-Checkouts lässt sich die Integration ohne Originaldatenbestand starten:

```sh
python -m pip install ./openschichtplaner5-generator ./openschichtplaner5-api
python -m sp5api.generator_demo --state-dir /tmp/sp5-generator-demo --port 8000
```

In einem zweiten Terminal:

```sh
cd openschichtplaner5/frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Die Demo bindet ausschließlich Loopback und startet ihren Worker selbst. Die Anmeldung ist ausdrücklich anonym und synthetisch: beliebige nichtleere Formularwerte führen ausschließlich zu Testperson 001. Es werden keine echten Zugangsdaten benötigt, geprüft oder gespeichert. Danach **Generator** öffnen. Der Demo-Server verweigert native Imports und nichtsynthesische Snapshots, verwendet einen markierten separaten Zustandsordner und lädt keinen Original-Anwendungs-Lifecycle. Dieser Startweg prüft nicht die reguläre Anmeldung gegen ein SP5-System.
