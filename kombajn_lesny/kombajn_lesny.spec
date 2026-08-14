# -*- mode: python ; coding: utf-8 -*-
"""
Kombajn Leśny PRO — specyfikacja PyInstaller
==============================================
Buduje plik .exe z nowej struktury modułowej.

Użycie:
    pyinstaller kombajn_lesny.spec

Albo komenda bezpośrednia:
    pyinstaller --noconfirm --onefile --windowed \
        --icon "kombajn.ico" --name "KombajnLesnyPRO" \
        --add-data "STR_TYT.docx;." \
        --add-data "STR_TYT_TYLKO-ISL-2.docx;." \
        --add-data "Skroty.docx;." \
        --add-data "BIAŁYNIN KRASÓWKA.xlsx;." \
        --add-data "config;config" \
        --add-data "pusty;pusty" \
        main.py
"""

import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Zbierz wszystkie submoduły pakietu app (ważne dla PyInstaller!)
hidden_imports = collect_submodules('app')
hidden_imports += [
    'customtkinter',
    'CTkToolTip',
    'win32com.client',
    'pythoncom',
    'pyautogui',
    'fitz',
    'pypdf',
    'openpyxl',
    'docx',
    'pyodbc',
    'PIL.Image',
    'PIL.ImageDraw',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('STR_TYT.docx', '.'),
        ('STR_TYT_TYLKO-ISL-2.docx', '.'),
        ('Skroty.docx', '.'),
        ('BIAŁYNIN KRASÓWKA.xlsx', '.'),
        ('config', 'config'),
        ('pusty', 'pusty'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KombajnLesnyPRO',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='kombajn.ico' if os.path.exists('kombajn.ico') else None,
)
