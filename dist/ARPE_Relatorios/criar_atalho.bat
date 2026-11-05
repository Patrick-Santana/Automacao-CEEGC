@echo off
REM Cria o atalho "ARPE Relatorios" na Area de Trabalho do usuario atual (usa o caminho de rede \\servidor\...).
cd /d "%~dp0"
"%~dp0ARPE_Relatorios.exe" --criar-atalho
