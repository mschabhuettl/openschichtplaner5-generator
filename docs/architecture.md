# Architektur

`sp5generator.models` ist der versionierte JSON-Vertrag (1.0). Schemaausgabe und Beispiele verwenden dieselben Pydantic-Modelle wie CLI, Jobs und Adapter. IDs sind Referenzen, Namen nur Anzeige. Ein Snapshot enthält Zeitraum, Kontext, Zeitzone, Revision, Regelversion, Herkunft und bestätigte bzw. noch ungeklärte Eingaben. Sein kanonischer SHA-256-Hash bindet das Ergebnis an alle Eingabewerte.

- **openschichtplaner5-generator:** allgemeine Modelle, zeitliche Domänenfunktionen, CP-SAT-Optimierung, unabhängige arithmetische Prüfung, Export, optionale Jobverwaltung und lesender Adapter. Der reine Solver erhält nur einen Snapshot und Parameter.
- **libopenschichtplaner5:** native Tabellenformate, Datenzugriff und bestehende Sollstundenberechnung. Der Adapter importiert diese Library erst bei Verwendung; der Kern benötigt sie nicht.
- **openschichtplaner5-api:** Anmeldung, Rechte, Sichtbarkeit, HTTP-Endpunkte, persistente Vorschläge und ausdrückliche Übernahmeaktion. Generatorinstallation und Aktivierung sind optional.
- **openschichtplaner5:** integrierte Generatoransicht mit bestehenden Navigationselementen und authentifiziertem HTTP-Client.

Der HTTP-Prozess führt keine langen Solverläufe aus. Er schreibt Jobs in einen privaten SQLite-Store. Ein separat gestarteter Worker mit exklusiver Betriebssystem-Dateisperre führt jeweils einen Berechnungs-Unterprozess aus. Sessionzustände werden nicht an diesen Prozess übertragen. Die Identität ist beim Enqueue bereits geprüft; Übernahme erfordert eine neue Rechteprüfung.

Der Validator erzeugt sein Urteil aus Snapshot und Einteilungen neu, ohne Variablenwerte oder Status des Solvers zu übernehmen. Reine Zeit-/Eignungsfunktionen werden geteilt. Komplexe Ruheprüfungen können ungültige Kandidaten während der Optimierung ausschließen; nur unabhängig geprüfte Kandidaten werden als Lösung ausgegeben.

Native SP5-Gesamtübernahme ist nicht implementiert: Die existierenden Writer teilen keine durchgehende Transaktion mit zusätzlich dateibasierten Regeln. Das Experiment ersetzt diese Grenze nicht durch einzelne Tabellenlocks oder einen frühen Versionsvergleich.
