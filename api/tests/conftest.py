import os
import sys
from pathlib import Path

# 允许直接 `python -m pytest` 而无需安装包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("PYTEST", "1")
