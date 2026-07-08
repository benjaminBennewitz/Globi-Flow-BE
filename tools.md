#### ##########
### INTRANET: TOOLS & BEFEHLE ###
#### ##########

## VENV aktivieren für Django Interna
cd /home/users/api
source venv/bin/activate


## Server/Backend starten

# Backend-Server (Daphne) - lokal #VENV
daphne -p 8000 config.asgi:application

# Celery Starten (legacy)
python -m celery -A config worker -l info -P solo


#### ##########
### PYTHON / DEPENDENCIES ###
#### ##########

## Abhängigkeiten installieren/aktualisieren #VENV

# Requirements installieren
pip install -r requirements.txt

# Requirements einfrieren/aktualisieren
pip freeze > requirements.txt


#### ##########
### DJANGO: STANDARD-BEFEHLE ###
#### ##########

## Staticfiles

# Statische Dateien sammeln (nur wenn nötig) #VENV
python manage.py collectstatic


## Datenbank / Migrationen #VENV
# Datenbank migrieren (nach jeder Änderung an Models)
# BEI MIGRATIONS VORHER BACKUP!
python manage.py makemigrations
python manage.py migrate

# Backfill der Fingerprints nach Migration #VENV
python manage.py backfill_position_fingerprint

## URLS/Endpunkte anzeigen #VENV
# App installieren
pip install django-extensions

# URLs anzeigen
python manage.py show_urls


#### ##########
### GIT ###
#### ##########

## Git Befehle

# Lokalen Stand hart auf origin/main setzen
git reset --hard origin/main


#### ##########
### TESTS ###
#### ##########

## Curl-Test

# Admin erreichbar?
curl -v http://localhost:8000/admin/


#### ##########
### SYSTEMD (Linux/WSL) ###
#### ##########

## Systemd Service für API

# Service-Datei anlegen/öffnen
nano /etc/systemd/system/...

# Service reload/aktivieren/starten
systemctl daemon-reload
systemctl enable ...
systemctl restart ...

# Status prüfen
systemctl status ...

# Logs der letzten 50 Zeilen
journalctl -u ... -n 50 --no-pager


#### ##########
### DEPLOY ###
#### ##########

## Deploy-Prozess (Server)

# Deployment-Skript ausführen
cd /home/users
chmod +x deploy_GlobiFlow-be.sh
./deploy_GlobiFlow-be.sh


#### ##########
### REDIS / MEMURAI (Windows) ###
#### ##########

## Memurai starten (Windows-Redis)
# Memurai als Dienst starten (Services.msc oder „Memurai Server“ im Startmenü)

## Dienststatus prüfen
sc.exe query memurai


## Redis/Memurai-Konsole testen
# Windows-Konsole öffnen und CLI starten
memurai-cli.exe

# Authentifizieren und Funktion prüfen
AUTH <dein_passwort>
PING
# Erwartet: PONG


## .env.local für Redis/Memurai

# Beispiel-Konfiguration (Werte anpassen)
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=<dein_passwort>
REDIS_USERNAME=default
REDIS_USE_ACL=0
REDIS_CHANNEL_DB=0
REDIS_CACHE_DB=1


## Python/Django Redis-Check

# Beim Django-Start auf folgende Zeile achten:
# [REDIS] HOST= 127.0.0.1 PORT= 6379 REACHABLE= True ...

# Im Fehlerfall prüfen:
# - .env.local
# - Passwort/Benutzer (requirepass in Memurai-Config!)
# - Memurai-Dienst läuft? (siehe sc.exe)


## Netzwerk-Port prüfen
netstat -ano | findstr :6379


## Memurai-Log prüfen

# Logfile:
# C:\Program Files\Memurai\log.txt
# → Fehlermeldungen, Verbindungsabbrüche, Shutdowns etc. nachsehen


#### ##########
### TROUBLESHOOTING ###
#### ##########

## NOAUTH Authentication required
# → Erst AUTH <passwort> im CLI eingeben.

## Timeouts/Verbindungsabbrüche
# → Timeouts in .env.local ggf. erhöhen:
REDIS_SOCKET_CONNECT_TIMEOUT=2.0
REDIS_SOCKET_TIMEOUT=4.0

## Fehler beim Starten von Daphne/Channels #VENV
# → Python-Pakete redis und channels_redis installiert?
pip show redis channels_redis

## Memurai läuft nicht?
# → Dienst über Services oder sc.exe neu starten.


#### ##########
### WSL (nur wenn Redis im WSL läuft, statt Memurai) ###
#### ##########

## Redis-Service prüfen/starten
sudo systemctl status redis-server
sudo systemctl start redis-server

## Ping testen
redis-cli ping
# Erwartet: PONG


#### ##########
### POSTGRESS ###
#### ##########

# wichtigste Befehle
# anmelden
psql -U postgres -d intranet_db

# User anzeigen
\du

# Datenbanken anzeigen
\l

# Tabellen anzeigen
\dt

# Konsole beenden
\q

#### ##########
### HINWEIS ###
#### ##########

# Für Windows-Entwicklung immer Memurai nutzen, nicht den originalen Redis-Server!
# Alle Zugangsdaten/Ports müssen in .env.local übereinstimmen.



## Doku
# tree.txt erstellen, Powershell Skript ausführen
# Powershell öffnen

powershell -NoProfile -ExecutionPolicy Bypass -File .\make-tree.ps1 -Depth 10 -Files -OutFile .\tree.txt