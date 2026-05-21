"""
HedgeFund AI — EXE Build Script
Çalıştır: python build.py
Çıktı   : dist/HedgeFundAI/HedgeFundAI.exe
"""

import subprocess, sys, shutil
from pathlib import Path

ROOT = Path(__file__).parent

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "HedgeFundAI",
    "--icon", str(ROOT / "icon.ico") if (ROOT / "icon.ico").exists() else "NONE",
    "--add-data", f"{ROOT / 'config'}{';'}config",
    "--add-data", f"{ROOT / 'data'}{';'}data",
    "--hidden-import", "customtkinter",
    "--hidden-import", "matplotlib",
    "--hidden-import", "matplotlib.backends.backend_tkagg",
    "--hidden-import", "pandas",
    "--hidden-import", "numpy",
    "--hidden-import", "yfinance",
    "--hidden-import", "ccxt",
    "--hidden-import", "yaml",
    "--hidden-import", "requests",
    "--hidden-import", "ta",
    "--hidden-import", "PIL",
    "--hidden-import", "darkdetect",
    "--hidden-import", "packaging",
    "--collect-all",  "customtkinter",
    "--collect-all",  "darkdetect",
    str(ROOT / "app.py"),
]

print("="*60)
print("  HedgeFund AI — PyInstaller Build")
print("="*60)
result = subprocess.run(cmd, cwd=ROOT)

if result.returncode == 0:
    print("\n" + "="*60)
    print("  BUILD BAŞARILI!")
    print(f"  EXE konum: {ROOT / 'dist' / 'HedgeFundAI' / 'HedgeFundAI.exe'}")
    print("="*60)
else:
    print("\n BUILD HATASI — yukarıdaki çıktıyı kontrol et.")
