@echo off
REM Gera dist\ARPE_Relatorios\ARPE_Relatorios.exe  (requer Python 3.11+ no Windows)
python -m pip install -r requirements.txt pyinstaller || goto :erro
python -m PyInstaller --noconfirm --clean --windowed --name ARPE_Relatorios ^
  --add-data "arpe_relatorios\web;arpe_relatorios\web" ^
  --add-data "modelos;modelos" ^
  --collect-submodules webview ^
  main.py || goto :erro
copy /Y metas_municipios.csv dist\ARPE_Relatorios\ >nul
xcopy /E /I /Y assets dist\ARPE_Relatorios\assets >nul
echo.
echo Pronto: dist\ARPE_Relatorios\ARPE_Relatorios.exe
echo Coloque DadosFiscalização.xlsx ao lado do .exe (ou use "Abrir planilha..." no aplicativo).
exit /b 0
:erro
echo Falha na geracao do executavel.
exit /b 1
