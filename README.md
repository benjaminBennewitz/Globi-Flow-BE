# Globi-Flow-BE

Lokales Django/DRF-Backend für **Globi Flow**. Das Backend ist schlank gehalten, nutzt PostgreSQL und verarbeitet Dateiimport, PDF-Textanalyse und optional lokale OCR ohne externe Cloud-Services.

## Struktur

```txt
config/          Django-Konfiguration, URLs, Celery, ASGI/WSGI
apps/core/      Healthcheck, Seed-Command, Hilfsfunktionen
apps/patients/  Testpersonen und Stammdaten
apps/labs/      Befunde, Laborwerte, Referenzbereiche, Review
apps/imports/   Upload, Importjob, lokale PDF-/OCR-Pipeline
apps/knowledge/ Kontrollierte Wissensbasis mit Quellen und Versionen
apps/reports/   Patientenberichte und Report-Vorschau
apps/dashboard/ Aggregierte API-Views für das Angular-Frontend
```

## Datenbank

Die Tabellen werden durch Django-Migrationen erstellt. Die PostgreSQL-Datenbank und der Benutzer müssen vorher einmal existieren.

Standardwerte aus `.env.local`:

```txt
DB_NAME=globi_flow_db
DB_USER=globi_flow_admin
DB_PASSWORD=123456
DB_HOST=localhost
DB_PORT=5432
```

### Datenbank per psql anlegen

Diese Befehle gehören nicht in `cmd`, sondern in `psql` oder in das Query Tool von pgAdmin.

```sql
CREATE USER globi_flow_admin WITH PASSWORD '123456';
CREATE DATABASE globi_flow_db OWNER globi_flow_admin ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE globi_flow_db TO globi_flow_admin;
```

Falls der User schon existiert:

```sql
ALTER USER globi_flow_admin WITH PASSWORD '123456';
CREATE DATABASE globi_flow_db OWNER globi_flow_admin ENCODING 'UTF8';
```

Falls die Datenbank schon existiert:

```sql
ALTER DATABASE globi_flow_db OWNER TO globi_flow_admin;
GRANT ALL PRIVILEGES ON DATABASE globi_flow_db TO globi_flow_admin;
```

## Lokaler Start ohne Docker

```bash
cd C:\Users\Werbung06\Desktop\Globi-Flow-BE
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data --reset
python manage.py runserver
```

Wenn `(.venv)` bereits links in der Konsole steht, ist die virtuelle Umgebung schon aktiv. Dann `python -m venv .venv` nicht erneut ausführen.

Wenn die virtuelle Umgebung beschädigt ist:

```bash
deactivate
rmdir /s /q .venv
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Lokale Verarbeitung

Die Importpipeline arbeitet lokal:

1. Dateigröße und PDF-Signatur prüfen.
2. PDF-Textschicht lokal mit `pypdf` extrahieren.
3. Falls keine verwertbare Textschicht vorhanden ist, optional lokale OCR über `pdf2image` und `pytesseract` nutzen.
4. Laborwert-Zeilen über Alias-Liste und Regex erkennen.
5. Einheit, Referenzbereich, Confidence und Reviewstatus normalisieren.
6. Importjob, Befund, Laborwerte und Review-Kandidaten speichern.

Celery ist vorbereitet, aber in `.env.local` standardmäßig deaktiviert. Für den schlanken lokalen Start läuft die Analyse synchron.

Zusätzlich unterstützt die Pipeline:

- lokale PDF-Textanalyse für optimierte Laborbefunde
- lokalen OCR-Fallback über Tesseract für gescannte oder bildbasierte PDFs
- lokale PDF-Bildkonvertierung über Poppler

## Lokale OCR-Abhängigkeiten

Globi Flow verarbeitet PDF-Dateien vollständig lokal. Für bildbasierte oder gescannte Laborbefunde wird ein lokaler OCR-Fallback verwendet.

Benötigte Systemprogramme:

- Tesseract OCR
- Poppler

Tesseract wird nicht mit dem Repository ausgeliefert und muss lokal installiert werden. Für deutsche und englische Laborbefunde sollten mindestens die Sprachdaten `deu` und `eng` installiert sein.

Empfohlene Windows-Pfade:

```txt
C:\Program Files\Tesseract-OCR\tesseract.exe
C:\Tools\poppler\Library\bin
```

Die lokale `.env.local` sollte folgende Werte enthalten:

```env
OCR_ENABLED=True
OCR_LANGUAGES=deu+eng
OCR_DPI=300
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
POPPLER_PATH=C:\Tools\poppler\Library\bin
```

Installation prüfen:

```bash
tesseract --version
pdftoppm -h
```

Backend danach neu starten:

```bash
python manage.py check
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Hinweis: Tesseract OCR wird als externe lokale Systemabhängigkeit genutzt und nicht in dieses Repository kopiert. Tesseract OCR steht unter der Apache License 2.0.

## API-Endpunkte

```txt
GET  /api/health/
GET  /api/dashboard/
GET  /api/overview/
GET  /api/auswertung/
GET  /api/patients/
POST /api/patients/
GET  /api/imports/jobs/
POST /api/imports/upload/
POST /api/imports/demo/
GET  /api/imports/review/
PATCH /api/imports/review/<review_id>/
GET  /api/knowledge/
POST /api/knowledge/
GET  /api/knowledge/<laborwert_key>/
PATCH /api/knowledge/<laborwert_key>/
DELETE /api/knowledge/<laborwert_key>/
POST /api/lab-reports/<report_id>/release/
POST /api/lab-reports/release/
GET  /api/reports/preview/
GET  /api/reports/patient-preview/
```

Die View-Endpunkte liefern camelCase-Daten für das vorhandene Angular-Frontend.

## Frontend-Patch

Der Frontend-Patch liegt als eigenes ZIP vor. Nach dem Backend-Start werden die Dateien in das Angular-Projekt kopiert. Erst wenn die API-Daten korrekt angezeigt werden, kann `src/app/core/mocks/` entfernt werden.

## Medizinischer Hinweis

Das Backend strukturiert, prüft und bereitet Laborwerte auf. Es stellt keine Diagnosen und ersetzt keine ärztliche Prüfung.

## Lokaler Start ohne Docker

PostgreSQL muss lokal laufen. Die SQL-Befehle werden in pgAdmin oder `psql` ausgeführt, nicht direkt in CMD.

```sql
CREATE USER globi_flow_admin WITH PASSWORD '123456';
CREATE DATABASE globi_flow_db OWNER globi_flow_admin ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE globi_flow_db TO globi_flow_admin;
```

Wenn der User bereits existiert:

```sql
ALTER USER globi_flow_admin WITH PASSWORD '123456';
```

Danach im Backend-Ordner:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data --reset
python manage.py runserver
```

## Start mit Daphne

Daphne ist in `requirements.txt` enthalten. Für den lokalen ASGI-Start:

```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Falls Windows den Script-Namen nicht findet:

```bash
.venv\Scripts\daphne.exe -b 127.0.0.1 -p 8000 config.asgi:application
```

## Frontend-Anbindung

Das Frontend ruft lokal direkt `http://127.0.0.1:8000/api/...` auf. Dadurch ist kein Angular-Proxy nötig und `localhost:4300/api/...` liefert nicht versehentlich die Angular-`index.html` zurück.
