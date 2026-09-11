# Version 0.9.18 – Offene Importangaben gezielt bearbeiten

„Offene Angaben“ zeigt statt einer unbegrenzten Liste zehn Meldungen je Seite
und eine Textsuche. Die Gesamtzahl bleibt sichtbar. Keine Treffer bedeuten nur,
dass die Suche nicht passt; andere offene Angaben werden nicht entfernt.

Jede Klärung bleibt eine ausdrückliche Einzelaktion nach fachlicher Korrektur.
Auch bei identischen Meldungstexten wird nur der tatsächlich ausgewählte Eintrag
entfernt. Profile, Freigaben und sonstige Angaben bleiben unverändert. Eine
Sammelfreigabe oder automatische fachliche Bestätigung wird nicht eingeführt.

Die vorhandenen Seitensteuerungen behalten nun beim Seitenwechsel den
Tastaturfokus am entsprechenden Knopf; an der ersten/letzten Seite erhält der
neue Bereichshinweis den Fokus. Die Navigation muss nicht wieder vom Seitenanfang
angesprungen werden. Dieselbe vorhandene Seitensteuerung wird wiederverwendet.

## Prüfungen

Der synthetische Browserablauf lädt 1.001 offene Angaben, prüft zehn sichtbare
Meldungen, Suche ohne Treffer, zwei identische Meldungen und das Entfernen nur
des zweiten ausgewählten Duplikats. Suche und Seitenwechsel ändern weder
Projektversion noch Projektdaten. Desktop/Mobil und Tastatur-Navigation werden
geprüft, einschließlich der letzten Seite bei Vergleichsdiensten.

Die [Änderungen aus 0.9.17](release-0.9.17.md) bleiben enthalten.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen werden nicht automatisch aktualisiert.
