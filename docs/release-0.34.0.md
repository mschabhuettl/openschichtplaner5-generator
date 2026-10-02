# Version 0.34.0 – Import schrittweise vorbereiten

## Änderungen

- **Projektdatei öffnen** steht direkt bei den Projekteinstiegen. Der SP5-Import
  ist davon getrennt; die synthetische Demo bleibt ein eigener Einstieg.
- Das Importformular führt von **Quelle & Teams** zu **Zeitraum & Vergleich**.
  Es gibt nur eine primäre Importaktion: **Daten importieren**.
- **Monat vorbelegen** und die Vorbereitung eines Folgezeitraums ändern nur die
  Einstellungen. Der Import erfolgt erst nach einer ausdrücklichen Aktion.
- Zeitzone, Vergleich und Historie liegen in aufklappbaren Optionen. Die sichtbare
  Zusammenfassung unterscheidet Vergleichsplan und historische Planbasis sowie
  gegebenenfalls die Mindestzahl historischer Einsatztage für Freigaben.
- Datei-, Quellen- und Importfehler erscheinen lokal mit Fokus. Alte Rückmeldungen
  und Teamauswahlen werden beim Wechsel der Quelle ungültig.
- Unvollständige native Zahleneingaben wie `1e` bleiben bei Navigation erhalten.
  Sie werden nicht als absichtlich leere Werte gespeichert. Bereits laufende
  Prüfungen oder Speicherantworten überschreiben keine neuere Eingabegeneration.
  Synchronisierte Sollfelder und das Zurücknehmen eines Entwurfs nach bestätigtem
  Speichern berücksichtigen den aktuellen, nicht einen veralteten Ausgangswert.

## Messung und Regression

Die Importmessung verwendet synthetische Daten, ein gespeichertes Projekt und
bereits vorhandene Berechnungshistorie. Bei **1440 × 1000**, **390 × 1000** und
**320 × 1000** werden bei geschlossenen Zusatzoptionen höchstens zwölf
layout-sichtbare native Bedienelemente im Importformular nach dem Laden der Teams
geprüft. Die erhaltene Ausgangsmessung zeigte in diesem Zustand siebzehn
(vor dem Laden der Teams: fünfzehn). Die frühere Erkundung scheiterte später
in einem anderen Szenario; ihre erhaltenen Geometriewerte sind kein vollständiger
Abnahmebericht. Das ist keine Aussage, dass alle
Elemente zugleich im Viewport liegen, und keine menschliche Zeitmessung.

Die Browserregressionen umfassen Monatsvorgabe und manuell identische Konfiguration
mit derselben synthetischen API-Quelle sowie separat mit neu erzeugten DBF-Dateien.
Vollständige Requesttexte und typgetreue Antwort-, Aufnahme- und Projektzustände
werden verglichen. Nur die je Import neu erzeugte Projekt-ID und Erstellungszeit
werden zwischen zwei Imports ausgenommen, nach UUID-/UTC-/Zeitintervallprüfung.
Verschachtelte Quellkennungen, Zahlenkategorien und Provenienz bleiben im Vergleich.
Das ist keine Gleichheitsbehauptung zwischen API- und DBF-Import.

Import, Dateiöffnung und Speichern schließen sich gegenseitig aus. Separat davon
prüfen echte verzögerte Quellenantworten die Überlappung mit jeder dieser Aktionen
in beiden Antwortreihenfolgen. Fehler- und Abbruchproben prüfen den Erhalt von
Projekt, unbestätigten Eingaben und Backendzustand. Tastatur- und lokale
Fehlerrückmeldungen werden bei **1440 × 1000** und **390 × 1000** geprüft.

## Grenzen

- Ausschließlich synthetische Daten; keine Produktivbestände oder Änderungen an
  bestehenden Installationen. Die DBF-Quellen bleiben unverändert.
- Chromium/Playwright und Browser-Dateiauswahlereignisse, keine Abnahme eines
  Betriebssystem-Dateidialogs, Screenreaders oder nativer Tabellenkalkulation.
- Explizit zugestellte DOM-Ereignisse während einer gesperrten Aktion testen
  wartende Ereignisse, nicht Tastatureingaben in gesperrte Felder.
- Historische Einteilungen bestätigen weiterhin keine Qualifikationen oder Regeln.
  Import und Dateiöffnung sind kein automatisches Speichern.
- Die weitere Vereinfachung von Diagnose und Plankorrektur ist nicht Teil dieser
  Version. Die bisherigen vier Arbeitsbereiche bleiben bestehen.

## Aktualisierung

Paket- und Imageversion: **0.34.0**. Für reproduzierbare Installationen den
zugehörigen Commit-Tag oder Image-Digest festhalten. Vor einem Update das
Zustandsverzeichnis sichern; Veröffentlichung eines Images startet keine
bestehende Installation neu. Release-Dateien werden erst nach erfolgreicher
Main-CI aus deren exakten Artefakten bereitgestellt.
