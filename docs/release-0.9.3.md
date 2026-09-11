# Version 0.9.3 – Qualifikationspflicht bei Einstellungsübernahme erhalten

## Wichtige Korrektur

Beim erneuten SP5-Import mit aktivierter Einstellungsübernahme wurden bisher persönliche Qualifikationen kopiert, aber nicht die zusätzliche Qualifikationspflicht der Position. Dadurch konnte eine zuvor ausdrücklich aktivierte Pflicht im neuen Projekt ohne Hinweis entfallen.

Die Übernahme erhält nun die aktivierte Pflicht, die geforderten Qualifikationen und deren Mindestniveau für eindeutig übereinstimmende Positionen. Dafür müssen Positionskennung, Dienst und Arbeitsplatz übereinstimmen. Gültigkeiten persönlicher Freigaben und Nachweise werden weiterhin nicht verlängert.

Bereits aktive Anforderungen aus dem neuen Import werden nicht abgeschaltet. Weichen zwei aktive Anforderungssätze voneinander ab, bleiben die aktuellen Importanforderungen erhalten und ein offener Prüfpunkt verlangt den fachlichen Abgleich. Kann eine frühere Pflicht keiner aktuellen Position eindeutig zugeordnet werden, wird dies ebenfalls als offener Prüfpunkt festgehalten. Solche offenen Angaben verhindern die Berechnung bis zur Klärung. Eine aktivierte Pflicht mit leerer Qualifikationsliste bleibt aktiviert und muss weiterhin ausdrücklich korrigiert werden.

**Bereits übernommene Projekte werden nicht rückwirkend repariert.** Falls in 0.9.0 bis 0.9.2 eine Einstellungsübernahme verwendet wurde, die zusätzlichen Qualifikationsanforderungen unter „Regeln & Bedarf“ mit dem ursprünglichen Projekt vergleichen und betroffene Pläne anschließend neu berechnen beziehungsweise prüfen.

## Weitere Verbesserungen

- Die Bereitschaftsprüfung meldet eine leere zusätzliche Qualifikationspflicht nur für Positionen, die tatsächlich in Bedarfen verwendet werden. Eine unbenutzte Katalogposition erzeugt keinen solchen Fehlalarm. Sobald die Position in einem Bedarf verwendet wird, greift die Prüfung wieder.
- Enthalten sind die [Engpassdiagnosen aus 0.9.2](release-0.9.2.md), einschließlich der Hinweise bei gültigen Teilplänen und des direkten Sprungs zum betroffenen Bedarf.

Persönliche Dienstfreigaben reichen bei neuen SP5-Importen weiterhin standardmäßig aus. Zusätzliche Qualifikationsanforderungen bleiben optional, sind aber nach ausdrücklicher Aktivierung verbindlich.

## Aktualisieren und prüfen

Vor dem Update Projekte über „Projekt sichern“ exportieren. Nach erfolgreicher Container-Veröffentlichung `ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.3` verwenden und das bestehende Zustandsvolume beibehalten. Eine laufende Installation wird nicht automatisch aktualisiert.

Neue Regressionen prüfen die unveränderte Übernahme aktiver Pflichten, Mindestniveaus, leere aktive Anforderungssätze, abweichende Arbeitsplätze, verschwundene Positionen und widersprüchliche Importanforderungen. Der Browserablauf prüft den erneuten SP5-Import mit Einstellungsübernahme bis zum dauerhaften Speichern. Die vorhandenen [Release-Gates](verification.md) bleiben verbindlich; der Workflow-Lauf des veröffentlichten Commits belegt den tatsächlichen Prüfstatus.
