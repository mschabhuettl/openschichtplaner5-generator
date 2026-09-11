# Version 0.9.7 – Konsistente Ergebniszuordnung

Die unabhängige CLI-Prüfung und die Übernahme in den isolierten synthetischen Testspeicher prüfen jetzt sowohl die Snapshot-ID als auch den Inhaltshash des Ergebnisses. Zuvor konnte ein Ergebnis mit abweichender ID und passendem Hash akzeptiert werden. Der Export prüfte bereits beide Angaben.

Die CLI meldet solche Eingaben mit Exitcode 2 und einer strukturierten Fehlermeldung, ohne einen vorhandenen Prüfbericht zu überschreiben. Eine abgewiesene synthetische Testübernahme schreibt weder Dienstplan noch Quittung oder Audit-Eintrag und verbraucht ihren Wiederholungsschlüssel nicht. Eine spätere Übernahme eines korrekt zugeordneten Ergebnisses bleibt möglich.

Diese Änderung betrifft die Zuordnung gespeicherter Ergebnisse, nicht die fachliche Bewertung ihrer Einteilungen. Persönliche Dienstfreigaben, optionale Qualifikationen und Planungsregeln bleiben unverändert. Eine native Rückübernahme in originale SP5-Bestände wird dadurch nicht eingeführt. Die [Excel-Korrekturen aus 0.9.6](release-0.9.6.md) sind enthalten.

## Prüfumfang

Vier Regressionen prüfen jeweils eine falsche ID und einen falschen Hash an beiden Grenzen. Beide ID-Fälle wurden vor der Korrektur als fehlschlagend reproduziert. Die Tests belegen den Erhalt vorhandener Prüfdateien, ausbleibende Datenbankänderungen und erfolgreiche Wiederholung nach einer Korrektur. Der vollständige lokale Python-Lauf bestand mit 353 Tests; Ruff und die Diff-Prüfung waren ebenfalls erfolgreich.

Vor Veröffentlichung müssen alle bestehenden [Release-Gates](verification.md) für den endgültigen Commit erfolgreich sein: saubere Paketinstallation, Browser, Container ohne Netzwerk, Webstart und GHCR-Rückprüfung. Lokale Tests ersetzen diese Gates nicht.

## Aktualisierung

Vor einem Update Projekte sichern. Nach erfolgreicher Veröffentlichung kann `ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.7` mit dem bestehenden Zustandsvolume eingesetzt werden. Laufende Installationen werden nicht automatisch verändert.
