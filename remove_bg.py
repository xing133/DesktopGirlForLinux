#!/home/gary/test/desktop-dancer/.venv/bin/python
"""
阶段1：AI 逐帧抠图，输出透明 PNG 序列

用法：
  .venv/bin/python remove_bg.py
  .venv/bin/python remove_bg.py --display-height 600 --overwrite
"""

import argparse
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image


def parse_args():
    p = argparse.ArgumentParser(description="视频背景去除")
    p.add_argument("--input", default="jean.mp4", help="输入视频文件")
    p.add_argument("--frames-dir", default="dancer/jean", help="输出帧目录（建议格式：dancer/<角色名>）")
    p.add_argument("--display-height", default=450, type=int,
                   help="输出帧高度（像素），宽度按比例缩放")
    p.add_argument("--model", default="u2net_human_seg",
                   choices=["u2net", "u2net_human_seg", "u2netp"],
                   help="U2Net 模型（u2net_human_seg 对人体效果最好）")
    p.add_argument("--overwrite", action="store_true",
                   help="强制重新处理（即使帧已存在）")
    return p.parse_args()


def probe_video(path):
    """用 ffprobe 获取视频元数据，返回 (fps, n_frames, width, height)"""
    out = subprocess.check_output([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", path
    ])
    import json as _json
    data = _json.loads(out)
    vs = next(s for s in data["streams"] if s["codec_type"] == "video")
    fps = float(Fraction(vs["r_frame_rate"]))
    n_frames = int(vs.get("nb_frames") or round(float(vs["duration"]) * fps))
    return fps, n_frames, int(vs["width"]), int(vs["height"])


def iter_raw_frames(video_path, width, height):
    """通过 ffmpeg stdout pipe 逐帧读取原始 RGB 数据，避免 moviepy 开销"""
    frame_bytes = width * height * 3
    proc = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", video_path,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE
    )
    try:
        while True:
            raw = proc.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            yield np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
    finally:
        proc.stdout.close()
        proc.wait()


def main():
    args = parse_args()
    input_path = Path(args.input)
    frames_dir = Path(args.frames_dir)
    meta_path = frames_dir / "metadata.json"

    if not input_path.exists():
        sys.exit(f"错误：找不到输入文件 '{input_path}'")

    # 检查是否已处理过
    if meta_path.exists() and not args.overwrite:
        existing = sorted(frames_dir.glob("frame_*.png"))
        if existing:
            print(f"已有 {len(existing)} 帧在 '{frames_dir}/'")
            print("如需重新处理，添加 --overwrite 参数")
            sys.exit(0)

    frames_dir.mkdir(parents=True, exist_ok=True)

    fps, n_frames, w, h = probe_video(str(input_path))
    display_h = args.display_height
    display_w = int(round(w / h * display_h))
    print(f"视频：{w}×{h} @ {fps:.0f}fps，共 {n_frames} 帧")
    print(f"输出尺寸：{display_w}×{display_h}px")

    # 加载模型（首次运行会自动下载 ~176MB 到 ~/.u2net/）
    print(f"\n加载模型 '{args.model}'（首次运行会下载约 176MB，请耐心等待）...")
    from backgroundremover.u2net import detect
    from backgroundremover.bg import naive_cutout
    net = detect.load_model(model_name=args.model)
    print("模型加载完成\n")

    print(f"开始处理 {n_frames} 帧（CPU 推理，预计 3~5 分钟）...")
    idx = 0
    for frame_np in iter_raw_frames(str(input_path), w, h):
        idx += 1
        out_path = frames_dir / f"frame_{idx:04d}.png"

        pil_img = Image.fromarray(frame_np, "RGB")
        # detect.predict 返回 RGB 模式的 mask 图像
        # convert("L") 转为灰度，naive_cutout 需要 L 模式
        mask = detect.predict(net, frame_np).convert("L")
        rgba = naive_cutout(pil_img, mask)
        rgba_scaled = rgba.resize((display_w, display_h), Image.LANCZOS)
        rgba_scaled.save(str(out_path), "PNG")

        if idx % 10 == 0 or idx == n_frames:
            print(f"  [{idx:4d}/{n_frames}] {idx / n_frames * 100:.1f}%")

    # 从实际输出读取最终尺寸（resize 可能有 1px 误差）
    sample = Image.open(frames_dir / "frame_0001.png")
    actual_w, actual_h = sample.size

    meta = {
        "fps": fps,
        "frame_count": idx,
        "width": actual_w,
        "height": actual_h,
        "source_video": str(input_path),
        "model": args.model,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n完成！{idx} 帧已写入 '{frames_dir}/'")
    print(f"帧尺寸：{actual_w}×{actual_h}px，元数据：{meta_path}")
    print(f"\n下一步运行：python3 dancer.py")


if __name__ == "__main__":
    main()
