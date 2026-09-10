# SP5-API als lesende Datenquelle

Die eigenständige Weboberfläche kann eine bereits betriebene `openschichtplaner5-api` im internen Netz lesen. Die API benötigt dafür weder das optionale Generatorpaket noch einen Generatorrouter. Sie bleibt für Anmeldung, Sichtrechte und Datenzugriff zuständig. Der Generator schreibt keine Dienste oder Regeln an diese API zurück.

## API im Dev-Modus

Bei einer API mit aktivem `SP5_DEV_MODE=true` ist keine Sitzungstoken-Datei erforderlich. Im Generator `SP5_API_DEV_MODE=true` und `SP5_API_URL` setzen. Der Generator prüft zuerst `/api/dev/mode` und verwendet nur nach ausdrücklicher Bestätigung die vom bestehenden API-Protokoll vorgesehene Dev-Kennung. Eine reguläre API wird nicht automatisch auf diesen Modus umgestellt; eine fehlgeschlagene Anmeldung löst keinen Dev-Fallback aus.

[Separater Portainer-Stack](../compose.portainer-dev.yaml): `API_IP` und `GENERATOR_IP` als Stack-Variablen setzen. Keine Quellverzeichnis- oder Token-Mounts erforderlich. Die Generatoroberfläche liegt auf Port 5006 und hat keine eigene Anmeldung; dieser Stack ist für das kontrollierte interne Testnetz vorgesehen.

## Konfiguration mit Anmeldung

`SP5_API_URL` ist die Basisadresse der bestehenden API. `SP5_API_TOKEN_FILE` zeigt auf eine lokale Datei mit einem gültigen Bearer-Sitzungstoken dieser API. Adresse und Token werden ausschließlich vom Server gelesen; sie gehören nicht in Snapshot, Export oder Browserformular. Die Datei wird schreibgeschützt in den Container eingebunden; siehe [Compose-Konfiguration](container.md#interne-sp5-api-verbinden).

Verwende die reguläre Anmeldung deiner bestehenden API, einschließlich einer dort geforderten zweiten Authentifizierungsstufe. Der Generator umgeht keine Anmeldung und speichert keine Benutzerpasswörter. Ein abgelaufenes oder widerrufenes Sitzungstoken muss lokal durch ein neu ausgestelltes ersetzt werden. Der Generator liest die Datei beim nächsten Import erneut. Verwende eine HTTPS-Verbindung mit gültigem Zertifikat; eine bewusst konfigurierte HTTP-Verbindung bietet keine Transportverschlüsselung. Zertifikatsprüfungen werden nicht abgeschaltet.

In der Oberfläche **Konfigurierte SP5-API** wählen, **Teams laden** drücken, Team und Zeiträume festlegen und **Daten importieren** wählen. Historische Ist-/Soll-Dienste liefern ausdrücklich unbestätigte Matrixvorschläge. Der gesamte Ablauf verwendet lokale Verarbeitung; nur die ausdrücklich konfigurierte API wird beim Import kontaktiert. Die anschließende Optimierung benötigt die API nicht.

## Lokale Prüfung mit eigenem Datenbestand

1. Compose auf dem eigenen Rechner starten und zunächst die synthetische Demo berechnen. Damit sind Oberfläche, Zustandsvolume und Worker unabhängig von der Quelle prüfbar.
2. Die gewünschte API-Adresse und Sitzung lokal konfigurieren. Keine Zugangsdaten oder Originalbestände in das Repository übernehmen.
3. Mit einem überschaubaren Team und Zeitraum importieren. Personalumfang, Arbeitsplätze, Schichtzeiten, Bedarf und Abwesenheiten lokal mit der Quelle vergleichen.
4. Offene Angaben fachlich bearbeiten. Beobachtete Einteilungen sind keine Qualifikationsnachweise. Freigaben, Nachtklassifikation, individuelle Grenzen und Randkontext müssen bewusst geprüft werden.
5. Einen Entwurf berechnen, unabhängig prüfen und gegebenenfalls lokal exportieren. Ein Import oder bestandener Solverlauf ist keine Bestätigung vollständiger Originalsemantik.

Die Snapshot-Konsistenz wird durch wiederholtes Lesen geprüft, nicht durch eine Transaktion über die entfernte API garantiert. Eingeschränkte Abwesenheitssicht, fehlende Schnittstellen und nicht eindeutig übertragbare Zusatzregeln dürfen nicht stillschweigend als uneingeschränkte Verfügbarkeit gelten. Entsprechende Hindernisse bleiben Fehler beziehungsweise offene Angaben.

Originaldaten, Screenshots mit Personalbezug, Exporte und Zugangstoken verbleiben beim Betreiber. Für reproduzierbare Fehlermeldungen ausschließlich einen neu konstruierten synthetischen Fall verwenden. Die Entwicklung und automatisierten Prüfungen dieser Anbindung verwenden synthetische Antworten, keine produktive Netzwerkquelle.
