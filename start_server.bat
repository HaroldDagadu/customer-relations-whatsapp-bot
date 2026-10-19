@echo off
echo Starting WhatsApp Backend Server...
echo Hot reloading enabled (excluding database files to prevent lag)
uvicorn webhook_server:app --reload --reload-exclude "whatsapp.db" --reload-exclude "whatsapp.db-journal" --reload-exclude "whatsapp.db-wal" --reload-exclude "whatsapp.db-shm"
pause
