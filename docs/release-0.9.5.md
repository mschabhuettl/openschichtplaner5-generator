# Version 0.9.5 – Ungültige Rechenzeitlimits früh erkennen

Die Kommandozeile akzeptierte bisher mit `--time-limit` auch `nan`, `inf` und `-inf`. Solche Werte sind keine endlichen Rechenbudgets: `nan` konnte erst nach dem Modellaufbau als ungültiges Modell erscheinen, positive Unendlichkeit setzte keine endliche Rechengrenze.

Der gemeinsame Solver-Einstieg weist diese Werte jetzt vor der Eingabeprüfung und dem Modellaufbau mit einem verständlichen Hinweis zurück. Die CLI endet mit Eingabefehlercode `2` und legt keine Ergebnisdatei an. Auch direkte Python-Aufrufe erhalten einen `ValueError`. Die bisherigen Bedeutungen endlicher Zeitlimits und die fachlichen Planungsregeln bleiben unverändert. Die Weboberfläche begrenzt ihr Zeitbudget bereits auf positive Werte bis 600 Sekunden.

Die [Projekt- und Metadatenprüfungen aus 0.9.4](release-0.9.4.md) sind enthalten. Persönliche Dienstfreigaben bleiben erforderlich; ausdrücklich aktivierte zusätzliche Qualifikationsanforderungen bleiben verbindlich.

## Aktualisieren und prüfen

Vor einem Update Projekte sichern. Nach erfolgreicher Veröffentlichung kann das Image `ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.5` mit dem bestehenden Zustandsvolume verwendet werden. Laufende Installationen werden nicht automatisch verändert.

Sechs neue Regressionen prüfen die drei nicht-endlichen Werte im Python-Einstieg und in der CLI, einschließlich verständlicher Fehlermeldung und fehlender Ergebnisdatei. Die vorhandenen [Release-Gates](verification.md) prüfen den endgültigen Commit einschließlich Paketinstallation, Browserablauf, Container, netzloser Berechnung und Rückprüfung des veröffentlichten Images. Maßgeblich ist der tatsächliche Workflow-Status des Releases.
