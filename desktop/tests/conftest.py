from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "desktop/src")]
