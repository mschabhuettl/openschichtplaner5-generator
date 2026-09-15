# Version 0.23.0 – Mehrere Suchprozesse für die Auftragsrechnung

Diese Freigabe baut auf 0.22.0 auf. Sie ändert keine harte Regel, keinen Bedarf
und keine Freigabe. Sie ändert, **wie viel Rechenleistung** eine Auftragsrechnung
nutzt, und macht die Suche dabei sichtbar.

## Was bisher ungenutzt blieb

Seit Langem stand im Quelltext: OR-Tools 9.15 kann bei paralleler Qualitätssuche
an einem gültigen Demomodell abstürzen; deshalb rechnete **jede** Planung mit
einem einzigen Suchprozess. Auf einer Maschine mit zwölf Kernen arbeitete elf
Zwölftel der Rechenleistung nicht mit.

## Gemessen, nicht vermutet

Drei Läufe je Einstellung, je 150 Sekunden, identische echte Quelldaten, nur
nicht identifizierende Aggregate:

| | 1 Suchprozess | 8 Suchprozesse |
|---|---|---|
| offene Pflichtstellen | 12 / 13 / 13 | **8 / 8 / 8** |
| gewichtete Bewertung (Mittel) | 866.397 | **629.083** |
| geteilte Wochenenden | 7 / 6 / 6 | **2 / 2 / 2** |
| mittlere Freizeitblocklänge | 2,83 Tage | **3,08 Tage** |
| Abstürze | – | 0 |

Der dokumentierte Absturzfall wurde außerdem zehnmal mit acht Suchprozessen
nachgestellt: kein Absturz. Zehn Läufe beweisen nicht, dass ein sporadischer
Absturz verschwunden ist — deshalb bleibt eine Absicherung.

## Was sich geändert hat

- **`solve(..., workers=…)`** nimmt die Zahl der Suchprozesse entgegen und weist
  sie im Ergebnis unter `parameters.workers` aus. Werte unter eins werden auf
  eins angehoben.
- **Die Bibliotheksvorgabe bleibt einspurig.** Aufrufe aus Tests und
  Kommandozeile bleiben damit reproduzierbar. Nur der Auftragsprozess rechnet
  parallel, mit `min(8, Kerne)`.
- **Rückfallweg.** Endet der Rechenprozess ohne Ergebnis, während der Auftrag
  noch als laufend geführt wird, wiederholt der Arbeitsprozess die Rechnung
  **einmal einspurig**. Ein seltener Absturz kostet damit Zeit, nicht den Plan.
  Abgebrochene, abgelaufene und bereits abgeschlossene Aufträge werden nicht
  wiederholt; ein zweiter Absturz gilt als Fehlschlag.
- Die Reparaturphase erbt die Zahl der Suchprozesse.

## Grenzen der Aussage

- **Mehrere Suchprozesse sind nicht reproduzierbar.** Dieselbe Eingabe kann
  verschiedene, gleich gültige Pläne ergeben. In der Messreihe lieferten die drei
  parallelen Läufe zwar dasselbe Ergebnis, das ist aber keine Zusage.
- Die unabhängige Ergebnisprüfung bleibt unverändert und einspurig. Kein Plan
  wird übernommen, den sie nicht bestätigt.
- Ein grüner Testlauf bleibt kein Nachweis eines brauchbaren Echtdatenplans.

## Prüfstand

Vollständige Testsuite, Ruff und dreizehn Browserabläufe laufen grün. Sieben neue
Tests decken ab: die einspurige Bibliotheksvorgabe, die Übernahme und Meldung
einer gewählten Prozesszahl, unsinnige Werte, und die Regel für den zweiten
Versuch in allen vier Zuständen. Sie schlagen ohne die Änderung fehl.
