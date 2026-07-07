"""CLIエントリポイント。

  python src/cli.py run     --sop SOP.yaml --video VIDEO.mp4 --out-dir out/   # 動画→抽出→観察→判定を1コマンドで
  python src/cli.py observe --sop SOP.yaml --frames-dir DIR --out answer_log.json  # 観察だけ(フレーム済みの場合)
  python src/cli.py judge   --sop SOP.yaml --answer-log answer_log.json               # 判定だけ(観察済みの場合)
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys

from sop import load_sop, load_answer_log
from judge import judge, JudgeResult

MODELS = {
    "2b": "mlx-community/Qwen3-VL-2B-Instruct-4bit",
    "4b": "mlx-community/Qwen3-VL-4B-Instruct-4bit",
}


def _print_result(sop_name: str, result: JudgeResult) -> None:
    print(f"\nSOP: {sop_name}")
    print(f"{'event':14s} {'status':13s} {'t(s)':>6s}  span(idx)")
    for name, run in result.events.items():
        if run:
            print(f"{name:14s} {'done':13s} {run.t:>6.1f}  {run.start_idx}-{run.end_idx}")
        else:
            print(f"{name:14s} {'NOT_DETECTED':13s} {'  -':>6s}")
    print(f"\ncoverage = {result.coverage:.0%}")
    if result.violations:
        print("違反:")
        for v in result.violations:
            print(f"  - {v}")
    else:
        print("違反: なし")
    print(f"\n>>> 総合判定: {result.verdict} <<<\n")


def _run_observer(sop, meta_or_paths, model_key, out_path):
    """meta_or_pathsは[{"idx","t","path"}] または [path,...](idxはenumerateで振る)。"""
    from observe import Observer

    domain_hint = sop["sop"].get("domain_hint", "これは作業動画の1フレームです")
    model_name = MODELS.get(model_key, model_key)  # エイリアス or フルモデルIDのどちらでも受ける
    obs = Observer(model=model_name, questions=sop["questions"])

    if meta_or_paths and isinstance(meta_or_paths[0], str):
        meta = [{"idx": i, "t": round(i, 2), "path": p} for i, p in enumerate(meta_or_paths)]
    else:
        meta = meta_or_paths

    results = json.load(open(out_path)) if os.path.exists(out_path) else []
    done_idx = {r["idx"] for r in results}

    for m in meta:
        if m["idx"] in done_idx:
            continue
        rec = obs.ask(m["path"], t=m["t"], domain_hint=domain_hint)
        results.append({"idx": m["idx"], "t": m["t"], "raw": rec["raw"],
                         "confidence": rec["confidence"], **rec["mem"]})
        conf_str = " ".join(f"{k}={v['argmax']}({v['probs'].get(v['argmax'], 0):.2f})"
                             for k, v in rec["confidence"].items())
        print(f"  t={m['t']:>5}s: {conf_str}", flush=True)
        results.sort(key=lambda r: r["idx"])
        json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=2)
    return results


def cmd_run(args):
    """動画 -> フレーム抽出 -> VLM観察 -> 判定 を1コマンドで実行する(Macで完結)。"""
    from extract import extract_frames

    sop = load_sop(args.sop)
    os.makedirs(args.out_dir, exist_ok=True)
    frames_dir = os.path.join(args.out_dir, "frames")
    answer_log_path = os.path.join(args.out_dir, "answer_log.json")

    print(f"[run] 1/3 動画からフレーム抽出中... ({args.video})")
    meta = extract_frames(args.video, frames_dir, fps=args.fps)
    print(f"[run]   {len(meta)}フレーム -> {frames_dir}")

    print(f"[run] 2/3 VLMで観察中... (model={args.model})")
    _run_observer(sop, meta, args.model, answer_log_path)
    print(f"[run]   観察ログ -> {answer_log_path}")

    print("[run] 3/3 判定中...")
    result = judge(sop, load_answer_log(answer_log_path))
    _print_result(sop["sop"]["name"], result)


def cmd_observe(args):
    frame_paths = sorted(glob.glob(os.path.join(args.frames_dir, "*.jpg")))
    if not frame_paths:
        print(f"[observe] {args.frames_dir} に.jpgが見つかりません", file=sys.stderr)
        sys.exit(1)
    sop = load_sop(args.sop)
    meta = [{"idx": i, "t": round(i / args.fps, 2), "path": p} for i, p in enumerate(frame_paths)]
    _run_observer(sop, meta, args.model, args.out)
    print(f"[observe] saved -> {args.out}")


def cmd_judge(args):
    sop = load_sop(args.sop)
    result = judge(sop, load_answer_log(args.answer_log))
    _print_result(sop["sop"]["name"], result)


def main():
    ap = argparse.ArgumentParser(prog="python src/cli.py")
    sub = ap.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="動画→抽出→観察→判定を1コマンドで実行")
    p_run.add_argument("--sop", required=True)
    p_run.add_argument("--video", required=True)
    p_run.add_argument("--fps", type=float, default=1.0)
    p_run.add_argument("--model", default="4b", help="'2b'/'4b' またはHF/mlx-communityのモデルID")
    p_run.add_argument("--out-dir", required=True)
    p_run.set_defaults(func=cmd_run)

    p_obs = sub.add_parser("observe", help="Phase1のみ: 抽出済みフレームをVLMで観察(信頼度付き)")
    p_obs.add_argument("--sop", required=True)
    p_obs.add_argument("--frames-dir", required=True)
    p_obs.add_argument("--fps", type=float, default=1.0)
    p_obs.add_argument("--model", default="4b")
    p_obs.add_argument("--out", required=True)
    p_obs.set_defaults(func=cmd_observe)

    p_judge = sub.add_parser("judge", help="Phase2のみ: 観察ログをSOPと突き合わせて判定")
    p_judge.add_argument("--sop", required=True)
    p_judge.add_argument("--answer-log", required=True)
    p_judge.set_defaults(func=cmd_judge)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
