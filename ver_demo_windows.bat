@echo off
REM ============================================================
REM  La Mesada - DEMO rapida (no necesita MySQL: usa SQLite)
REM  Doble clic y se abre en el navegador: http://localhost:8000
REM ============================================================
cd /d "%~dp0"
title La Mesada - Demo
REM Si quedo abierta una version anterior, se cierra para usar la nueva
taskkill /f /im waitress-serve.exe >nul 2>nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /f /pid %%p >nul 2>nul
set PY=python
where py >nul 2>nul && set PY=py -3
REM Si la carpeta se movio de lugar, el entorno de Python viejo no sirve: se vuelve a crear
if exist venv\pyvenv.cfg (
  findstr /i /c:"%~dp0venv" venv\pyvenv.cfg >nul || (echo La carpeta cambio de lugar: se rearma el entorno de Python... & rmdir /s /q venv)
)
if not exist venv\Scripts\activate.bat (
  echo Creando entorno de Python...
  %PY% -m venv venv || goto error
)
call venv\Scripts\activate.bat
echo Instalando dependencias (solo tarda la primera vez)...
python -m pip install -q --disable-pip-version-check -r requirements.txt || goto error
REM La base de demo va fuera de OneDrive (OneDrive bloquea los archivos de SQLite mientras sincroniza)
set DBDIR=%LOCALAPPDATA%\LaMesada
if not exist "%DBDIR%" mkdir "%DBDIR%"
set DBPATH=%DBDIR:\=/%
set DATABASE_URL=sqlite:///%DBPATH%/demo_lamesada_v5.db
set SECRET_KEY=demo-local-lamesada
REM init-db crea las tablas que falten y agrega columnas nuevas sin borrar datos
python -m flask --app run init-db || goto error
if not exist "%DBDIR%\demo_cargada_v5.txt" (
  echo Cargando datos de demostracion ficticios...
  python -m flask --app run seed-demo || goto error
  echo ok> "%DBDIR%\demo_cargada_v5.txt"
)
echo.
echo  La Mesada esta funcionando en http://localhost:8000
echo  Usuario: propietario@lamesada.com   Clave: LaMesada2026
echo  (cerra esta ventana para detenerla)
echo.
start "" http://localhost:8000
python -m waitress --host=127.0.0.1 --port=8000 --call run:crear
pause
exit /b 0
:error
echo.
echo Hubo un error. Verifica que Python 3.10 o superior este instalado (python.org).
pause
exit /b 1
