@echo off
cd /d "%~dp0"

echo ==========================================
echo   Sistema de Jiu-Jitsu - Iniciando...
echo ==========================================
echo.
echo Pasta atual: %CD%
echo.

REM Verificar Python
python --version
if errorlevel 1 (
    echo.
    echo ERRO: Python nao encontrado!
    echo Instale em: https://www.python.org/downloads/
    echo (Marque "Add Python to PATH" durante a instalacao)
    pause
    exit /b 1
)

echo.
echo Instalando dependencias (aguarde)...
python -m pip install flask flask-sqlalchemy flask-login werkzeug
if errorlevel 1 (
    echo.
    echo ERRO ao instalar dependencias!
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Dependencias instaladas com sucesso!
echo ==========================================
echo.
echo Iniciando servidor...
echo Acesse: http://localhost:5000
echo Admin:  usuario=admin  senha=admin123
echo.
echo Para parar: pressione CTRL+C
echo.
python app.py
pause
