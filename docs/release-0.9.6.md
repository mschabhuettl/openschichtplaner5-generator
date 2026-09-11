# Version 0.9.6 – Verlässliche Texte im Excel-Export

Bezeichnungen wie `#REF!`, `#N/A` und `#VALUE!` bleiben im XLSX-Export echte Texte statt Excel-Fehlerzellen. Dies gilt für Monatsplan, Stundenübersicht und Einteilungsdetails. Zahlen bleiben Zahlen; der bisherige Schutz gegen Tabellenformeln bleibt erhalten.

Zelltexte über 32767 Zeichen und in XML nicht darstellbare Steuer- oder Unicode-Zeichen werden vor dem Schreiben der Datei verständlich abgewiesen. Dadurch werden überlange Texte nicht mehr still gekürzt. Vorhandene Exportdateien bleiben bei diesen Eingabefehlern unverändert. Der Hinweis enthält keine persönlichen Quelltexte. In der Weboberfläche wird der Fehler als Eingabehinweis zurückgegeben; für überlange Texte steht weiterhin CSV zur Verfügung. Die Prüfung verändert weder Projekttexte noch Planungsregeln oder persönliche Freigaben.

Die [Zeitlimitprüfung aus 0.9.5](release-0.9.5.md) ist enthalten.

## Prüfumfang

Neun neue Regressionen prüfen gespeicherte und erneut geladene Arbeitsmappen, den unveränderten Zahlenzelltyp, drei abgewiesene Textfälle mit erhaltener Zieldatei, zulässigen Text an der Längengrenze sowie verständliche HTTP-Fehler und den weiterhin möglichen CSV-Export. Sechs Kernregressionen wurden vor der Korrektur als fehlschlagend reproduziert. Der vollständige lokale Python-Lauf nach dem Exportfix bestand mit 349 Tests.

Vor einer Veröffentlichung müssen die vorhandenen [Release-Gates](verification.md) für den endgültigen Commit einschließlich sauberer Paketinstallation, Browser, Container und GHCR-Rückprüfung erfolgreich sein. Ein lokaler Testlauf ersetzt diese Gates nicht.

## Aktualisierung

Vor einem Update Projekte sichern. Nach erfolgreicher Veröffentlichung kann `ghcr.io/mschabhuettl/openschichtplaner5-generator:0.9.6` mit dem bestehenden Zustandsvolume eingesetzt werden. Laufende Installationen werden nicht automatisch verändert.
