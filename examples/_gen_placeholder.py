"""生成 examples 夹具用的占位图（纯标准库，无 Pillow）。

用途：让 `errors/BIO-20261013-001.md` 里的图片引用是一个**真实可打开**的
文件，而不是断链——断链的夹具等于没有夹具。

重新生成：
    python examples/_gen_placeholder.py

图形是一条**虚构的**膜电位变化曲线（静息低电位 → 上升 → 峰值 → 回落），
与夹具错题 BIO-20261013-001 的虚构题干对应。不含任何真实卷面内容。
"""

import math
import os
import struct
import zlib

W, H = 400, 200
AX, AY = 60, 160  # 原点（左、下）
BLUE = (31, 78, 140)
RED = (196, 32, 38)
GRAY = (150, 150, 150)


def build_pixels():
    px = bytearray(b"\xff" * (W * H * 3))

    def put(x, y, color):
        if 0 <= x < W and 0 <= y < H:
            off = (y * W + x) * 3
            px[off:off + 3] = bytes(color)

    def hline(y, x0, x1, color):
        for x in range(x0, x1 + 1):
            put(x, y, color)

    def vline(x, y0, y1, color):
        for y in range(y0, y1 + 1):
            put(x, y, color)

    # 坐标轴
    hline(AY, AX, W - 12, BLUE)
    vline(AX, 12, AY, BLUE)
    # 刻度
    for k in range(1, 5):
        hline(AY - k * 28, AX - 4, AX + 4, BLUE)
        vline(AX + k * 62, AY - 4, AY + 4, BLUE)
    # 零线（虚线）
    for x in range(AX + 4, W - 12, 8):
        put(x, AY - 28, GRAY)

    # 曲线：静息低电位 → 快速上升 → 峰值 → 回落 → 恢复
    span = (W - 14) - AX
    for x in range(AX + 5, W - 12):
        t = (x - AX) / span
        if t < 0.15:
            v = 0.10
        elif t < 0.34:
            v = 0.10 + (t - 0.15) / 0.19 * 0.90
        elif t < 0.52:
            v = 1.00 - (t - 0.34) / 0.18 * 0.80
        else:
            v = 0.20 + 0.035 * math.sin((t - 0.52) * 11)
        y = int(AY - v * 128)
        for dy in (-1, 0, 1):
            put(x, y + dy, RED)

    # 上升段标注色块（示意「0~2ms 区间」）
    xa, xb = AX + int(0.15 * span), AX + int(0.34 * span)
    for x in range(xa, xb + 1):
        put(x, AY + 16, BLUE)
        put(x, AY + 17, BLUE)

    return px


def chunk(tag, data):
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def main():
    px = build_pixels()
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter type 0
        raw.extend(px[y * stride:(y + 1) * stride])

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")

    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(
        here, "data", "subjects", "生物", "assets", "BIO-20261013-001-01.png"
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(png)
    print("wrote %s (%d bytes)" % (out, len(png)))


if __name__ == "__main__":
    main()