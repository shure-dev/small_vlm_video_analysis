"""observe/judge の結果を、フレーム画像と一緒に再生できる1枚のHTMLにまとめる。

なぜ作ったか:
  ターミナルの表だけでは「結局PASSなのかFAILなのか」「VLMは本当は何と答えたのか」が
  パッと見で分かりにくい。この使い捨てツールは、動画のように再生しながら
  「今どのフレームで」「VLMは各質問にyes/no/unclearのどれと答え」「どのイベントが
  検出/進行中で」「最終的にPASS/FAILか」を1画面で見られるようにする。

出力は依存ファイルの一切ないHTML1枚(フレーム画像もbase64で埋め込み済み)。
ダブルクリックで開くだけで動く。サーバ不要・fetch不要。

使い方:
  python tools/replay_viewer/build.py
  # デフォルトで examples/konro_inspection/ の同梱データ(sop.yaml最新版)を使う。
  # 別の判定(誤った手順など)や別の実行結果を見たい場合は引数で差し替え可能:
  python tools/replay_viewer/build.py \
    --sop examples/konro_inspection/sop_wrong_order.yaml \
    --answer-log examples/konro_inspection/sample_output/answer_log.json \
    --frames-dir examples/konro_inspection/sample_output/frames \
    --out tools/replay_viewer/replay_wrong_order.html
"""
from __future__ import annotations
import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # リポジトリルート
sys.path.insert(0, str(ROOT / "src"))

from sop import load_sop  # noqa: E402
from judge import judge, parse_clauses  # noqa: E402


def _confidence_to_answers(confidence: dict) -> dict[str, str]:
    return {qid: c["argmax"] for qid, c in confidence.items()}


def build_data(sop_path: Path, answer_log_path: Path, frames_dir: Path) -> dict:
    sop_def = load_sop(sop_path)
    raw_log = json.loads(answer_log_path.read_text(encoding="utf-8"))

    frames = []
    for r in raw_log:
        idx = r["idx"]
        img_path = frames_dir / f"f{idx:03d}.jpg"
        b64 = base64.b64encode(img_path.read_bytes()).decode("ascii") if img_path.exists() else ""
        frames.append({
            "idx": idx,
            "t": r["t"],
            "image": f"data:image/jpeg;base64,{b64}" if b64 else "",
            "raw": r.get("raw", ""),
            "answers": _confidence_to_answers(r.get("confidence", {})),
            "probs": {qid: c["probs"] for qid, c in r.get("confidence", {}).items()},
        })

    # judge() 用に answers 形式へ変換したフレーム列を作って実際に判定する
    judge_frames = [{"idx": f["idx"], "t": f["t"], "answers": f["answers"]} for f in frames]
    result = judge(sop_def, judge_frames)

    events = {}
    for name, spec in sop_def["events"].items():
        evidence = spec if isinstance(spec, str) else spec["evidence"]
        run = result.events.get(name)
        events[name] = {
            "evidence": evidence,
            "start_idx": run.start_idx if run else None,
            "end_idx": run.end_idx if run else None,
            "t": run.t if run else None,
        }

    return {
        "sop": {"id": sop_def["sop"]["id"], "name": sop_def["sop"]["name"]},
        "questions": sop_def["questions"],
        "relations": sop_def.get("relations", []),
        "verdict": result.verdict,
        "coverage": result.coverage,
        "violations": result.violations,
        "events": events,
        "n_frames": len(frames),
        "frames": frames,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sop", default=str(ROOT / "examples/konro_inspection/sop.yaml"))
    ap.add_argument("--answer-log", default=str(ROOT / "examples/konro_inspection/sample_output/answer_log.json"))
    ap.add_argument("--frames-dir", default=str(ROOT / "examples/konro_inspection/sample_output/frames"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "replay.html"))
    args = ap.parse_args()

    data = build_data(Path(args.sop), Path(args.answer_log), Path(args.frames_dir))

    template = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # </script>混入対策
    html = template.replace('"__REPLAY_DATA__"', data_json)

    out_path = Path(args.out)
    out_path.write_text(html, encoding="utf-8")
    print(f"[replay_viewer] {out_path} を書き出しました "
          f"({data['n_frames']}フレーム, 判定={data['verdict']})")


if __name__ == "__main__":
    main()
