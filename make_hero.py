"""첫 화면 히어로 영역 배경 영상(hero.mp4)을 만든다.

PRD.md 의 장면을 글자 없이 그림으로 옮긴다.
- 천천히 흘러가는 지도 길 : 여행하며 돌아다니는 지역
- 현재 위치에서 퍼지는 물결 : 현재 위치에서 반경 1.5km
- 깜빡이는 점 : 지금 영업 중인 가게들

모든 움직임이 LOOP_SECONDS 마다 정확히 처음으로 돌아오므로, 반복 재생해도 끊기지 않는다.

    python make_hero.py              # hero.mp4 를 만든다 (imageio-ffmpeg 필요)
    python make_hero.py --preview D  # 영상 대신 몇 장의 PNG 를 D 폴더에 만든다
"""

import argparse
import math
from pathlib import Path

import numpy as np

WIDTH, HEIGHT = 1280, 720
FPS = 30
LOOP_SECONDS = 10
FRAMES = FPS * LOOP_SECONDS

# 중심 색 #C9A982 와, 거기에 흰색·검은색을 섞은 같은 계열 색만 쓴다
BASE = np.array([201, 169, 130], dtype=np.float32) / 255


def tint(amount):
    """BASE 에 흰색을 amount 만큼 섞는다."""
    return BASE + (1 - BASE) * amount


def shade(amount):
    """BASE 에 검은색을 amount 만큼 섞는다."""
    return BASE * (1 - amount)


BG_LIGHT = tint(0.38)
BG_DARK = BASE
STREET = tint(0.75)
MAIN_ROAD = tint(0.9)
PARK = shade(0.06)
STORE = shade(0.32)
STORE_GLOW = tint(0.55)
HERE = shade(0.45)
RIPPLE = shade(0.3)

# 지도 한 칸(TILE)이 한 바퀴 동안 대각선으로 정확히 한 칸 흘러간다
TILE = 300
CELL = TILE // 4
MAP_ANGLE = math.radians(-14)

# 한 칸 안의 가게 점 (칸 안 위치 x, y, 깜빡이는 시작점). 칸마다 같은 무늬가 되풀이된다
STORES = [
    (0.20, 0.34, 0.00),
    (0.66, 0.16, 0.40),
    (0.58, 0.74, 0.75),
]

# 공원처럼 살짝 진한 블록 (칸 안 4x4 블록 중 어느 것인지)
PARKS = {(1, 0), (3, 2)}

# 현재 위치 · 가운데 제목과 버튼을 피해 오른쪽에 둔다
HERE_X, HERE_Y = 0.74 * WIDTH, 0.52 * HEIGHT
RIPPLE_COUNT = 3
RIPPLE_MAX = 0.42 * HEIGHT

ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)


def blend(image, color, alpha):
    """image 위에 color 를 alpha(0~1 배열) 만큼 덮는다."""
    a = np.clip(alpha, 0, 1)[..., None]
    image *= 1 - a
    image += a * color


def line_alpha(distance, half_width):
    """선까지의 거리로 가장자리를 부드럽게 한 선의 진하기."""
    return np.clip(half_width + 0.5 - distance, 0, 1)


def wrapped(value, period):
    """주기 period 로 되풀이되는 좌표에서, 가장 가까운 0 까지의 거리(부호 있음)."""
    return (value + period / 2) % period - period / 2


def render(frame):
    t = frame / FRAMES  # 0 이상 1 미만. 1 이 되면 처음과 같다
    wave = 2 * math.pi * t

    # 바탕 · 왼쪽 위가 밝고 오른쪽 아래가 짙은 기울기가 천천히 숨 쉬듯 움직인다
    ramp = (xs / WIDTH * 0.55 + ys / HEIGHT * 0.45) + 0.06 * math.sin(wave)
    ramp = np.clip(ramp, 0, 1)[..., None]
    image = BG_LIGHT * (1 - ramp) + BG_DARK * ramp

    # 지도 좌표 · 화면을 살짝 돌리고, 한 바퀴에 대각선으로 한 칸 흘린다
    cos_a, sin_a = math.cos(MAP_ANGLE), math.sin(MAP_ANGLE)
    u = xs * cos_a - ys * sin_a + t * TILE
    v = xs * sin_a + ys * cos_a + t * TILE

    # 공원 블록
    block_u = np.floor(u / CELL).astype(np.int64) % 4
    block_v = np.floor(v / CELL).astype(np.int64) % 4
    park = np.zeros_like(u)
    for bu, bv in PARKS:
        park[(block_u == bu) & (block_v == bv)] = 1
    blend(image, PARK, park * 0.35)

    # 골목길과 큰길
    street = np.maximum(
        line_alpha(np.abs(wrapped(u, CELL)), 1.0),
        line_alpha(np.abs(wrapped(v, CELL)), 1.0),
    )
    blend(image, STREET, street * 0.28)
    road = np.maximum(
        line_alpha(np.abs(wrapped(u, TILE)), 2.5),
        line_alpha(np.abs(wrapped(v, TILE)), 2.5),
    )
    blend(image, MAIN_ROAD, road * 0.45)

    # 가게 점 · 칸과 함께 흘러가며, 한 바퀴에 두 번 천천히 깜빡인다
    for sx, sy, phase in STORES:
        du = wrapped(u - sx * TILE, TILE)
        dv = wrapped(v - sy * TILE, TILE)
        distance = np.sqrt(du * du + dv * dv)
        glow = 0.5 + 0.5 * math.sin(2 * wave + 2 * math.pi * phase)
        blend(image, STORE_GLOW, np.exp(-((distance / 16) ** 2)) * (0.3 + 0.4 * glow))
        blend(image, STORE, line_alpha(distance, 4.0) * (0.45 + 0.35 * glow))

    # 현재 위치에서 퍼지는 물결 · 세 겹이 1/3 바퀴씩 어긋나 끝없이 이어진다
    here = np.sqrt((xs - HERE_X) ** 2 + (ys - HERE_Y) ** 2)
    for k in range(RIPPLE_COUNT):
        p = (t + k / RIPPLE_COUNT) % 1
        radius = 14 + p * (RIPPLE_MAX - 14)
        fade = (1 - p) ** 1.6 * min(1.0, p / 0.08)
        blend(image, RIPPLE, line_alpha(np.abs(here - radius), 1.6) * 0.5 * fade)
    blend(image, STORE_GLOW, np.exp(-((here / 30) ** 2)) * 0.7)
    blend(image, HERE, line_alpha(here, 7.0))

    # 가장자리를 살짝 어둡게 해 가운데 글자가 잘 보이게 한다
    edge = ((xs / WIDTH - 0.5) ** 2 + (ys / HEIGHT - 0.5) ** 2) * 0.35
    image *= (1 - edge)[..., None]

    return (np.clip(image, 0, 1) * 255 + 0.5).astype(np.uint8)


def save_preview(folder):
    from PIL import Image

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for frame in (0, FRAMES // 4, FRAMES // 2, FRAMES - 1):
        Image.fromarray(render(frame)).save(folder / f"hero_{frame:03d}.png")
    # 마지막 다음 장(FRAMES)이 첫 장(0)과 같아야 끊기지 않는다
    gap = np.abs(render(FRAMES).astype(int) - render(0).astype(int)).max()
    print(f"첫 장과 한 바퀴 뒤 장의 가장 큰 차이 : {gap} (0 이면 끊기지 않음)")


def save_video(path):
    import imageio_ffmpeg

    writer = imageio_ffmpeg.write_frames(
        str(path),
        (WIDTH, HEIGHT),
        fps=FPS,
        codec="libx264",
        pix_fmt_out="yuv420p",
        quality=8,
        output_params=["-movflags", "+faststart"],
    )
    writer.send(None)
    for frame in range(FRAMES):
        writer.send(render(frame).tobytes())
    writer.close()
    print(f"{path} 를 만들었어요 · {WIDTH}x{HEIGHT}, {FPS}fps, {LOOP_SECONDS}초, {FRAMES}장")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="첫 화면 히어로 배경 영상 만들기")
    parser.add_argument("--preview", help="영상 대신 PNG 미리보기를 이 폴더에 만든다")
    args = parser.parse_args()
    if args.preview:
        save_preview(args.preview)
    else:
        save_video(Path(__file__).with_name("hero.mp4"))
