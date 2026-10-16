@echo off
REM Inicia La Mesada en http://localhost:8000 (accesible desde otros equipos de la red con la IP de esta PC).
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo La Mesada funcionando en http://localhost:8000  (Ctrl+C para detener)
waitress-serve --host=0.0.0.0 --port=8000 --call run:crear
pause
