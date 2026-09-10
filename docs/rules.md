# Regeln, Zeit und Bewertung

Alle hier beschriebenen Regeln sind ausdrücklich konfigurierte technische Regeln,
keine hinterlegten gesetzlichen Mindestwerte. Beispielprofile sind synthetisch.
Ein Profil muss `confirmed=true` sein und den Planungszeitraum lückenlos abdecken.
Mehrere gleichzeitig gültige Profile gelten gemeinsam: keine individuelle
Präferenz kann eine verbindliche Grenze aufheben. Gültigkeitsdaten sind inklusive.

## Identitäten und Eignung

Funktionen und Arbeitsplätze sind frei definierte IDs. Eine gültige, ausdrückliche
Freigabe für beide ist nötig; Gruppenmitgliedschaft ersetzt sie nicht.
`qualifications_required=false` bedeutet ausdrücklich keinen zusätzlichen Nachweis.
Bei `true` müssen alle genannten Nachweise mit ausreichendem Level und bis zum
letzten Einsatztag gültig vorliegen; eine leere Nachweisliste ist nicht erfüllt.
Schichtkategorien sind Daten. `allowed_kinds` begrenzt verbindlich;
`preferred_kind` und `preferred_functions` sind ausschließlich Kosten.
RESTR 1 wird nur mit `approved=true` zugelassen, RESTR 2 niemals.

Betreuung braucht eine tatsächlich eingeteilte Person am selben Arbeitsplatz mit
derselben Funktionsfreigabe und zeitlicher Abdeckung jedes betreuten Dienstteils.
Ihre Freigabe darf nicht selbst betreuungspflichtig sein. `mentor_capacity` ist die
maximale Zahl zugeordneter Betreuungen pro eigenem Dienst. Das gilt auch für
zeitlich getrennte betreute Teile: eine konservative, ausdrücklich dienstbezogene
Kapazität, keine Wiederverwendung nach jeder kurzen Teilaufgabe.

## Zeitsemantik

Alle Einsätze sind halboffene Intervalle `[start,end)` mit explizitem UTC-Offset,
auf ganze Minuten genau. Vergleiche und Dauerberechnungen erfolgen über UTC.
Mehrteilige Dienste dürfen intern nicht überlappen. Eine andere Einteilung darf
nicht zwischen deren Teile geschoben werden. Mehrere getrennte Dienste an einem
Tag sind dagegen bei ausreichender Ruhe zulässig.

Die Snapshot-Zeitzone bestimmt lokale Kalendertage, Beschäftigungs- und
Freigabegültigkeit, Tagesgrenzen und Wochen. Tages-/Wochen-/Perioden-Höchstminuten
zählen reale Einsatzminuten der Teile, einschließlich korrekter Aufteilung über
Mitternacht; Lücken sind keine Einsatzzeit. `paid_minutes` ist ein eigenständiger,
expliziter Wert, der nur für Soll-/Ist-Bewertung eingesetzt wird. Gutschriften sind
keine Arbeitsintervalle und verbrauchen keine Ruhe.

Lokale Verfügbarkeitsfenster werden mit IANA-Zeitzonen aufgelöst. Nicht existierende
Uhrzeiten und mehrdeutige Uhrzeiten ohne explizite Auswahl werden als Eingabefehler
abgewiesen. `localize(..., fold=0|1)` ermöglicht eine explizite Auswahl in Adaptern.
Ein bereits offsetbehafteter Snapshot-Zeitpunkt ist ein eindeutiger Zeitpunkt.
Die allgemeine Demo verwendet UTC.

Verfügbarkeiten sind die Vereinigung expliziter Fenster. Eine leere Liste bedeutet
keine zusätzliche Zeitfensterbegrenzung, nicht das Fehlen einer Funktionsfreigabe.
Jeder ganze Dienstteil muss durch zusammenhängende erlaubte Fenster abgedeckt
sein. Sperrintervalle bleiben zusätzlich verbindlich. Wechselwochen verwenden
`floor((Datum-cycle_anchor)/7) modulo cycle_weeks == cycle_phase`; Anker und Phase
sind ausdrücklich nötig. Verschiedene Gültigkeitszeiträume ermöglichen Modellwechsel.
Fenster über Mitternacht werden auf den folgenden Tag erweitert, jedoch nicht
über ihr Gültigkeitsende hinaus. Gleichzeitige additive Fenster erweitern die
Verfügbarkeit; sie sind deshalb keine zusätzliche Möglichkeit, eine übergeordnete
Sperre zu überschreiben.

## Ruhe und Randkontext

Die tägliche Ruhe läuft vom Ende des letzten Teils bis zum Anfang des nächsten
Dienstes. Alle aktiven Profile an beiden Dienstanfängen werden berücksichtigt.
Nach Nacht gilt zusätzlich `after_night_rest_minutes`. Ein Nachtblock enthält
aufeinanderfolgende Nacht-Dienstanfangstage mit höchstens
`night_block_gap_days` Tagen Abstand. Zum nächsten Nicht-Nachtdienst oder einer
außerhalb dieses Abstands liegenden Nacht gilt
`after_night_block_rest_minutes`; die strengste Ruheanforderung gewinnt.

Arbeitstage zählen jeden lokalen Tag mit Einsatzminuten. Nachttage zählen den
lokalen Anfangstag eines als `night` kategorisierten Dienstes. Wochenendanzahl
zählt unterschiedliche Montag-basierte Wochen mit Arbeit am Samstag/Sonntag,
nicht einzelne Wochenend-Schichten. Serien werden auch über die Planungsgrenzen
mit festen Kontextdiensten geprüft.

Wochenruhe ist ein zusammenhängender freier Abschnitt innerhalb jedes relevanten
Bezugsfensters. Ein über die Fenstergrenze reichendes freies Intervall wird an der
Grenze abgeschnitten: nur der im Fenster liegende Anteil zählt. Diese explizite
Semantik ist strenger als eine Zuweisung einer gesamten grenzüberschreitenden Ruhe
zu genau einer Woche. `weekly_rest_add_daily=false` erlaubt gemeinsame Anrechnung;
bei `true` muss ein zusammenhängender Abschnitt von Wochenruhe plus täglicher
Mindestruhe vorhanden sein.

* `calendar_week`: Montag 00:00 bis nächster Montag 00:00 lokal; das können während
  Zeitumstellung 167 oder 169 Stunden sein.
* `rolling_elapsed`: jedes minutenversetzte Fenster mit genau `window_days*1440`
  verstrichenen Minuten, das den Planungszeitraum berührt. Die Prüfung nutzt alle
  kritischen Schwellen der freien Intervalle plus benachbarte Minuten, keine
  Stichproben an ausgewählten Wochentagen.
* `rolling_local`: jedes reale Minuten-Anfangsintervall bis zum gleichen lokalen
  Uhrzeitwert `window_days` Kalendertage später. Es werden sämtliche Minutenanker
  geprüft. Beim Fensterende gilt die erste Instanz einer mehrdeutigen Uhrzeit;
  eine nicht existierende Uhrzeit wird durch die Zeitzonenabbildung vorwärts auf
  den entsprechenden realen Zeitpunkt normalisiert. Dies ist ausschließlich die
  definierte Fensterregel, nicht die Auflösung eingegebener Verfügbarkeitszeiten.
  Die vollständige Minutenprüfung kann bei langen Zeiträumen deutlich teurer sein.

Der Snapshot muss vollständigen Kontext explizit bestätigen. Der Prüfer verlangt
zusätzlich beidseitige Reserven aus maximaler Ruhe, Serienlänge und Wochenrahmen.
Fehlt Kontext, bleibt `complete=false`, auch wenn alle bekannten Einteilungen
regelkonform sind. Solche Ergebnisse dürfen nicht übernommen werden. Außerhalb
des Planungszeitraums werden ausschließlich vorhandene Fixierungen eingeplant.

## Optimierung und unabhängige Kontrolle

CP-SAT läuft lokal mit einem Suchworker und festem Startwert 0. Diese Einstellung
vermeidet einen in OR-Tools 9.15.6755 reproduzierten Absturz bei paralleler Suche.
Ein erster
Zulässigkeitslauf dient als Ausgangslösung. Bei mindestens 40 Personen wird davor
eine zeitlich begrenzte, nach Arbeitslast geordnete Belegung versucht. Jede
Erweiterung wird arithmetisch geprüft; der fertige Plan wird zusätzlich komplett
validiert und mit fixierten Einteilungsvariablen durch CP-SAT zertifiziert. Nur
ein erfolgreiches Zertifikat liefert einen zulässigen Ausgangsplan. Ein
`OPTIMAL` dieses eingeschränkten Zertifikats bedeutet ausdrücklich keine globale
Optimalität; das Gesamtergebnis bleibt mindestens `FEASIBLE`. Anschließend wird die konfigurierte
gewichtete Bewertung minimiert. Kalenderwochenruhe hat direkte Existenzbedingungen
für freie Intervalle. Komplexe rollierende Regeln werden zusätzlich durch den
unabhängigen arithmetischen Prüfer geprüft. Verletzende Personeneinteilungsmengen
werden mit gültigen Ausschlussbedingungen ausgeschlossen und erneut optimiert.
Kein ungeprüfter Zwischenstand wird als zulässiges Ergebnis geliefert. Zeitlimit
kann daher `UNKNOWN` bedeuten, auch wenn eine noch ungeprüfte Zwischenbelegung
existiert. Eine gefundene gültige Lösung bleibt bei Zeitlimit `FEASIBLE`.

Teilplanung optimiert lexikografisch: zuerst die Zahl fehlender Mindeststellen,
erst nach bewiesenem Minimum die Bewertung. Personelle Grenzen und Maximalbedarf
bleiben unverändert hart. `validation.valid` bezeichnet personelle Zulässigkeit;
`validation.complete` verlangt zusätzlich alle Mindestbedarfe und geprüften
Randkontext. `INFEASIBLE` wird nur nach einem Beweis des bindenden Modells gemeldet.
Ein fehlender Kandidat wird vorab benannt; kombinierte Kandidatenengpässe werden
durch das Modell bewiesen. Die Diagnose beansprucht weder Minimalität noch eine
einzige Konfliktursache.

In der Qualitätsphase gilt

`J = wH EH + wN EN + wW EW + wF EF + wP EP + wA EA`.

* `EH`: Summe absoluter Minutenabweichungen
  `|paid + credit + balance - target|` je Person im Planungszeitraum.
* Belastungskategorien Nacht, Wochenende, Feiertag: Für Person i ist
  `oi = geeignete unterschiedliche Schichten * employment_fraction`.
  Ohne geeignete Gelegenheit wird sie für diese Kategorie nicht verglichen.
  `ci` sind aktuelle Belastungen plus ausdrücklich gelieferte Historienanzahl.
  Mit `O=sum oi`, `C=sum ci` gilt
  `E = sum floor(100 * |ci*O - C*oi| / O)`.
  Einheit: Hundertstel Belastungseinheiten, auf ganze Werte abgerundet.
  Die Gelegenheit berücksichtigt Freigaben, Verfügbarkeit und Abwesenheiten,
  aber nicht die erst durch andere Einteilungen entstehenden Konkurrenzkonflikte.
  Historienwerte müssen für einen konsistenten extern festgelegten Zeitraum
  geliefert werden. Das Modell behauptet keine universelle objektive Fairness.
* `EP`: Summe unerfüllter Dienst-/Freiwünsche mal jeweiliger `priority`, plus
  abweichender Dienstkategorien und Funktionspräferenzen mit Priorität 1.
* `EA`: Zahl hinzugefügter oder entfernter Personen-/Bedarfs-Paare gegenüber dem
  vorhandenen Entwurf. Ein Wechsel kann damit zwei Änderungen zählen.

Die Gewichte werden ausdrücklich im Snapshot gespeichert. Harte Regeln sind
niemals durch diese Kosten abkaufbar. `metrics.weighted_objective_contributions`
enthält die tatsächlich gewichteten Beiträge; `objective_contributions` die
jeweiligen zugrundeliegenden Terme. Zielfunktionswert und Schranke beziehen sich
auf die in `metrics.objective_phase` genannte Phase. Ohne verfügbaren Qualitätswert
werden beide weggelassen; eine Zulässigkeitsphase mit Zielfunktion null wird nicht
als bewiesenes Qualitätsoptimum ausgegeben.

Der Validator liest Ergebnispaare neu, berechnet Eignung, Zeit, Besetzung,
Fixierungen, Betreuung und Grenzen erneut, und verwendet keine Solver-Wahrheitswerte.
Optionale Ergebnisintervalle müssen exakt zum referenzierten Snapshot passen.
Snapshot-Integrität verwendet SHA-256 des vollständigen kanonischen JSON.
