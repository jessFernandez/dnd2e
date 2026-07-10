# -*- mode: python ; coding: utf-8 -*-
import os, sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Grab QtWebEngine resources (required for QWebEngineView to work)
qtwe_data = collect_data_files('PyQtWebEngine', include_py_files=False)
qtwe_bins = collect_dynamic_libs('PyQtWebEngine')

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=qtwe_bins,
    datas=[
        ('dnd2e.db',              '.'),
        ('dmscreen_html.py',      '.'),
        ('actionsscreen_html.py', '.'),
        ('spellsscreen_html.py',  '.'),
        ('splash_html.py',        '.'),
        ('screen_common.py',      '.'),
        ('askscreen_html.py',     '.'),
        ('rules_agent.py',        '.'),
        *qtwe_data,
    ],
    hiddenimports=[
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebChannel',
        'dmscreen_html',
        'actionsscreen_html',
        'spellsscreen_html',
        'splash_html',
        'screen_common',
        'askscreen_html',
        'rules_agent',
        'charactermancer_html',
        'charactermancer',
        'character',
        'character_library',
        'char_rules',
        'ask_controller',
        'proficiencies_html',
        'roll20_export',
        'nonweapon_book', 'ct_text',
        'equipment',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['requests', 'beautifulsoup4', 'bs4', 'playwright'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DnD2eRules',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DnD2eRules',
)
