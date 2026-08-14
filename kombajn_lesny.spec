# -*- mode: python ; coding: utf-8 -*-
"""
Kombajn Leśny PRO — specyfikacja PyInstaller
==============================================
Buduje plik .exe z nowej struktury modułowej.

Użycie:
  pyinstaller kombajn_lesny.spec
"""

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None

# Zbierz wszystkie submoduły pakietu app (ważne dla PyInstaller!)
hidden_imports = collect_submodules('app')

# customtkinter i CTkToolTip mają pliki danych (motywy, czcionki, obrazy) — trzeba je włączyć ręcznie
hidden_imports += collect_submodules('customtkinter')
hidden_imports += collect_submodules('CTkToolTip')

datas = [
    ('STR_TYT.docx', '.'),
    ('STR_TYT_TYLKO-ISL-2.docx', '.'),
    ('Skroty.docx', '.'),
    ('BIAŁYNIN KRASÓWKA.xlsx', '.'),
    ('config', 'config'),
    ('pusty', 'pusty'),
]
datas += collect_data_files('customtkinter')
datas += collect_data_files('CTkToolTip')

hidden_imports += [
    'pandas',
    'pandas._libs',
    'pandas._libs.tslibs',
    'pandas._libs.tslibs.timedeltas',
    'numpy',
    'numpy.core',
    'fitz',
    'win32com.client',
    'pythoncom',
    'pyautogui',
    'pypdf',
    'openpyxl',
    'docx',
    'pyodbc',
    'PIL.Image',
    'PIL.ImageDraw',
    'customtkinter',
    'CTkToolTip',
]


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
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
