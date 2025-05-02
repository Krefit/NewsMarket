@echo off
cd /d "CAMINHO_DO_SEU_PROJETO"

echo Iniciando coleta de símbolos da B3...
python scripts\coleta_simbolos_b3.py

echo Iniciando coleta de preços diários...
python scripts\coleta_precos_diarios_yfinance.py

echo Iniciando coleta de preços intradiários...
python scripts\coleta_precos_intradiarios_binance.py

echo Iniciando coleta de notícias...
python scripts\coleta_noticias_gnews.py

echo Coletas concluídas.
pause
