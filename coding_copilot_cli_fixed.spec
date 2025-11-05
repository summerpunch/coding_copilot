# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Coding Copilot CLI
# 包含所有必要的数据文件（提示词、配置等）

import os
from pathlib import Path

block_cipher = None

# 项目根目录
root_dir = os.path.abspath('.')

# 收集所有需要打包的数据文件
datas = [
    # .env 文件
    ('.env', '.'),

    # 所有提示词文件 (.md)
    ('src/engine/prompts/*.md', 'src/engine/prompts'),

    # 如果有其他配置文件，也添加进来
]

a = Analysis(
    ['src/cli/main.py'],  # CLI 入口文件
    pathex=[root_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'src.engine.chat',
        'src.engine.agents.supervisor',
        'src.engine.agents.llm_factory',
        'src.engine.prompts.template',
        'langchain',
        'langchain_core',
        'langchain_anthropic',
        'langchain_openai',
        'langgraph',
        'langgraph.checkpoint.sqlite',
        'aiosqlite',
        'rich',
        'prompt_toolkit',
        'prompt_toolkit.shortcuts',
        'prompt_toolkit.shortcuts.dialogs',
        'prompt_toolkit.completion',
        'prompt_toolkit.key_binding',
        'prompt_toolkit.formatted_text',
        'prompt_toolkit.styles',
        'jinja2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='coding_copilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # 改为 False，保留调试符号
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
