@echo off
setlocal
call .venv\Scripts\activate.bat
celery -A config worker --loglevel=INFO --pool=solo --queues=globi_imports
endlocal
