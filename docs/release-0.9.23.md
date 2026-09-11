# Version 0.9.23 – Importhinweise gezielt bearbeiten

Offene Angaben zu bestehenden Diensten zeigen den aktuellen Personnamen statt
der technischen SP5-Kennung, wenn die Person im Projekt vorhanden ist. Die
Suche findet sowohl den Namen als auch die ursprüngliche Kennung.

„Person prüfen“ öffnet den vorhandenen Personeneditor mit Tastaturfokus.
„Bedarfe am Datum prüfen“ öffnet die vorhandene Bedarfssuche für den Tag.
Fehlt die Person im aktuellen Projekt, bleibt die ursprüngliche Kennung
sichtbar und ein ausdrücklicher Hinweis erklärt den fehlenden Personenbezug.

Es werden keine Freigaben erteilt, keine Bedarfe ergänzt und keine Hinweise
automatisch geklärt. Die gespeicherten Importhinweise bleiben unverändert;
fachliche Klärungen erfolgen weiterhin einzeln und ausdrücklich. Unbekannte
Hinweisformate werden unverändert angezeigt.

## Prüfung und Aktualisierung

Die synthetische Browserregression prüft Desktop und Mobil, Namen- und
Kennungssuche, gezielte Navigation mit Fokus und fehlende Personen. Sie
vergleicht den vollständigen Projektzustand vor und nach den Prüfwegen:
Regeln, Freigaben, Einteilungen und offene Angaben dürfen sich nicht ändern.
Der bisherige Stand scheitert erwartungsgemäß an der Namensanzeige.

Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Die lokale Benutzerinstallation wird nicht automatisch aktualisiert.
