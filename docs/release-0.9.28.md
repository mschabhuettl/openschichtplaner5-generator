# Version 0.9.28 – Ein gemeinsamer Planungsarbeitsplatz

Die zentrale Strecke vom Import über Einrichtung und Berechnung bis zum
Dienstplan erhält ein zusammenhängendes Designsystem: klare Typografie,
einheitliche Abstände, neutrale Datenflächen und blaue Aktionsfarben.
Alle Styles bleiben lokal; keine externen Schrift-, CDN- oder UI-Dienste.

- Direkter Einstieg „SP5 importieren“ neben der Projektanlage, auch per Tastatur
  mit Fokus auf der tatsächlichen Datenquellenauswahl.
- Import in zwei sichtbaren Schritten: Quelle/Teams und Zeitraum/Vergleich.
  Historie, Folgezeitraum und Einrichtungsautomatik sind gesondert aufklappbar.
- Berechnung mit kompaktem Projektkontext, Planungsgrundlage, Vorprüfung und
  ausdrücklichem Berechnungsstart. Zusätzliche Kennzahlen und Ablaufhilfe
  werden bei Bedarf aufgeklappt. Prüfstatus bleibt sichtbar.
- Lesbarer Dienstplan mit kompakteren Leerzeilen, einheitlichen Tabellen und
  unterscheidbaren Tages-/Nachtdiensten; Scrollen und fixierte Personen bleiben.
- Sichtbare Navigationsbeschriftungen auch am Tablet; mobile Formulare,
  Tastaturbedienung und Fokusführung bleiben Bestandteil der Browserprüfung.

Keine Regel, Bestätigung, Freigabe oder Datenquellensemantik wird geändert.
Aufklappen und Navigation übernehmen keine Einstellungen. Ein technischer
Jobabschluss ist weiterhin kein Nachweis eines gültigen Dienstplans.

Vor der Umsetzung wurden die vorhandenen Komponenten sowie
[Pico CSS](https://picocss.com/docs) und
[Bootstrap Accordions](https://getbootstrap.com/docs/5.3/components/accordion/)
geprüft. Die vorhandenen nativen HTML-Aufklapper und lokalen Styles decken
hier den Bedarf; eine Frameworkmigration würde bestehende Interaktionen
unnötig ersetzen.

Synthetische Vorher-/Nachher-Aufnahmen zeigen denselben Import-, Berechnungs-
und Dienstplanablauf auf Desktop und Mobilgerät. Die Browserregression prüft
zusätzlich den Import-Einstieg per Tastatur, unveränderte automatische Freigaben
und sichtbare Navigation bei 320, 768 und 1024 Pixeln. Keine Behauptung einer
vollständigen Barrierefreiheitszertifizierung.

Veröffentlichung nach den [Release-Gates](verification.md). Private API-Abnahme
bleibt separat erforderlich; synthetische Tests ersetzen keine fachlich
bestätigte Einrichtung. Die Benutzerinstallation wird nicht verändert.
