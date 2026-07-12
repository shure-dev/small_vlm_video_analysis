"""SOPイベント定義 × 回答ログ → イベント区間の検出（決定論的・ルールベース）。

設計思想（experiments/sop_step_detect/confidence_judge/ での実験で確立）:
  質問への回答はVLMにやらせるが、回答列から「いつ何が起きたか(区間)」を導出する
  部分は、VLM(自然文推論)に投げるとよくある単純な数値・順序比較すら
  間違えることが実験で確認された。したがって導出は常にこの決定的なコードで行う。

イベント = 質問。フレーム回答が "yes" のフレームの連なりが、そのイベントの出現区間。
同じイベントが動画内で複数回起こる場合は、検出も複数区間のリストとして返す
（旧形式の evidence 式・occurrence による兄弟イベントは廃止した）。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class Run:
    start_idx: int
    end_idx: int
    t: float       # 区間内フレームの時刻の平均(代表時刻)
    hits: int
    idxs: tuple[int, ...] | None = None  # 実際に一致したフレームidx(max_gapで橋渡しした隙間は含まない)。
                                         # None = 不明(正解区間のように連続とみなす場合)


def find_runs(frames: list[dict], event_id: str,
              min_frames: int = 1, max_gap: int = 0) -> list[Run]:
    """回答が "yes" の極大区間を探す。不一致(unclear/no)を max_gap フレームまで橋渡しする
    (VLM推論の孤立した誤検出・ブレを吸収するノイズ耐性)。
    frames: [{"idx": int, "t": float, "answers": {event_id: value, ...}}, ...]
    """
    runs, cur_hits, gap = [], [], 0
    for f in frames:
        if f["answers"].get(event_id) == "yes":
            cur_hits.append((f["idx"], f["t"]))
            gap = 0
        elif cur_hits and gap < max_gap:
            gap += 1
        else:
            if cur_hits:
                runs.append(cur_hits)
            cur_hits, gap = [], 0
    if cur_hits:
        runs.append(cur_hits)

    out = []
    for r in runs:
        if len(r) < min_frames:
            continue
        idxs = [i for i, _ in r]
        ts = [t for _, t in r]
        out.append(Run(start_idx=min(idxs), end_idx=max(idxs),
                        t=round(sum(ts) / len(ts), 2), hits=len(r), idxs=tuple(idxs)))
    return out


def detect_events(events: list[dict[str, Any]], frames: list[dict],
                  defaults: dict[str, Any] | None = None) -> dict[str, list[Run]]:
    """SOPの events: を評価し、各イベントid -> 出現区間のリスト(時系列順) を返す。

    リストが空 = そのイベントは検出されなかった。min_frames / max_gap_frames は
    イベント個別指定 > defaults > 組み込み既定(2 / 2) の順で決まる。
    """
    defaults = defaults or {}
    result: dict[str, list[Run]] = {}
    for ev in events:
        min_frames = ev.get("min_frames", defaults.get("min_frames", 2))
        max_gap = ev.get("max_gap_frames", defaults.get("max_gap_frames", 2))
        result[ev["id"]] = find_runs(frames, ev["id"], min_frames=min_frames, max_gap=max_gap)
    return result
