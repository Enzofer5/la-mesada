@echo off
REM Instalación en Windows: crea el entorno virtual e instala las dependencias.
cd /d "%~dp0"
python -m venv venv || goto error
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto error
if not exist .env copy .env.example .env
echo.
echo Listo. Ahora:
echo   1) Edita el archivo .env con los datos de tu MySQL.
echo   2) Ejecuta:  venv\Scripts\activate  y luego  flask --app run init-db
echo   3) (Opcional) datos de prueba:  flask --app run seed-demo
echo   4) Inicia con iniciar_windows.bat
pause
exit /b 0
:error
echo Hubo un error. Verifica que Python 3.10 o superior este instalado y en el PATH.
pause
exit /b 1
