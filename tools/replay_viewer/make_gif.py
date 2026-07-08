"""同梱フレーム＋観察ログから、READMEに載せるデモGIFを合成する(再現可能)。

qwen3-4b(PASS)で16フレーム再生 → 末尾で internvl3-2b(FAIL) に切替え、同じ動画・同じSOPでも
観察VLMを変えると判定が割れる様子を1枚のGIFで見せる。ビューア(build.py)と同じ配色。

    python tools/replay_viewer/make_gif.py   # docs/replay_demo.gif を生成
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent  # リポジトリルート
FRAMES = ROOT / "examples/konro_inspection/sample_output/frames"
MODELS = ROOT / "examples/konro_inspection/sample_output/models"
OUT = ROOT / "docs/replay_demo.gif"
QIDS = ["knob", "flame", "pointing", "grill", "battery", "gloves"]
# 日本語も含めて描けるフォント(macOS)。無ければ環境のTTFに差し替える。
FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"

C = {  # ビューア(template.html)と同じ配色
    "yes": ("#1a7f37", "#e6f4ea"), "no": ("#6b7280", "#f1f2f4"),
    "unclear": ("#b45309", "#fef3e0"), "?": ("#6b7280", "#f1f2f4"),
    "pass": ("#1a7f37", "#e6f4ea"), "fail": ("#c0362c", "#fbe9e7"),
    "ink": "#1c1c1c", "sub": "#666666", "line": "#dddddd", "bg": "#ffffff",
}


def _font(sz, bold=False):
    return ImageFont.truetype(FONT_PATH, sz, index=1 if bold else 0)


def _load(model):
    return {r["idx"]: r for r in json.loads((MODELS / f"{model}.json").read_text())}


def _ans(rec, q):
    c = rec.get("confidence", {}).get(q)
    return c["argmax"] if c else "?"


def _chip(d, x, y, w, h, qid, val):
    fg, bg = C.get(val, C["no"])
    d.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=bg)
    d.text((x + w / 2, y + 9), qid, font=_font(12), fill=C["sub"], anchor="mm")
    d.text((x + w / 2, y + h - 14), val, font=_font(16, True), fill=fg, anchor="mm")


def _pill(d, x, y, text, kind):
    fg, bg = C[kind]
    tw = d.textlength(text, font=_font(16, True))
    d.rounded_rectangle([x, y, x + tw + 28, y + 30], radius=15, fill=bg)
    d.text((x + 14 + tw / 2, y + 15), text, font=_font(16, True), fill=fg, anchor="mm")


def _compose(idx, model, log, verdict):
    W, PANEL = 640, 176
    img = Image.open(FRAMES / f"f{idx:03d}.jpg").convert("RGB").resize((640, 360))
    canvas = Image.new("RGB", (W, 360 + PANEL), C["bg"])
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.line([0, 360, W, 360], fill=C["line"], width=1)
    d.text((20, 380), model, font=_font(22, True), fill=C["ink"])
    d.text((20, 410), f"frame {idx + 1}/16  ·  t={idx}.0s", font=_font(14), fill=C["sub"])
    _pill(d, W - 118, 384, verdict, "pass" if verdict == "PASS" else "fail")
    rec = log[idx]
    cw, gap, y = 96, 8, 448
    x0 = (W - (cw * 6 + gap * 5)) // 2
    for i, q in enumerate(QIDS):
        _chip(d, x0 + i * (cw + gap), y, cw, 66, q, _ans(rec, q))
    return canvas


def main():
    q_log, i_log = _load("qwen3-4b"), _load("internvl3-2b")
    frames, durs = [], []
    for idx in range(16):                         # qwen3-4b で全16フレーム再生(PASS)
        frames.append(_compose(idx, "qwen3-4b", q_log, "PASS")); durs.append(360)
    for idx in [10, 11, 12, 13, 14, 15]:          # 同じ動画後半を internvl3-2b(FAIL) で
        frames.append(_compose(idx, "internvl3-2b", i_log, "FAIL")); durs.append(430)
    durs[15], durs[-1] = 900, 1200                # 切替直前と最終コマを長めに
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durs,
                   loop=0, optimize=True, disposal=2)
    print(f"書き出し: {OUT}  ({os.path.getsize(OUT)//1024} KB, {len(frames)}フレーム)")


if __name__ == "__main__":
    main()
