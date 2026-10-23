"""
为无实拍照片的景点生成设计感占位图:
渐变底 + 山影/莲花剪影 + 楷体景点全名 + 类别水印
输出: design/lingshan-guide/assets/spot-imgs/{spot_id}.jpg
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "design" / "lingshan-guide" / "assets" / "spot-imgs"
FONT_KAI = "C:/Windows/Fonts/simkai.ttf"
FONT_YH = "C:/Windows/Fonts/msyh.ttc"

# 每类配色(深→浅斜向渐变)
PALETTES = {
    "佛教建筑": ((26, 48, 84), (74, 127, 193)),
    "雕塑圣景": ((110, 74, 32), (197, 165, 90)),
    "文化场馆": ((58, 42, 86), (142, 123, 192)),
    "拈花湾":   ((36, 90, 74), (103, 178, 140)),
}
SPOTS = {
    "LS-001": ("灵山大照壁", "佛教建筑"),
    "LS-002": ("五明桥", "佛教建筑"),
    "LS-003": ("佛足坛", "雕塑圣景"),
    "LS-004": ("五智门", "佛教建筑"),
    "LS-005": ("菩提大道", "佛教建筑"),
    "LS-007": ("降魔浮雕", "雕塑圣景"),
    "LS-008": ("阿育王柱", "雕塑圣景"),
    "LS-014": ("五印坛城", "佛教建筑"),
    "LS-015": ("曼飞龙塔", "佛教建筑"),
    "LS-016": ("无尽意斋", "文化场馆"),
    "NH-001": ("拈花广场", "拈花湾"),
    "NH-002": ("梵天花海", "拈花湾"),
    "NH-003": ("香月花街", "拈花湾"),
    "NH-004": ("拈花堂", "拈花湾"),
    "NH-005": ("五灯湖", "拈花湾"),
    "NH-006": ("鹿鸣谷", "拈花湾"),
}
W, H = 800, 500


def lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def make(name, cat, out):
    c_dark, c_light = PALETTES[cat]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    # 斜向渐变
    for y in range(H):
        for_step = y / H
        d.line([(0, y), (W, y)], fill=lerp(c_dark, c_light, for_step ** 1.4))
    # 右上光环
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    dg.ellipse([W - 260, -140, W + 140, 260], fill=(255, 240, 200, 46))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)
    # 远山剪影(两层)
    def ridge(base_y, amp, color, alpha):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        pts = [(0, H)]
        import math
        for x in range(0, W + 40, 40):
            y = base_y + math.sin(x / 140.0) * amp + math.sin(x / 57.0) * amp * 0.4
            pts.append((x, y))
        pts.append((W, H))
        dl.polygon(pts, fill=(*color, alpha))
        return layer
    img = Image.alpha_composite(img.convert("RGBA"), ridge(H - 150, 46, c_dark, 90)).convert("RGBA")
    img = Image.alpha_composite(img, ridge(H - 80, 30, c_dark, 130))
    # 大莲花剪影(右下)
    lotus = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lotus)
    cx, cy, r = W - 130, H - 60, 150
    for ang in range(0, 360, 30):
        import math
        rad = math.radians(ang)
        px = cx + math.cos(rad) * r * 0.55
        py = cy + math.sin(rad) * r * 0.55
        dl.ellipse([px - r * 0.42, py - r * 0.16, px + r * 0.42, py + r * 0.16],
                   fill=(255, 255, 255, 22))
    lotus = lotus.filter(ImageFilter.GaussianBlur(3))
    img = Image.alpha_composite(img, lotus)
    d = ImageDraw.Draw(img)
    # 楷体景点名(带投影)
    f_big = ImageFont.truetype(FONT_KAI, 108)
    bbox = d.textbbox((0, 0), name, font=f_big)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = (W - tw) / 2, H * 0.34 - th / 2
    d.text((tx + 4, ty + 5), name, font=f_big, fill=(0, 0, 0, 90))
    d.text((tx, ty), name, font=f_big, fill=(255, 252, 244))
    # 英文装饰线
    f_sub = ImageFont.truetype(FONT_YH, 22)
    sub = "LINGSHAN HOLY LAND"
    d.text(((W - d.textlength(sub, font=f_sub)) / 2, ty + th + 22), sub,
           font=f_sub, fill=(255, 255, 255, 170))
    # 底部类别条
    f_cat = ImageFont.truetype(FONT_YH, 24)
    d.rectangle([0, H - 56, W, H], fill=(0, 0, 0, 60))
    d.text((28, H - 43), f"灵山胜境 · {cat}", font=f_cat, fill=(240, 230, 210))
    d.text((W - 140, H - 43), "AI讲解 ›", font=f_cat, fill=(223, 201, 138))

    img = img.convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.04)
    img.save(out, quality=88, optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for sid, (name, cat) in SPOTS.items():
        make(name, cat, OUT / f"{sid}.jpg")
        print(f"{sid}.jpg  {name} [{cat}]")


if __name__ == "__main__":
    main()
