# -*- mode: python ; coding: utf-8 -*-
# PeakCut PyInstaller spec file

import os

block_cipher = None
src_dir = 'src'

a = Analysis(
    [os.path.join(src_dir, 'main_pyqt.py')],
    pathex=[src_dir],
    binaries=[],
    datas=[
        (os.path.join('assets', 'pictures'), os.path.join('assets', 'pictures')),
        (os.path.join('assets', 'zahlen'), os.path.join('assets', 'zahlen')),
        ('luts', 'luts'),
    ],
    hiddenimports=[
        'core.analysis_process',
        'core.detection',
        'core.sync',
        'core.exporters',
        'core.peak',
        'core.playback',
        'core.project',
        'core.session',
        'lib.lut_processor',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PeakCut',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PeakCut',
)

app = BUNDLE(
    coll,
    name='PeakCut.app',
    icon='PeakCut.icns',
    bundle_identifier='com.peakcut.app',
    info_plist={
        'CFBundleDisplayName': 'PeakCut',
        'CFBundleShortVersionString': '2.9.0',
        'CFBundleVersion': '2.9.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '12.0',
        'NSMicrophoneUsageDescription': 'PeakCut needs microphone access for audio playback.',
    },
)
