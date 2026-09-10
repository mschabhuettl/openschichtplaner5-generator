# Eigenständiger Webbetrieb

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
Produktversion veröffentlicht, beispielsweise `:0.4.0`. Für reproduzierbare
Installationen eine geprüfte Version oder einen Image-Digest festhalten.
Vor Updates eines persistenten Betriebs das Zustandsvolume sichern. Beim
temporären Stack ist keine Wiederherstellung vorgesehen: Importe und Entwürfe
werden beim Neustart verworfen. Ein Imagewechsel kann diesen Verlust nicht
rückgängig machen.

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
