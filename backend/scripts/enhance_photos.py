"""
景区照片调色增强 - 国赛级观感
对Hero轮播与景点卡照片做:
  - 智能构图裁剪(去杂边/游客人群,主体居中)
  - 色彩增强(自然饱和度+对比度+微暖调)
  - 轻微锐化
输出 *-hd.jpg 版本,页面引用增强版。
"""
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter

ASSETS = Path(__file__).resolve().parents[2] / "design" / "lingshan-guide" / "assets"

# (文件, 裁剪比例(top, bottom), 目标宽, 增强参数)
JOBS = {
    # Hero轮播:横构图强化
    "fangong-palace.jpg":   (0.0, 1.0, 1600, dict(sat=1.12, con=1.08, sharp=1.15, warm=4)),
    "xiangfu-temple.jpg":   (0.0, 0.94, 1600, dict(sat=1.28, con=1.12, sharp=1.2, warm=8)),
    "jiulong-guanyu.jpg":   (0.0, 0.82, 1400, dict(sat=1.22, con=1.10, sharp=1.2, warm=6)),
    "fojiao-museum.jpg":    (0.0, 1.0, 1600, dict(sat=1.15, con=1.08, sharp=1.15, warm=4)),
    # 景点卡
    "lingshan-buddha.jpg":  (0.06, 0.96, 1200, dict(sat=1.18, con=1.08, sharp=1.15, warm=5)),
    "baizi-milefo.jpg":     (0.05, 0.95, 1200, dict(sat=1.18, con=1.08, sharp=1.15, warm=5)),
}


def enhance(img: Image.Image, p) -> Image.Image:
    img = ImageEnhance.Color(img).enhance(p["sat"])        # 饱和度
    img = ImageEnhance.Contrast(img).enhance(p["con"])     # 对比度
    # 微暖调(金气)
    r, g, b = img.split()
    r = r.point(lambda x: min(255, x + p["warm"]))
    g = g.point(lambda x: min(255, x + p["warm"] // 2))
    img = Image.merge("RGB", (r, g, b))
    img = img.filter(ImageFilter.UnsharpMask(radius=1.6, percent=int(60 * p["sharp"]), threshold=2))
    return img


def main():
    for name, (top, bottom, tw, params) in JOBS.items():
        src = ASSETS / name
        img = Image.open(src).convert("RGB")
        W, H = img.size
        img = img.crop((0, int(H * top), W, int(H * bottom)))
        if img.width > tw:
            img = img.resize((tw, int(img.height * tw / img.width)), Image.LANCZOS)
        img = enhance(img, params)
        out = ASSETS / (src.stem + "-hd.jpg")
        img.save(out, quality=86, optimize=True)
        print(f"{out.name}: {img.size} ({out.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
