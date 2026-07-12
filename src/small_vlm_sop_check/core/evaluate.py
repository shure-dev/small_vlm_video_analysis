"""正解アノテーション(ground_truth.json) × 回答ログ → 回答精度の評価。

一次指標はイベント区間の検出状態(match/miss/false_detection/true_absent)と
tIoU。境界の完全一致は要求しない(Ego4D等の時間的アクション検出と同じく、
許容誤差は注釈側ではなく指標のしきい値側で吸収する)。
フレーム回答の一致は参考値の診断層として別に出す。

ground_truth.json のスキーマ(sop-annotate が書き出す。v0.2):
  {
    "schema_version": "0.2",
    "sop_id": "konro_inspection",
    "fps": 1.0,
    "n_frames": 16,
    "events": {
      "pointing": [{"start_idx": 5, "end_idx": 5},     # 起きた区間(複数回なら複数)
                   {"start_idx": 12, "end_idx": 13}],
      "gloves": null                                    # 「起きていない」と注釈済み
      # キー自体が無い = 未注釈(評価から除外)
    }
  }
旧v0.1(値が単一の区間dict)も読み込み時にリストへ変換して受け付ける。

同一イベントの複数区間は、GT・検出の両方を開始時刻順に並べ、k番目どうしを
突き合わせる(余ったGT区間=miss、余った検出区間=false_detection)。
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .events import Run, detect_events


def _as_span_list(value: Any) -> list[dict] | None:
    """GTのevents値を正規化する: null / 区間dict(v0.1) / 区間リスト(v0.2)。"""
    if value is None:
        return None
    if isinstance(value, dict):
        return [value]
    return list(value)


def load_ground_truth(path: str | Path) -> dict[str, Any]:
    gt = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("fps", "n_frames", "events"):
        if key not in gt:
            raise ValueError(f"{path}: ground_truthに必須キー {key!r} がありません")
    for name, value in gt["events"].items():
        spans = _as_span_list(value)
        if spans is None:
            continue
        for span in spans:
            s, e = span.get("start_idx"), span.get("end_idx")
            if not (isinstance(s, int) and isinstance(e, int) and 0 <= s <= e < gt["n_frames"]):
                raise ValueError(f"{path}: events.{name} の区間が不正です: {span}")
        gt["events"][name] = sorted(spans, key=lambda sp: sp["start_idx"])
    return gt


def gt_runs(gt: dict[str, Any]) -> dict[str, list[Run] | None]:
    """正解区間を Run のリストに変換する(キーが無い=未注釈のイベントは含めない)。"""
    fps = gt["fps"]
    runs: dict[str, list[Run] | None] = {}
    for name, spans in gt["events"].items():
        if spans is None:
            runs[name] = None
            continue
        runs[name] = [Run(start_idx=sp["start_idx"], end_idx=sp["end_idx"],
                          t=round((sp["start_idx"] + sp["end_idx"]) / 2 / fps, 2),
                          hits=sp["end_idx"] - sp["start_idx"] + 1)
                      for sp in spans]
    return runs


def tiou(a: Run, b: Run) -> float:
    """フレームidx集合同士の temporal IoU。idxs(実際に一致したフレーム)を持つRunは
    その集合で数え、max_gapで橋渡しした隙間フレームは重なりにも母数にも入れない
    (yes,no,yes を3フレーム連続の検出として扱わない)。idxsが無いRun(正解区間など)は
    区間(両端含む)を連続集合とみなす。"""
    a_set = set(range(a.start_idx, a.end_idx + 1)) if a.idxs is None else set(a.idxs)
    b_set = set(range(b.start_idx, b.end_idx + 1)) if b.idxs is None else set(b.idxs)
    inter = len(a_set & b_set)
    if inter == 0:
        return 0.0
    return round(inter / len(a_set | b_set), 3)


def _event_rows(sop_def: dict, gts: dict[str, list[Run] | None],
                detected: dict[str, list[Run]]) -> list[dict]:
    """イベントごとの GT×検出 の突き合わせ(区間単位・時系列順ペアリング)。status:
    match(対応する区間あり) / miss(GT区間に対応する検出なし) /
    false_detection(GTに無い検出区間) / true_absent(両方なし) / no_gt(未注釈=評価対象外)
    """
    rows = []
    for ev in sop_def["events"]:
        name = ev["id"]
        det = sorted(detected.get(name, []), key=lambda r: r.start_idx)
        if name not in gts:
            rows.append({"event": name, "occurrence": None, "gt": None, "detected": None,
                         "tiou": None, "status": "no_gt"})
            continue
        gt_list = gts[name]
        if gt_list is None:
            if not det:
                rows.append({"event": name, "occurrence": None, "gt": None, "detected": None,
                             "tiou": None, "status": "true_absent"})
            else:
                for k, d in enumerate(det, 1):
                    rows.append({"event": name,
                                 "occurrence": k if len(det) > 1 else None,
                                 "gt": None,
                                 "detected": [d.start_idx, d.end_idx],
                                 "tiou": None, "status": "false_detection"})
            continue
        n = max(len(gt_list), len(det))
        for k in range(n):
            g = gt_list[k] if k < len(gt_list) else None
            d = det[k] if k < len(det) else None
            if g and d:
                status = "match"
            elif g:
                status = "miss"
            else:
                status = "false_detection"
            rows.append({
                "event": name,
                "occurrence": (k + 1) if n > 1 else None,
                "gt": [g.start_idx, g.end_idx] if g else None,
                "detected": [d.start_idx, d.end_idx] if d else None,
                "tiou": tiou(g, d) if (g and d) else None,
                "status": status,
            })
    return rows


def _frame_rows(sop_def: dict, gt: dict[str, Any], frames: list[dict]) -> list[dict]:
    """正解区間からフレームラベルを導出してVLM回答と突き合わせる(参考値)。

    イベントごとに、正例 = 注釈済み正解区間の和集合。区間外で yes と答えたら
    偽陽性と数える。この解釈は「全出現を注釈する」運用(annotatorの前提)でのみ正しい。
    """
    rows = []
    for ev in sop_def["events"]:
        name = ev["id"]
        if name not in gt["events"]:
            continue  # 未注釈イベントは導出できない
        spans = gt["events"][name] or []
        pos: set[int] = set()
        for sp in spans:
            pos.update(range(sp["start_idx"], sp["end_idx"] + 1))
        tp = sum(1 for f in frames if f["idx"] in pos and f["answers"].get(name) == "yes")
        fn = len(pos) - tp
        fp = sum(1 for f in frames if f["idx"] not in pos and f["answers"].get(name) == "yes")
        rows.append({
            "question": name, "value": "yes", "gt_frames": len(pos),
            "precision": round(tp / (tp + fp), 3) if (tp + fp) else None,
            "recall": round(tp / (tp + fn), 3) if pos else None,
            "false_positives": fp,
        })
    return rows


def evaluate(sop_def: dict[str, Any], gt: dict[str, Any],
             frames: list[dict]) -> dict[str, Any]:
    """回答ログ(frames)を正解アノテーション(gt)と突き合わせた評価一式を返す。"""
    detected = detect_events(sop_def["events"], frames, sop_def.get("defaults"))
    gts = gt_runs(gt)

    events = _event_rows(sop_def, gts, detected)
    frame_rows = _frame_rows(sop_def, gt, frames)

    matched = [r["tiou"] for r in events if r["tiou"] is not None]
    n_gt_present = sum(1 for r in events if r["status"] in ("match", "miss"))
    tiou_at = {f"tiou@{th}": sum(1 for t in matched if t >= th)
               for th in (0.1, 0.3, 0.5)}

    return {
        "events": events,
        "frames": frame_rows,
        "summary": {
            "mean_tiou": round(sum(matched) / len(matched), 3) if matched else None,
            **tiou_at,
            "n_gt_present": n_gt_present,
        },
    }


def format_report(ev: dict[str, Any]) -> str:
    """evaluate()の結果を人間向けのテキストにする。"""
    s = ev["summary"]
    lines = ["", "イベント区間 (正解 vs 検出):",
             f"{'event':16s} {'GT(idx)':>9s} {'検出(idx)':>9s} {'tIoU':>6s}  状態"]
    label = {"match": "✓ 検出", "miss": "✗ 見逃し", "false_detection": "✗ 誤検出",
             "true_absent": "✓ 正しく未検出", "no_gt": "- 未注釈"}
    for r in ev["events"]:
        fmt = lambda sp: f"{sp[0]}-{sp[1]}" if sp else "なし"
        ti = f"{r['tiou']:.2f}" if r["tiou"] is not None else "-"
        name = r["event"] + (f"[{r['occurrence']}]" if r["occurrence"] else "")
        lines.append(f"{name:16s} {fmt(r['gt']):>9s} {fmt(r['detected']):>9s}"
                     f" {ti:>6s}  {label[r['status']]}")
    if s["mean_tiou"] is not None:
        ths = "  ".join(f"{k.split('@')[1]}:{v}/{s['n_gt_present']}"
                        for k, v in s.items() if k.startswith("tiou@"))
        lines.append(f"mean tIoU = {s['mean_tiou']:.2f}   検出数(tIoU>=しきい値) {ths}")

    if ev["frames"]:
        lines += ["", "フレーム回答 (正解区間から導出・参考値):"]
        for r in ev["frames"]:
            p = f"{r['precision']:.2f}" if r["precision"] is not None else "  - "
            rc = f"{r['recall']:.2f}" if r["recall"] is not None else "  - "
            lines.append(f"  {r['question']}=={r['value']:8s} precision {p}  recall {rc}"
                         f"  (GT {r['gt_frames']}フレーム / 偽陽性 {r['false_positives']})")

    lines.append("")
    return "\n".join(lines)
