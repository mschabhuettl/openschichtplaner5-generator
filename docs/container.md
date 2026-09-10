# Docker-Image

## Vorgebautes Image starten

Die Datei `compose.yaml` verwendet das Image aus der GitHub Container Registry:

```sh
docker compose pull
docker compose up -d
```

Die Weboberfläche liegt unter `http://127.0.0.1:8080`. Das benannte Volume `generator-state` hält Entwürfe, Matrixergänzungen und Jobs. Originaldateien und Zugangsdaten gehören nicht in das Image. Zum Aktualisieren erneut die beiden Befehle ausführen; die gespeicherten Entwürfe bleiben im Volume.

Das Image heißt `ghcr.io/mschabhuettl/openschichtplaner5-generator:latest` und wird für `linux/amd64` gebaut. Für einen reproduzierbaren Stand kann in Compose stattdessen der Tag `sha-<vollständige Commit-ID>` oder der Digest verwendet werden. `latest` wird nur nach erfolgreichen Containerprüfungen auf `main` aktualisiert.

## Interne SP5-API verbinden

Die API muss aus dem Container erreichbar sein. `localhost` im Container bezeichnet den Container selbst, nicht den Docker-Host. Verwende die tatsächlich konfigurierte interne Adresse; es ist kein öffentlicher API-Endpunkt erforderlich.

Die Basis-URL kann in einer **lokalen, nicht versionierten** `.env` neben Compose gesetzt werden:

```dotenv
SP5_API_URL=http://192.0.2.10:8000
```

Die Beispieladresse ist ein Dokumentationsplatzhalter und muss ersetzt werden. Zugangstoken nicht in `.env`, Compose, Kommandozeilen oder URLs schreiben. Falls die API einen Token erfordert, lege ihn lokal in einer nur für den Betreiber zugänglichen Datei ab und ergänze eine lokale `compose.override.yaml`:

```yaml
services:
  generator:
    environment:
      SP5_API_TOKEN_FILE: /run/secrets/sp5_api_token
    secrets:
      - sp5_api_token
secrets:
  sp5_api_token:
    file: ./secrets/sp5-api-token
```

Die Token-Datei muss für den Containerprozess (UID 10001) lesbar sein. Compose-Secrets sind bei lokalem Docker Compose dateibasierte Mounts, kein verschlüsselter Tresor. Diese Dateien und die lokale Override-Datei nicht ins Repository übernehmen. Nach Änderungen `docker compose up -d` ausführen. In der Oberfläche die API als Datenquelle auswählen; importierte Daten und Entwürfe bleiben in der lokalen Umgebung. Die Verbindung ist lesend, eine Übernahme zurück in originale SP5-Bestände ist nicht freigegeben.

## SP5-Stammverzeichnis schreibgeschützt einbinden

Alternativ zur API eine lokale `compose.override.yaml` anlegen:

```yaml
services:
  generator:
    environment:
      SP5_SOURCE_ROOT: /source
    volumes:
      - type: bind
        source: /absoluter/pfad/zum/stammverzeichnis
        target: /source
        read_only: true
```

Anschließend `docker compose up -d` ausführen und in der Oberfläche `/source` laden. Die Quelle muss für UID 10001 lesbar sein; der Container verändert keine Quellberechtigungen. API- und Verzeichnis-Konfiguration können in einer gemeinsamen Override-Datei kombiniert werden.

Der Hostport ist absichtlich nur auf Loopback veröffentlicht. Eine Netzwerkfreigabe der Generatoroberfläche erfordert eine separat geeignete Zugangsabsicherung. Echte Bestände werden ausschließlich vom Betreiber lokal geprüft; für Fehlerberichte ausschließlich synthetische Reproduktionen verwenden, keine Personal- oder Dienstplandaten.

## Lokal bauen

```sh
docker build -t openschichtplaner5-generator:local .
docker run --rm -p 127.0.0.1:8080:8080 -v generator-state:/state openschichtplaner5-generator:local
```

## Image-Build und zusätzliches Downloadarchiv

Der Workflow **Container** baut auf GitHub, prüft Berechnung und unabhängige Validierung ohne Netzwerk und startet die Weboberfläche. Erst danach veröffentlicht er auf `main` die geprüften Tags in GHCR. Featurebranches werden geprüft, veröffentlichen aber kein `latest`. Der Workflow verwendet die integrierte GitHub-Anmeldung mit Paket-Schreibrecht; ein zusätzliches Registry-Passwort ist nicht erforderlich.

Zusätzlich stellt jeder erfolgreiche Build ein Artefakt `openschichtplaner5-generator-linux-amd64` bereit. Es enthält das tatsächliche Image und eine SHA-256-Prüfsumme; die Aufbewahrung beträgt 30 Tage. Nach Download und Entpacken:

```sh
sha256sum -c SHA256SUMS
gunzip -c openschichtplaner5-generator-linux-amd64.tar.gz | docker load
docker run --rm -p 127.0.0.1:8080:8080 -v generator-state:/state openschichtplaner5-generator:local
```

Die Berechnung funktioniert nach Installation ohne externen Netzzugriff. Eine konfigurierte interne API-Verbindung benötigt ihren lokalen Netzwerkzugriff beim Import. `--network none` wird für die eigenständigen CLI-Prüfungen verwendet, nicht für einen vom Host erreichbaren Webserver.
