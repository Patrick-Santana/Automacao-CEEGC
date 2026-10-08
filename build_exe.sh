#!/usr/bin/env bash
pip install -r requirements.txt
pyinstaller --noconfirm --windowed --name ArpeRelatorios --collect-all matplotlib --collect-all docx main.py
