@echo off
REM Rotina diaria do NewsMarket: coleta precos/noticias e gera as previsoes.
REM Para agendar: Agendador de Tarefas do Windows > Criar Tarefa Basica >
REM   Diariamente, 19:00 > Iniciar um programa > este arquivo.
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
    echo Criando ambiente virtual...
    python -m venv .venv || goto :erro
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :erro
)

if not exist logs mkdir logs
.venv\Scripts\python.exe -m newsmarket -v rodar >> logs\rodar_diario.log 2>&1
if errorlevel 1 goto :erro
echo Concluido. Veja logs\rodar_diario.log
exit /b 0

:erro
echo Falhou. Veja logs\rodar_diario.log
exit /b 1
