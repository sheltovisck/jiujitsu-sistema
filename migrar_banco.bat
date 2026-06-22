@echo off
cd /d "%~dp0"
echo Executando migracao do banco de dados...
python migrar_banco.py
