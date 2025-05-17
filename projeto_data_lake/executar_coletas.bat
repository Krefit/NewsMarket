@echo off
cd /d %~dp0

@REM echo Iniciando coleta de símbolos da B3...
@REM call .venv\Scripts\activate.bat
@REM python.exe scripts\coleta_simbolos_b3.py

echo Iniciando coleta de preços diários...
python.exe scripts\coleta_precos_diarios_yfinance.py

@REM echo Iniciando coleta de preços intradiários...
@REM python.exe scripts\coleta_precos_intradiarios_binance.py

@REM echo Iniciando coleta de notícias...
@REM python.exe scripts\coleta_noticias_gnews.py

echo Coletas concluídas.
pause
