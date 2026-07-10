# Globi Flow Backend

> Lokales Django-Backend für die strukturierte Verarbeitung, Prüfung und verständliche Aufbereitung künstlicher Laborbefunde.

**Projektart:** Lernprojekt · Demo-Anwendung · technische Case Study  
**Entwicklertag:** B² Benjamin Bennewitz  
**Frontend:** [Globi Flow Frontend](https://github.com/benjaminBennewitz/Globi-Flow.git)

---

## Projektüberblick

Globi Flow ist ein lokales Laborwerte-Assistenzsystem mit getrennten Arbeitsbereichen für Import, ärztliche Prüfung, Wissenspflege und Patientenbericht. Dieses Repository stellt die REST-API, Datenhaltung und lokale Verarbeitungsstrecke für das zugehörige Angular-Frontend bereit.

Das Backend dient als technische Case Study für:

- modular aufgebaute Django- und Django-REST-Framework-Anwendungen,
- normalisierte Datenmodelle für Laborbefunde und Laborwerte,
- lokale PDF-Textanalyse und OCR-Verarbeitung,
- asynchrone Importjobs mit Celery und Redis,
- kontrollierte Wissensinhalte statt frei erzeugter medizinischer Aussagen,
- lokale Übersetzung von Patientenberichten,
- nachvollziehbare Review-, Freigabe- und Reportabläufe,
- sichere Verarbeitung ausschließlich künstlicher Testdaten.

Globi Flow stellt keine Diagnosen. Medizinische Bewertung, Korrektur und Freigabe verbleiben immer bei einer fachlich zuständigen Person.

---

## Systemverbund

| Bestandteil | Repository | Aufgabe |
|---|---|---|
| Frontend | [Globi Flow](https://github.com/benjaminBennewitz/Globi-Flow.git) | Angular-Oberfläche für Import, Review, Dashboard, Wissensbasis und Patientenbericht |
| Backend | Dieses Repository | REST-API, PostgreSQL-Datenhaltung, lokale Analyse, OCR, Übersetzung und Hintergrundjobs |

Das Frontend greift lokal standardmäßig über `http://127.0.0.1:8000/api/` auf die Backend-Endpunkte zu.

---

## Technologie-Stack

| Bereich | Technologie |
|---|---|
| Backend | Python, Django 5.2, Django REST Framework |
| API-Betrieb | Daphne, ASGI |
| Datenbank | PostgreSQL mit Psycopg |
| Hintergrundjobs | Celery |
| Broker und Cache | Redis oder Memurai unter Windows |
| PDF-Textanalyse | pypdf |
| PDF-Bildkonvertierung | pdf2image und lokal installiertes Poppler |
| OCR | pytesseract und lokal installiertes Tesseract OCR |
| Lokale Übersetzung | Argos Translate |
| Tests | pytest, pytest-django |
| Qualität | Ruff |

Alle fachlichen Verarbeitungswege sind für einen lokalen Betrieb ohne externe OCR-, Übersetzungs- oder Analyse-API ausgelegt.

---

## Kernfunktionen

### Import und Analyse

- Upload künstlicher PDF-Laborbefunde
- Prüfung von Dateigröße, Dateityp und PDF-Signatur
- optionale lokale Malware-Prüfung über ClamAV
- Extraktion vorhandener PDF-Textschichten
- lokaler OCR-Fallback für gescannte oder bildbasierte PDFs
- Erkennung von Laborwert, Ergebnis, Einheit und Referenzbereich
- Normalisierung erkannter Werte
- Confidence Score für unsichere Extraktionen
- Erstellung von Review-Kandidaten
- synchroner oder asynchroner Importworkflow

### Laborwerte und Review

- Verwaltung künstlicher Testpersonen und Laborbefunde
- strukturierte Speicherung von Laborwerten und Referenzbereichen
- Reviewstatus für automatisch erkannte Werte
- Korrektur und Freigabe durch den vorgesehenen Prüfworkflow
- Verlaufsauswertung über mehrere Befunde
- aggregierte Daten für Dashboard und Analyseansicht

### Wissensbasis und Berichte

- kontrollierte Wissenseinträge mit Quellen und Versionen
- getrennte Inhalte für Arztansicht und Patientenerklärung
- Freigabe- und Statusworkflow für Wissensinhalte
- serverseitig aufgebautes Berichtstemplate
- lokale Übersetzung unterstützter Berichtsinhalte
- Report-Vorschau für das Angular-Frontend
- medizinischer Disclaimer in der Patientenansicht

---

## Projektstruktur

```text
config/          Django-Konfiguration, URLs, Celery, ASGI und WSGI
apps/core/       Healthcheck, Sicherheitsfunktionen und gemeinsame Hilfen
apps/patients/   Testpersonen und Stammdaten
apps/labs/       Befunde, Laborwerte, Referenzbereiche und Review
apps/imports/    Upload, Importjobs, PDF-Analyse und lokale OCR-Pipeline
apps/knowledge/  Kontrollierte Wissensbasis mit Quellen und Versionen
apps/reports/    Patientenberichte, Templates und lokale Übersetzung
apps/dashboard/  Aggregierte API-Daten für das Angular-Frontend
scripts/         Lokale Start- und Hilfsskripte
tools.md         Projektbezogene Entwicklungs- und Betriebsbefehle
```

---

## Lokale Einrichtung unter Windows

### Voraussetzungen

- Python in einer zum Projekt passenden Version
- PostgreSQL
- Redis oder Memurai
- Tesseract OCR
- Poppler

### Virtuelle Umgebung und Abhängigkeiten

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Wenn `(.venv)` bereits in der Konsole angezeigt wird, ist die virtuelle Umgebung aktiv und muss nicht erneut erstellt werden.

### PostgreSQL vorbereiten

Die folgenden Befehle werden in `psql` oder im Query Tool von pgAdmin ausgeführt:

```sql
CREATE USER globi_flow_admin WITH PASSWORD 'DEIN_LOKALES_PASSWORT';
CREATE DATABASE globi_flow_db OWNER globi_flow_admin ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE globi_flow_db TO globi_flow_admin;
```

Lokale Zugangsdaten gehören ausschließlich in die nicht zu veröffentlichende Umgebungsdatei. Beispielwerte in der Dokumentation sind keine Empfehlung für produktive Passwörter.

### Migrationen und Demodaten

```powershell
python manage.py migrate
python manage.py seed_demo_data --reset
python manage.py check
```

### Backend starten

Entwicklungsserver:

```powershell
python manage.py runserver
```

ASGI-Server mit Daphne:

```powershell
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Falls der globale Script-Aufruf unter Windows nicht gefunden wird:

```powershell
.venv\Scripts\daphne.exe -b 127.0.0.1 -p 8000 config.asgi:application
```

---

## Redis und Celery

Celery verarbeitet Importjobs außerhalb des Webprozesses. Der Broker und das Result Backend werden über Redis beziehungsweise Memurai bereitgestellt.

Celery Worker unter Windows starten:

```powershell
python -m celery -A config worker --loglevel=info --pool=solo --queues=globi_imports
```

Alternativ kann das vorhandene Startskript verwendet werden:

```powershell
scripts\start_celery_windows.bat
```

Für eine rein synchrone lokale Entwicklung kann Celery über die Umgebungsvariable deaktiviert werden:

```env
GLOBI_USE_CELERY=False
```

Bei aktiviertem Celery müssen Redis oder Memurai und der Worker vor dem Start eines Importjobs erreichbar sein.

---

## Lokale OCR-Verarbeitung

Für PDFs ohne verwertbare Textschicht verwendet Globi Flow eine lokale OCR-Kette:

1. PDF-Seiten mit Poppler in Bilder umwandeln.
2. Bilder mit Tesseract OCR auslesen.
3. erkannte Zeilen normalisieren und fachlichen Laborwerten zuordnen.
4. Ergebnis, Einheit, Referenzbereich und Confidence speichern.
5. unsichere Werte für die manuelle Prüfung markieren.

Empfohlene lokale Windows-Pfade:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
C:\Tools\poppler\Library\bin
```

Relevante Umgebungsvariablen:

```env
OCR_ENABLED=True
OCR_LANGUAGES=deu+eng
OCR_DPI=300
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
POPPLER_PATH=C:\Tools\poppler\Library\bin
```

Installation prüfen:

```powershell
tesseract --version
pdftoppm -h
```

Tesseract und Poppler sind lokale Systemabhängigkeiten und werden nicht mit diesem Repository ausgeliefert.

---

## Lokale Übersetzung

Die Übersetzung des Patientenberichts erfolgt lokal über Argos Translate. Statische Reporttexte werden serverseitig kontrolliert aufgebaut; Übersetzungsergebnisse werden nicht als medizinische Diagnose oder automatisch freigegebener Fachinhalt behandelt.

Die aktivierten Zielsprachen und das Glossar werden über die Backend-Konfiguration gesteuert:

```env
GLOBI_TRANSLATION_ENABLED=True
GLOBI_TRANSLATION_SOURCE_LANGUAGE=de
GLOBI_TRANSLATION_LANGUAGES=en,fr,es,tr
```

Benötigte Sprachmodelle müssen lokal installiert sein. Es werden keine Texte an externe Übersetzungsdienste übertragen.

---

## Importworkflow

```text
Testdaten-PDF
    ↓
Upload und Sicherheitsprüfung
    ↓
PDF-Textschicht oder lokale OCR
    ↓
Extraktion und Normalisierung
    ↓
Confidence-Bewertung
    ↓
Review und Korrektur
    ↓
Freigabe des Befunds
    ↓
Dashboard und Patientenbericht
```

---

## Wichtige API-Bereiche

| Bereich | Beispielpfade |
|---|---|
| System | `/api/health/`, `/api/demo-reset/` |
| Dashboard | `/api/dashboard/`, `/api/overview/`, `/api/auswertung/` |
| Patienten | `/api/patients/` |
| Import | `/api/imports/jobs/`, `/api/imports/upload/`, `/api/imports/demo/` |
| Review | `/api/imports/review/` |
| Wissensbasis | `/api/knowledge/`, `/api/knowledge/<laborwert_key>/` |
| Befundfreigabe | `/api/lab-reports/<report_id>/release/` |
| Berichte | `/api/reports/preview/`, `/api/reports/patient-preview/` |

Die Presenter und API-Views liefern für das Angular-Frontend aufbereitete camelCase-Strukturen.

---

## Tests und Qualitätsprüfung

```powershell
pytest
python manage.py check
ruff check .
```

Gezielte Testmodule können beispielsweise so ausgeführt werden:

```powershell
pytest apps/imports/tests_security.py
pytest apps/reports/tests_translation.py
```

---

## Sicherheits- und Datenschutzgrenzen

Dieses Repository ist ein nicht-kommerzielles Lern-, Demo- und Portfolio-Projekt.

- Es dürfen ausschließlich künstliche, anonymisierte Testdaten verwendet werden.
- Echte Patienten-, Gesundheits- oder Identitätsdaten sind nicht für dieses Projekt vorgesehen.
- Die Anwendung ist nicht als Medizinprodukt zertifiziert.
- Die Anwendung ist nicht für Diagnose, Therapieentscheidung oder Notfallbewertung bestimmt.
- Die vorhandenen Sicherheitsmaßnahmen stellen keine Garantie für vollständige Sicherheit dar.
- Eine produktive Nutzung erfordert eine eigenständige fachliche, rechtliche, datenschutzrechtliche und technische Prüfung.
- OCR-, Parser- und Übersetzungsergebnisse können unvollständig oder fehlerhaft sein und müssen geprüft werden.
- Externe Systemprogramme und Sprachmodelle unterliegen ihren jeweiligen eigenen Lizenzen.

Die Software wird ohne Zusicherung einer bestimmten Eignung, Fehlerfreiheit oder Verfügbarkeit bereitgestellt. Maßgeblich sind die Nutzungs- und Haftungshinweise dieses Projekts.

---

## Autor

**B² Benjamin Bennewitz**  
Webentwicklung · Full Stack · Grafikdesign
