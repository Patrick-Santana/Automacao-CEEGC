@echo off
REM Gera dist\ARPE_Relatorios\ARPE_Relatorios.exe  (requer Python 3.11+ no Windows)
REM Use "build_exe.bat debug" para gerar uma versao com console (mostra erros na tela).
set MODO=--windowed
if /I "%1"=="debug" set MODO=--console
REM Ambiente isolado (.venv_build): ignora pacotes soltos em %%APPDATA%%\Python e evita misturar versoes de numpy/pandas.
if not exist .venv_build\Scripts\python.exe (
  py -3.13 -m venv .venv_build 2>nul || py -3.12 -m venv .venv_build 2>nul || python -m venv .venv_build || goto :erro
)
call .venv_build\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller || goto :erro
python -m PyInstaller --noconfirm --clean %MODO% --name ARPE_Relatorios ^
  --add-data "arpe_relatorios\web;arpe_relatorios\web" ^
  --add-data "modelos;modelos" ^
  --collect-all webview --hidden-import tkinter ^
  main.py || goto :erro
copy /Y metas_municipios.csv dist\ARPE_Relatorios\ >nul
copy /Y criar_atalho.bat dist\ARPE_Relatorios\ >nul
copy /Y LEIA-ME_implantacao.txt dist\ARPE_Relatorios\ >nul
xcopy /E /I /Y assets dist\ARPE_Relatorios\assets >nul
echo.
echo Pronto: dist\ARPE_Relatorios\ARPE_Relatorios.exe
echo Copie a pasta ARPE_Relatorios INTEIRA para o servidor (veja LEIA-ME_implantacao.txt).
exit /b 0
:erro
echo Falha na geracao do executavel.
exit /b 1
