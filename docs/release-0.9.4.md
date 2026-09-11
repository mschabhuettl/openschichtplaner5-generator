# Version 0.9.4 – Beschädigte Projektübersichten sicher zurückweisen

Projektdateien konnten formal gültige Planungsdaten, aber beschädigte Einrichtungs- oder Historienübersichten enthalten. Solche Dateien passierten bisher die Importvorprüfung und konnten anschließend die Browseroberfläche beim Anzeigen der Übersichten unterbrechen.

Die gemeinsame Vorprüfung für Öffnen, Importieren und Speichern prüft nun die bekannten Strukturen von `setup_review`, `history_matrix` und `history_automation`, einschließlich verschachtelter Vorschläge und Beobachtungen. Ungültige Strukturen werden mit einem verständlichen Hinweis auf den betroffenen Metadatenbereich zurückgewiesen, bevor sie das aktuelle Projekt ersetzen. Bestehende gespeicherte Projekte und der aktuell angezeigte Plan bleiben erhalten.

Unbekannte Metadaten und zusätzliche Felder bleiben unverändert erhalten. Fehlende optionale Historienangaben bleiben erlaubt. Die Prüfung vergibt keine Dienstfreigaben und ändert weder Qualifikationspflichten noch fachliche Regeln. Bereits gespeicherte beschädigte Dateien werden nicht automatisch repariert; eine unveränderte Projektsicherung verwenden oder die angegebene Übersicht korrigieren.

Die [wichtige Korrektur aus 0.9.3](release-0.9.3.md) zur Übernahme aktivierter Qualifikationsanforderungen ist enthalten. Deren Hinweis zur Kontrolle bereits früher übernommener Projekte gilt weiterhin.

## Aktualisieren und prüfen

Vor dem Update Projekte über „Projekt sichern“ exportieren. Nach erfolgreicher Container-Veröffentlichung `ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.4` verwenden und das bestehende Zustandsvolume beibehalten. Laufende Installationen werden nicht automatisch verändert.

API-Regressionen prüfen Zurückweisung und unveränderte gespeicherte Projekte. Der vollständige Browserablauf lädt beschädigte Projektdateien und prüft den Erhalt des angezeigten Plans. Der Workflow des veröffentlichten Commits belegt die tatsächlichen Ergebnisse der vorhandenen Python-, Paket-, Browser- und Container-[Release-Gates](verification.md).
