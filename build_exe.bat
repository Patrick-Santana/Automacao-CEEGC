@echo off
REM Gera dist\ArpeRelatorios\ArpeRelatorios.exe (colocar DadosFiscalização.xlsx e a pasta assets ao lado do .exe)
pip install -r requirements.txt
pyinstaller --noconfirm --windowed --name ArpeRelatorios --collect-all matplotlib --collect-all docx main.py
echo.
echo Pronto: dist\ArpeRelatorios\ArpeRelatorios.exe
pause
