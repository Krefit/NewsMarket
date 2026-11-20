@echo off
cd /d %~dp0

echo Iniciando coleta de simbolos da B3...
call .venv\Scripts\activate.bat
python.exe scripts\utils\coleta_historico_b3.py

@REM echo Iniciando coleta de preços diários...
@REM python.exe scripts\coleta_precos_diarios_yfinance.py

@REM echo Iniciando coleta de FIIs...
@REM python.exe scripts\utils\crawler_fii.py

@REM python.exe scripts\utils\consulta.py

@REM echo Iniciando coleta de notícias...
@REM python.exe scripts\utils\coleta_noticias_b3.py

echo Coletas concluídas.
pause


