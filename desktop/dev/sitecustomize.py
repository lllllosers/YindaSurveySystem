"""Local Desktop venv: select the Windows ICU ABI required by Qt.

Environment repair only. No copied DLLs, product changes, or system PATH changes.
"""
import ctypes
import os

_yinda_windows_icu = ctypes.WinDLL(
    os.path.join(os.environ["SystemRoot"], "System32", "icuuc.dll"),
    winmode=0x00000800,  # LOAD_LIBRARY_SEARCH_SYSTEM32
)
