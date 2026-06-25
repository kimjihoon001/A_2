#!/usr/bin/env python3
"""
pixelart.py — 사진을 픽셀 캐릭터 아트로 변환

사용법:
  python3 pixelart.py 입력.jpg                    # 기본 (48px, 16색)
  python3 pixelart.py 입력.jpg -s 32 -c 8         # 32px 해상도, 8색
  python3 pixelart.py 입력.jpg -s 64 -c 32 -o 결과.png
"""

import argparse
import sys
from pathlib import Path
from PIL import Image


def to_pixelart(src: Path, dst: Path, size: int, colors: int, upscale: int):
    img = Image.open(src).convert("RGBA")

    # 정사각형 크롭 (중앙)
    w, h = img.size
    crop = min(w, h)
    left = (w - crop) // 2
    top  = (h - crop) // 2
    img  = img.crop((left, top, left + crop, top + crop))

    # 소형 해상도로 다운스케일 (픽셀화 핵심)
    small = img.resize((size, size), Image.NEAREST)

    # 알파 채널 기반 배경 제거 → 흰 배경 합성
    bg = Image.new("RGBA", small.size, (255, 255, 255, 255))
    bg.paste(small, mask=small.split()[3])
    small = bg.convert("RGB")

    # 색 수 제한 (포스터라이즈 효과)
    small = small.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
    small = small.convert("RGB")

    # 업스케일 (nearest-neighbor — 블록 픽셀 느낌 유지)
    out = small.resize((size * upscale, size * upscale), Image.NEAREST)
    out.save(dst)
    print(f"저장 완료: {dst}  ({size}×{size}px, {colors}색, 출력 {size*upscale}×{size*upscale}px)")


def main():
    ap = argparse.ArgumentParser(description="사진 → 픽셀 캐릭터 아트 변환")
    ap.add_argument("input",               help="입력 이미지 경로")
    ap.add_argument("-s", "--size",   type=int, default=48,  help="픽셀 해상도 (기본 48)")
    ap.add_argument("-c", "--colors", type=int, default=16,  help="색상 수 (기본 16)")
    ap.add_argument("-u", "--upscale",type=int, default=12,  help="출력 배율 (기본 12배)")
    ap.add_argument("-o", "--output",          default=None, help="출력 파일명 (기본: 입력파일_pixel.png)")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"파일 없음: {src}", file=sys.stderr)
        sys.exit(1)

    dst = Path(args.output) if args.output else src.with_stem(src.stem + "_pixel").with_suffix(".png")
    to_pixelart(src, dst, args.size, args.colors, args.upscale)


if __name__ == "__main__":
    main()
