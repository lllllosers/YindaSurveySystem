"""Desktop service adapters.

The desktop entry point is executed from ``src``. Add the repository root once
so the separately owned pure ``shared`` package is available in source runs.
Packaged builds include the same package through the PyInstaller search path.
"""

from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))
