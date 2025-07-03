# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('common/*', 'common'),
        ('adapter/*', 'adapter'),
        ('application/*', 'application')
    ],
    hiddenimports=[
        'aiofiles',
        'anthropic',
        'autogen_agentchat',
        'autogen_core',
        'cachetools',
        'colorlog',
        'docker',
        'fastapi',
        'boto3',
        'google.genai',
        'ijson',
        'injector',
        'jsonlines',
        'loguru',
        'markitdown',
        'mcp',
        'openai',
        'pdfminer',
        'PIL',
        'playwright',
        'yaml',
        'socksio',
        'tiktoken',
        'tldextract',
        'uvicorn',
        'websockets',
    ],
    hookspath=[],
    hooksconfig={},
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
    name='efflux_desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
