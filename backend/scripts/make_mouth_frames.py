"""
灵小仙口型帧离线预渲染
----------------------
从肖像底图生成6档开口度的变形帧:
  - dense像素级下颌变形(仅下巴椭圆区,衣服/耳环/颈部零位移)
  - 高斯羽化口腔/唇影/上齿,与画功融合
产物: design/lingshan-guide/assets/mouth-frames/m0.png ~ m5.png
运行: python backend/scripts/make_mouth_frames.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "design" / "lingshan-guide" / "assets" / "xiuxian-avatar.jpg"
OUT_DIR = ROOT / "design" / "lingshan-guide" / "assets" / "mouth-frames"

# ---- 像素级实测标定(全身图912x1216,4倍放大精网格复核) ----
MOUTH_X, MOUTH_Y, MOUTH_W = 0.478, 0.236, 0.053
MAX_DROP = 0.008          # 最大下巴下移(占图高比)——小嘴画风,幅度克制
RADIUS_X = 0.075          # 变形水平半径(收敛面部,避开莲花灯与发饰)
CHIN_Y = 0.27             # 变形垂直下界(下巴底,以下绝不动)
SKIN = (252, 223, 190)    # 脸颊肤色(实测)
SKIN_DARK = (242, 200, 168)
# 双眼标定(1%精网格复核)
EYE_L = (0.443, 0.203, 0.026)   # x, y, rx
EYE_R = (0.524, 0.202, 0.026)
LASH = (58, 42, 38)

# 开口度档位(0=闭合)——9档,帧间渐变更顺滑
LEVELS = [0.0, 0.14, 0.26, 0.38, 0.50, 0.62, 0.74, 0.86, 1.0]


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def jaw_warp(img: np.ndarray, k: float) -> np.ndarray:
    """dense下颌变形:嘴线以下平滑下移,下巴处渐隐为零"""
    H, W = img.shape[:2]
    mcx, mcy = MOUTH_X * W, MOUTH_Y * H
    max_drop = MAX_DROP * H * k
    chin_y = CHIN_Y * H
    rx = RADIUS_X * W

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # 水平余弦窗口(嘴周)
    u = np.abs(xx - mcx) / rx
    win_x = np.where(u < 1, np.cos(u * np.pi / 2) ** 2, 0.0)
    # 垂直:嘴线处为1,下巴处平滑归0;嘴线以上不动
    below = yy > mcy
    win_y = np.where(below, 1.0 - smoothstep(mcy, chin_y, yy), 0.0)
    dy = max_drop * win_x * win_y

    src_y = np.clip(yy - dy, 0, H - 1)
    # 双线性采样
    y0 = src_y.astype(np.int32)
    y1 = np.clip(y0 + 1, 0, H - 1)
    wy = (src_y - y0)[..., None]
    x_idx = xx.astype(np.int32)
    out = img[y0, x_idx] * (1 - wy) + img[y1, x_idx] * wy
    return out


def paint_cavity(frame: Image.Image, k: float) -> Image.Image:
    """唇部区自模糊(用图像自身像素融掉拉花唇)+ 径向渐变口腔"""
    if k <= 0.02:
        return frame
    W, H = frame.size
    mcx, mcy = MOUTH_X * W, MOUTH_Y * H
    drop = MAX_DROP * H * k
    frame = frame.convert("RGBA")

    # ---- 1) 唇部带自模糊:裁出唇区→高斯糊→椭圆羽化蒙版贴回 ----
    prx = int(MOUTH_W * W * 1.0)
    ptop = int(mcy - H * 0.003)
    pbot = int(mcy + drop + H * 0.008)
    x0, x1 = int(mcx - prx), int(mcx + prx)
    band = frame.crop((x0, ptop, x1, pbot))
    band_blur = band.filter(ImageFilter.GaussianBlur(radius=4.2))
    # 椭圆蒙版(中心实,边缘渐变)
    mask = Image.new("L", band.size, 0)
    dm = ImageDraw.Draw(mask)
    dm.ellipse([0, 0, band.size[0], band.size[1]], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=3.0))
    frame.paste(band_blur, (x0, ptop), mask)

    # ---- 2) 口腔层:深酒棕径向渐变,藏于上唇之下 ----
    cav_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(cav_layer)
    cw = MOUTH_W * W * (0.24 + 0.10 * k)
    ch = max(drop * 0.6, 1.5)
    cy = mcy + drop * 0.40          # 口腔重心下沉,上缘藏进上唇
    rings = 10
    for i in range(rings, 0, -1):
        t = i / rings
        # 外圈(38,14,11) → 中心(84,30,23) 深酒棕
        r = int(38 + (84 - 38) * (1 - t))
        g = int(14 + (30 - 14) * (1 - t))
        b = int(11 + (23 - 11) * (1 - t))
        d.ellipse([mcx - cw * t, cy - ch * t, mcx + cw * t, cy + ch * t],
                  fill=(r, g, b, 255))
    d.arc([mcx - cw * 1.1, mcy - ch * 0.5, mcx + cw * 1.1, mcy + ch * 0.5],
          start=200, end=340, fill=(70, 28, 22, 160), width=max(int(H * 0.002), 1))
    cav_layer = cav_layer.filter(ImageFilter.GaussianBlur(radius=max(ch * 0.15, 1.2)))
    frame.alpha_composite(cav_layer)
    return frame.convert("RGB")


def make_eyes_closed(base: Image.Image) -> Image.Image:
    """闭眼帧:眼部区自模糊(用图像自身像素盖住眼球)+ 柔和睫毛线
    与口型帧同思路——离线高质量,运行时crossfade,杜绝'鬼眼补丁'。"""
    W, H = base.size
    frame = base.convert("RGBA")
    for ex, ey, erx in (EYE_L, EYE_R):
        cx, cy = ex * W, ey * H
        rx = erx * W
        # 眼部带自模糊
        x0, x1 = int(cx - rx * 1.6), int(cx + rx * 1.6)
        y0, y1 = int(cy - rx * 0.9), int(cy + rx * 1.1)
        band = frame.crop((x0, y0, x1, y1))
        band_blur = band.filter(ImageFilter.GaussianBlur(radius=3.4))
        mask = Image.new("L", band.size, 0)
        dm = ImageDraw.Draw(mask)
        dm.ellipse([0, 0, band.size[0], band.size[1]], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=2.6))
        frame.paste(band_blur, (x0, y0), mask)
        # 睫毛线(闭合弧线,小羽化)
        lash_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lash_layer)
        lw = rx * 1.35
        ly = cy + rx * 0.12
        dl.arc([cx - lw, ly - rx * 0.5, cx + lw, ly + rx * 0.9],
               start=25, end=155, fill=(*LASH, 220), width=max(int(H * 0.0022), 2))
        # 睫毛末梢两三根
        dl.line([(cx + lw * 0.72, ly + rx * 0.30), (cx + lw * 0.88, ly + rx * 0.46)],
                fill=(*LASH, 200), width=2)
        dl.line([(cx + lw * 0.45, ly + rx * 0.44), (cx + lw * 0.55, ly + rx * 0.60)],
                fill=(*LASH, 190), width=2)
        lash_layer = lash_layer.filter(ImageFilter.GaussianBlur(radius=0.8))
        frame.alpha_composite(lash_layer)
    return frame.convert("RGB")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = Image.open(SRC).convert("RGB")
    arr = np.asarray(base).astype(np.float32)
    W, H = base.size
    print(f"底图 {W}x{H},生成 {len(LEVELS)} 帧...")

    for i, k in enumerate(LEVELS):
        if k <= 0.02:
            frame = base.copy()
        else:
            warped = jaw_warp(arr, k).astype(np.uint8)
            frame = Image.fromarray(warped)
            frame = paint_cavity(frame, k)
        out = OUT_DIR / f"m{i}.png"
        frame.save(out, optimize=True)
        print(f"  m{i}.png 开口度={k}")

    total = sum(f.stat().st_size for f in OUT_DIR.glob("*.png"))
    # 闭眼帧
    eyes = make_eyes_closed(base)
    eyes.save(OUT_DIR / "e0.png", optimize=True)
    total += (OUT_DIR / "e0.png").stat().st_size
    print(f"  e0.png 闭眼帧")
    print(f"完成,总大小 {total // 1024}KB → {OUT_DIR}")


if __name__ == "__main__":
    main()
