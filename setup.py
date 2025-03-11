from setuptools import setup

APP = ['main.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'packages': ['PyQt6', 'pkg_resources', 'jaraco.text'],
    'iconfile': 'app.icns',
    'plist': {
        'CFBundleName': 'iOS崩溃日志符号化工具',
        'CFBundleDisplayName': 'iOS崩溃日志符号化工具',
        'CFBundleIdentifier': 'com.crashsymbolizer.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': '© 2024'
    },
    'excludes': ['packaging']  # 排除可能导致冲突的包
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)