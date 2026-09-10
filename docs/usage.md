# Bedienung

1. In der bestehenden Anwendung **Generator** öffnen und synthetische Demo, JSON oder den lesenden SP5-Import auswählen. Zeitraum, Team und explizite Zeitzone prüfen.
2. Offene Pflichtangaben und Herkunft prüfen. Ungeklärte SP5-Felder blockieren verbindliche Planung; nicht durch Löschen einer Meldung fachlich bestätigen.
3. In der Personenmatrix Freigaben, erlaubte Dienstarten und Regelprofile bearbeiten. **Nur Tag/Nacht** begrenzt Einsätze verbindlich; **bevorzugt** ist ein Wunsch. Individuelle Fenster und wechselnde Wochen in der Detailansicht bearbeiten. Erweiterte strukturierte Regeln sind über den JSON-Editor zugänglich.
4. Bedarfe und Profilgültigkeit kontrollieren, Prioritäten und Zeitlimit einstellen, Entwurf speichern und Berechnung starten. Ohne laufenden Worker bleibt der Auftrag wartend. Laufende Aufträge lassen sich abbrechen.
5. Einteilungen, offene Stellen, Stundenabweichungen und Diagnosen prüfen. Unlösbar, noch keine Lösung und ungültige Eingabe sind unterschiedliche Ergebnisse.
6. Einteilungen ändern oder fixieren und erneut validieren. Für Neuberechnung die Änderungen als vorherigen Entwurf verwenden. Der Vergleich zeigt hinzugefügte und entfernte Einteilungen, keine erfundenen Alternativen.
7. Übernahme ist eine separate ausdrückliche Aktion. Der derzeit unterstützte Testmodus ist deutlich vom nativen SP5-Bestand getrennt. Native Übernahme bleibt gesperrt.

JSON ist das verlustfreie Austauschformat. CSV/XLSX enthalten Planungszeitraum, tatsächliche Dienstteile, Salden und offene Stellen. Importierte Texte mit Tabellenformelpräfix werden als Text exportiert.
