# Docker-Image

## Bauen und starten

```sh
docker build -t openschichtplaner5-generator:local .
docker compose up -d
```

Die Weboberfläche liegt unter `http://127.0.0.1:8080`. Das benannte Volume `generator-state` hält Entwürfe, Matrixergänzungen und Jobs. Die Originaldateien gehören nicht in dieses Volume und nicht in das Image.

Für einen Originalbestand ein lesbares Verzeichnis ausdrücklich schreibgeschützt einbinden:

```sh
docker run --rm --name sp5-generator \
  -p 127.0.0.1:8080:8080 \
  -v generator-state:/state \
  --mount type=bind,src=/absoluter/pfad/zum/stammverzeichnis,dst=/source,readonly \
  -e SP5_SOURCE_ROOT=/source \
  openschichtplaner5-generator:local
```

Anschließend in der Oberfläche `/source` laden. Der Prozess läuft als UID 10001. Die Quelle muss für diesen Benutzer lesbar sein; der Container verändert keine Quellberechtigungen. Der Hostport ist absichtlich nur auf Loopback veröffentlicht. Eine Netzwerkfreigabe erfordert eine separat geeignete Zugangsabsicherung.

## Vorgebautes Image herunterladen

Der Workflow **Container** baut auf GitHub für `linux/amd64`, prüft Berechnung und unabhängige Validierung ohne Netzwerk, startet die Weboberfläche und stellt ein Artefakt `openschichtplaner5-generator-linux-amd64` bereit. Es enthält das tatsächliche Image und eine SHA-256-Prüfsumme; die Aufbewahrung beträgt 30 Tage. Es wird kein Paketregister und kein Release angelegt.

Nach Download und Entpacken des Artefakts:

```sh
sha256sum -c SHA256SUMS
gunzip -c openschichtplaner5-generator-linux-amd64.tar.gz | docker load
docker run --rm -p 127.0.0.1:8080:8080 -v generator-state:/state openschichtplaner5-generator:local
```

Die Berechnung funktioniert nach Installation ohne externen Netzzugriff. Der lokale Browserzugriff auf die Weboberfläche bleibt bei normalem Container-Netzwerk möglich. `--network none` wird für die eigenständigen CLI-Prüfungen verwendet, nicht für einen vom Host erreichbaren Webserver.
