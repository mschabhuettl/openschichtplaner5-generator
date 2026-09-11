# Version 0.9.29 – 11/36-Ruhevorgaben und weiche Dienstblöcke

- Neue SP5-Importe schlagen 11 Stunden tägliche Ruhe (660 Minuten) und
  36 Stunden zusammenhängende Ruhe je Kalenderwoche (2160 Minuten) vor.
  Tägliche Ruhe ist enthalten, nicht zusätzlich 36 + 11 Stunden.
  Importprofil, Randkontext und persönliche Freigaben bleiben unbestätigt.
- In bestehenden Profilen können genau diese vier Ruhefelder bewusst
  übernommen werden. Andere Regeln, Gültigkeit und Bestätigungsstand werden
  nicht angefasst. Keine neuen maximalen Blocklängen werden eingeführt.
- Neues weiches Ziel: weniger Arbeits-/Freizeitwechsel fördern Dienstblöcke
  und zusammenhängende freie Tage. Bestehende lokale Arbeitstagsvariablen
  berücksichtigen Übernacht-Dienste sowie fixierte Randdienste.
- Neue Importe und Projektanlagen starten mit Gewicht 100. Alte Projekte
  ohne das neue Feld behalten Gewicht 0; Aktivierung bleibt ausdrücklich.
  Harte Grenzen und persönliche Freigaben werden nicht gelockert.
- Eine [verbundene Quellenanalyse](source-semantics.md) belegt CALCBASE,
  Sollbuchungsgrenzen, Ist/Soll, Teamfilter und die Trennung von Historie
  und persönlicher Freigabe anhand gepinnter Original-Commits.

Die Kalenderwochenregel ist keine rollierende Siebentageregel und schneidet
freie Intervalle an der Wochengrenze ab. Randkontext muss vollständig sein.
Das Blockziel maximiert nicht exakt die längste Freizeit in Minuten:
OPTIMAL betrifft die gesamte gewichtete Bewertung; FEASIBLE garantiert
keine Maximalität. [Regel- und Zielsemantik](rules.md).

Geprüft mit synthetischen Regressionen: harte Freigaben/Höchsttage bleiben
trotz Blockziel wirksam; durchgehende Blöcke bei nachgewiesenem OPTIMAL;
Übernacht-Dienste und beide Periodenränder; genau 36 Stunden einschließlich
Tagesruhe; unveränderte alte Profile; explizite Übernahme im Desktop-/Mobil-
Browser ohne automatische Bestätigung oder Freigabe. Separat private
API-Abnahme mit unveränderten fachlichen Blockern, niemals mit erfundenen
Freigaben. Veröffentlichung nach den [Release-Gates](verification.md).
