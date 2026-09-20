# Version 0.26.0 – Richtiger Zuschnitt, Bedarf aus der Historie, Ersatz bei Krankmeldung

Diese Freigabe baut auf 0.25.0 auf. Sie ändert keine bestehende Regel, keine
Freigabe und kein gespeichertes Projekt. Alles Neue ist ein zusätzlicher Schritt,
den jemand ausdrücklich auslöst.

## Der Zuschnitt: wer überhaupt geplant wird

In einem großen Haus stehen in derselben Datenbasis Leute, die nicht in diesen
Plan gehören: ein fremder Bereich mit eigenem Plan, das Ehrenamt, längst
ausgeschiedene Personen. Bisher musste jede davon einzeln abgewählt werden – bei
einigen hundert Personen ist das keine ernsthafte Möglichkeit, und deshalb rechnet
das Werkzeug dann eben mit allen.

- Unter **Team & Freigaben → Gruppen von der Planung ausnehmen** nimmt ein Schritt
  eine ganze Gruppe heraus oder wieder auf.
- **Mehrfachmitgliedschaften werden gemeldet, nicht verschwiegen.** Wer noch in
  einer anderen Gruppe steht, wird dabei ebenfalls herausgenommen – die Meldung
  sagt, wie viele das betrifft.
- Die Daten der Personen bleiben unberührt: Verträge, Freigaben, Abwesenheiten,
  alles steht weiter da. Es wird nur nicht eingeteilt.
- Die Zeile darunter sagt jederzeit, wie viele von wie vielen Personen gerade
  eingeplant werden.

## Fehlende Höchstarbeitszeit wird benannt

Ein Regelprofil ohne tägliche und ohne wöchentliche Höchstgrenze plante bisher
kommentarlos bis an die Ruhevorgaben heran – rechnerisch weit über jede
Vereinbarung hinaus. Das Profil weist jetzt darauf hin, solange beide Felder leer
sind, und bietet **12/48** zur Übernahme an: 720 Minuten täglich, 2880 Minuten je
Kalenderwoche.

Das ist ein Angebot, keine rechtliche Prüfung. Wer kürzere Grenzen vereinbart hat,
trägt sie direkt ein. Leer heißt weiterhin ausdrücklich: keine Grenze aus diesem
Profil. Die Übernahme rührt keine andere Regel, keinen Bestätigungsstand und keine
Freigabe an.

## Bedarf aus der Historie: der typische Tag

Für künftige Zeiträume gab es keine brauchbare Bedarfsquelle. Die Bedarfstabelle
der Quelle ist vielerorts nur halb gepflegt, und der beobachtete Plan existiert
naturgemäß nur für Vergangenes.

Neue Bedarfsquelle **„Aus der Historie ableiten (typischer Tag)"**: aus einem
gewählten Fenster wird je Dienst, Arbeitsplatz und Wochentag die typische
Besetzung vergleichbarer Tage übernommen.

- **Tage ohne Dienst zählen mit.** Sonst sähe ein reiner Werktagsdienst wie ein
  Siebentagedienst aus.
- **Unterer Median**, nicht Mittelwert oder Höchstwert: ein Posten, der seltener
  als an der Hälfte der vergleichbaren Tage besetzt war, wird nicht zur Vorgabe.
- **Feiertage werden wie Sonntage besetzt**, behalten aber die Feiertagszeiten der
  Quelle.
- Je Posten und Wochentag stehen **typische, niedrigste und höchste Besetzung**
  sowie die Zahl der verglichenen Tage im Importbericht. Die Ableitung ist damit
  nachvollziehbar und fachlich zu bestätigen, bevor damit geplant wird.
- **Bedarfsfenster und Freigabefenster sind getrennt einstellbar.** Freigaben
  profitieren vom langen Rückblick, ein typischer Tag will einen aktuellen
  Vergleichszeitraum. Ohne Angabe bleibt es beim bisherigen gemeinsamen Fenster.

## Ausbildung und Begleitung

Begleitete Freigaben und Begleitkapazität konnte das Modell längst – gesetzt hat
sie nie jemand, weil es dafür keinen Weg gab. Unter **Team & Freigaben →
Ausbildung und Begleitung** wird jetzt eine Gruppe als Ausbilder gekennzeichnet
und eine Gruppe unter Begleitung gestellt.

Personen ohne jede Freigabe werden dabei ausdrücklich benannt statt stillschweigend
übergangen: unter Begleitung stellen kann man nur, was es gibt. Ohne begleitende
Person im selben Dienst bleibt ein Posten offen und wird als Lücke gemeldet – das
ist gewollt und sichtbar.

## Ersatzsuche bei Krankmeldung

Der häufigste Notfall im Betrieb ist der kurzfristige Krankenstand. Dafür gab es
bisher gar nichts.

Unter **Ihr Dienstplan → Krankmeldung & Ersatzsuche** nennt das Werkzeug zu einer
abwesenden Person und einem Zeitraum je freigewordenem Dienst die Personen, die
einspringen könnten.

- Geprüft wird an **denselben harten Regeln wie die Planung selbst**: Freigabe,
  Beschäftigung, Gruppe, Dienstart, Verfügbarkeit, Abwesenheit, Dienstsperre,
  Ruhezeit und Überschneidung mit eigenen Diensten.
- **Sortiert nach der längsten Wartezeit** seit dem letzten Dienst, damit nicht
  immer dieselben angerufen werden.
- Wer **alle** freigewordenen Dienste übernehmen könnte, wird gesondert genannt.
- Wer nicht kann, **verschwindet nicht, sondern erscheint mit Grund** – gezählt je
  Grund, in Klartext.
- Die Suche **ändert den Plan nicht**. Sie beantwortet eine Frage; eingeteilt wird
  weiterhin von Hand oder durch eine neue Berechnung.

## Ohne Auswirkung auf Bestehendes

Gespeicherte Projekte, laufende Aufträge und Exporte verhalten sich unverändert.
Die neue Bedarfsquelle wird nur benutzt, wenn sie beim Import ausdrücklich gewählt
wird; die Standardquelle bleibt die Bedarfstabelle der Quelle.
