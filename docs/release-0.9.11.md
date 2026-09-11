# Version 0.9.11 – Sollstundenherkunft sichtbar

Die Personenbearbeitung erklärt das Soll als Stunden für den gesamten
Planungszeitraum, getrennt von maximalen Wochenstunden. Neue SP5-Importe
speichern zusätzlich die verwendete Quellenbasis und den ursprünglichen
berechneten Wert als Herkunftsnachweis. Er steht direkt am Sollstundenfeld,
auch für assistive Technik über dessen Beschreibung erreichbar.

Bei Monatsbasis wird ausdrücklich „Stunden je Monat“ angezeigt. Der
berechnete Importwert kann für einen Teilmonat anders ausfallen. Eine spätere
manuelle Solländerung überschreibt die Herkunft nicht. Fehlende Herkunft
in älteren Projekten wird nicht erraten; Sollbuchungen bleiben ausdrücklich
zur gesonderten Prüfung offen.

Die bestehende Quellenberechnung wird unverändert weiterverwendet.
Siehe [Quellsemantik und Beispiele](nominal-hours.md).
Persönliche Freigaben, Regelgrenzen und Benutzerinstallationen bleiben unverändert.

## Prüfungen

Sechs synthetische Importfälle unterscheiden Tages-, Wochen-, Monats- und
Gesamtbasis, Teilperioden und zwei ganze Monate. Der Browser prüft den
Monatsbasis-Hinweis, das tatsächlich berechnete Wochenausschnitt-Soll,
unveränderte Herkunft nach manueller Bearbeitung, die zugängliche
Feldbeschreibung und Desktop/Mobil ohne horizontalen Seitenüberlauf.
Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Die [UI-Verbesserungen aus 0.9.10](release-0.9.10.md) sind enthalten.
