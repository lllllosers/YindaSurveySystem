"""Deterministic icon conversion from the unmodified official logo; no redrawing.

The upper symbol is used for small icons, excluding the large Chinese wordmark.
PNG payloads in the ICO retain transparency at all Windows icon sizes.
"""
from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter


def main():
    folder = Path(__file__).resolve().parent / "assets"
    original = QImage(str(folder / "YindaSurvey_Official_Logo.png"))
    if original.isNull():
        raise RuntimeError("缺少用户提供的正式 Logo。")
    symbol = original.copy(round(original.width() * .16), round(original.height() * .06),
                           round(original.width() * .67), round(original.height() * .65))
    mark = QImage(1024, 1024, QImage.Format_ARGB32)
    mark.fill(Qt.transparent)
    resized = symbol.scaled(940, 940, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    painter = QPainter(mark)
    painter.drawImage((1024 - resized.width()) // 2, (1024 - resized.height()) // 2, resized)
    painter.end()
    mark.save(str(folder / "BrandMark.png"))
    payloads = []
    sizes = (16, 24, 32, 48, 64, 128, 256)
    for size in sizes:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        mark.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(buffer, "PNG")
        payloads.append(bytes(data))
    offset = 6 + 16 * len(sizes)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(sizes)))
    for size, payload in zip(sizes, payloads):
        directory.extend(struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0,
                                     0, 0, 1, 32, len(payload), offset))
        offset += len(payload)
    (folder / "YindaWebCenter.ico").write_bytes(bytes(directory) + b"".join(payloads))


if __name__ == "__main__":
    main()
