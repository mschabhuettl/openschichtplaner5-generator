# Version 0.9.24 – Zeitregel vor der Übernahme prüfen

Die vorhandene Tag-/Nacht-Automatik zeigt jetzt vor der Sammelübernahme eine
Vorschau: offene Dienstvorkommen als Tag, als Nacht und ohne Vorschlag.
Je Dienstzeitmuster sind Uhrzeiten, offene Vorkommen und Minuten im gewählten
Nachtfenster sichtbar. Die Vorschlagsliste ist suchbar und seitenweise lesbar.

Das Bearbeiten der Vorschlagsregel und das Anzeigen der Vorschau ändern
weder Projektstand noch Dienstarten. Erst „Geprüfte Zeitregel-Vorschläge
übernehmen“ stellt die zuordenbaren offenen Vorkommen ein und speichert die
gewählte Zeitregel. Bereits festgelegte Dienstarten bleiben erhalten.

Ein anderes Nachtfenster oder eine andere Mindestdauer entfernt die alte
Übernahmeaktion. Wurde das Projekt seit der Vorschau bearbeitet, muss eine
neue Vorschau erstellt werden. Ohne auswertbare Vorschläge gibt es keine
Übernahmeaktion. Nicht zuordenbare Vorkommen bleiben ausdrücklich offen.

Die Zeitregel ist eine fachlich zu prüfende Vorschlagsregel, keine gesetzliche
Vorgabe. Persönliche Freigaben, Regelprofile, Bedarfe und offene Importhinweise
werden dadurch nicht bestätigt oder verändert. Die bestehende Behandlung
geteilter Dienste und angrenzender Zeiträume bleibt unverändert.

## Prüfungen

Synthetische Tests prüfen Zählungen einschließlich nicht zuordenbarer Dienste,
unveränderte bestätigte Dienstarten, ungültige Einstellungen und rein lesende
Vorschauen. Der vollständige Desktop-/Mobilablauf prüft zusätzlich veraltete
Vorschauen, gezielte Übernahme und den unveränderten restlichen Projektinhalt.
Das Formular passt auch auf schmale Bildschirme; die Tabelle kann innerhalb
ihres Bereichs gescrollt werden.

Veröffentlichung erst nach erfolgreichen [Release-Gates](verification.md).
Benutzerinstallationen bleiben unverändert.
