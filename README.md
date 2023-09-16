# SP5ToICalExp

## Überblick

SP5ToICalExp ist eine leistungsstarke Webanwendung zur Konvertierung von Schichtplänen im PDF-Format aus dem Schichtplaner 5 in iCal-Dateien (`.ics`). Neben der Schichtkonvertierung bietet das Tool auch Namenserkennung und umfassende Schichtstatistiken.

## Technologie-Stack

- Python
- Flask
- Regular Expressions (für Textextraktion)
- iCal (für Kalenderdaten)
- HTML, CSS (Bootstrap) (für die Benutzeroberfläche)
- Werkzeug (für sicheren Datei-Upload)

## Installation

```bash
# Repository klonen
git clone https://github.com/mschabhuettl/SP5ToICalExp.git

# In das Verzeichnis wechseln
cd SP5ToICalExp

# Abhängigkeiten installieren
pip install -r requirements.txt

# App starten
python main.py
```

Navigieren Sie nach dem Start zur Adresse `http://127.0.0.1:5000`, um die Anwendung zu verwenden.

## Neue Features

- **Automatische Namenserfassung**: Extrahiert den Namen direkt aus dem hochgeladenen Schichtplan.
- **Optimierte Textverarbeitung**: Erweiterte Regular Expressions für präzisere und zuverlässigere Textextraktion.
- **Detaillierte Schichtstatistiken**: Ermöglicht dem Benutzer, einen detaillierten Überblick über verschiedene Schichtarten zu erhalten.

## Verwendung

1. **Datei hochladen**: Über die Benutzeroberfläche können Sie Ihre Schichtplan-PDF hochladen.
2. **Daten validieren**: Nach dem Upload können Sie die extrahierten Schichten und den erfassten Namen überprüfen.
3. **Statistiken betrachten**: Verschaffen Sie sich einen Überblick über Ihre Schichten durch die aggregierten Statistiken.
4. **iCal herunterladen**: Klicken Sie auf den Button, um Ihre extrahierten Schichten im iCal-Format zu speichern.

## Häufig gestellte Fragen (FAQ)

**Q: Welche Schichtpläne werden unterstützt?**

A: SP5ToICalExp ist optimiert für Schichtplaner 5-PDFs. Die Effizienz kann je nach Formatierung und Struktur der Datei variieren.

**Q: Ist die Nutzung des Tools kostenpflichtig?**

A: Nein, dieses Tool ist kostenlos und Open Source.

## Beiträge

Wir freuen uns über Beiträge, Fehlerberichte und Vorschläge zur Verbesserung des Tools. Bitte eröffnen Sie ein GitHub-Issue oder senden Sie einen Pull Request.

## Lizenz

Dieses Projekt ist unter der BSD 3-clause "New" or "Revised" License lizenziert. Weitere Informationen finden Sie in der [LICENSE](LICENSE) Datei.

## Kontakt

Bei Fragen oder Anmerkungen kontaktieren Sie mich bitte über GitHub.
