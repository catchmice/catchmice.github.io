#!/usr/bin/env python3
"""CatchMICE 안드로이드 앱 아이콘·스플래시 생성기

`icons/icon-512.png`(Micy 로고) 한 장에서 안드로이드 런처 아이콘과 스플래시를 만듭니다.
아이콘을 바꾸고 싶으면 icons/icon-512.png 를 새로 넣고 이 스크립트를 다시 실행하세요.

    python3 scripts/make-android-icons.py

필요: pillow  (pip install pillow)
결과: android/app/src/main/res/mipmap-*/ic_launcher*.png, drawable-*/splash.png
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "icons" / "icon-512.png"
RES = ROOT / "android" / "app" / "src" / "main" / "res"
PAPER = (250, 246, 239)  # 사이트 배경색 (#faf6ef)

# 런처 아이콘 밀도별 크기
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
# 어댑티브 아이콘 foreground 는 108dp 캔버스
FOREGROUND = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
SPLASH = {
    "drawable": (480, 320),
    "drawable-land-mdpi": (480, 320),
    "drawable-land-hdpi": (800, 480),
    "drawable-land-xhdpi": (1280, 720),
    "drawable-land-xxhdpi": (1600, 960),
    "drawable-land-xxxhdpi": (1920, 1280),
    "drawable-port-mdpi": (320, 480),
    "drawable-port-hdpi": (480, 800),
    "drawable-port-xhdpi": (720, 1280),
    "drawable-port-xxhdpi": (960, 1600),
    "drawable-port-xxxhdpi": (1280, 1920),
}


def resize(img, size):
    return img.resize((size, size), Image.LANCZOS)


def circular(img):
    """정사각 이미지를 원형으로 잘라 RGBA 로 돌려줍니다."""
    w, h = img.size
    mask = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, w * 4 - 1, h * 4 - 1), fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img.convert("RGBA"), (0, 0), mask)
    return out


def main():
    art = Image.open(SRC).convert("RGB")
    bg = art.getpixel((1, 1))  # 아이콘 모서리 색 = 어댑티브 아이콘 배경색
    alt = Image.new("RGBA", (art.size[0] * 2, art.size[1] * 2), bg + (255,))

    for density, px in DENSITIES.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        icon = resize(art, px).convert("RGBA")
        icon.save(folder / "ic_launcher.png")
        circular(icon).save(folder / "ic_launcher_round.png")

    for density, px in FOREGROUND.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        # 원형 배지를 캔버스의 약 62% 로 (안드로이드 안전 영역 안쪽)
        badge = circular(resize(art, int(px * 0.62)))
        canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        off = ((px - badge.size[0]) // 2, (px - badge.size[1]) // 2)
        canvas.paste(badge, off, badge)
        canvas.save(folder / "ic_launcher_foreground.png")

    for folder_name, (w, h) in SPLASH.items():
        folder = RES / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGB", (w, h), PAPER)
        badge = circular(resize(art, int(min(w, h) * 0.42)))
        canvas.paste(badge, ((w - badge.size[0]) // 2, (h - badge.size[1]) // 2), badge)
        canvas.save(folder / "splash.png")

    values = RES / "values" / "ic_launcher_background.xml"
    values.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        f'    <color name="ic_launcher_background">#{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}</color>\n'
        "</resources>\n",
        encoding="utf-8",
    )
    print(f"✓ 아이콘 {len(DENSITIES)}종 + foreground {len(FOREGROUND)}종 + 스플래시 {len(SPLASH)}종 생성")
    print(f"  배경색: #{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}")


if __name__ == "__main__":
    main()
