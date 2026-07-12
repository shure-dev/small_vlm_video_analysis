"""evaluate(正解アノテーションとの突き合わせ)の回帰テスト。VLM不要。

回答ログは test_events.py と同じ実データ(Qwen3-VL-4B)。正解アノテーションは
「人間が付けたらこうなる」体の合成フィクスチャで、基準検出(knob 1-5 / flame 3-3 /
pointing 4-5,10-14 / grill 7-8 / battery 12-13 / gloves なし)と境界を
わざと1〜2フレームずらしてある。境界のズレは注釈側でなくtIoUしきい値側で吸収する、
という設計上の主張をここで固定する。
"""
import json
from pathlib import Path

import pytest

from small_vlm_sop_check.core.evaluate import evaluate, load_ground_truth, tiou
from small_vlm_sop_check.core.events import Run
from small_vlm_sop_check.core.sop import load_answer_log, load_sop

DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets" / "konro_inspection"
SOP = DATASET_DIR / "sops" / "konro_inspection" / "konro_inspection.yaml"
ANSWER_LOG = DATASET_DIR / "fixtures" / "reference_outputs" / "answer_log.json"


def make_gt(events: dict) -> dict:
    return {"schema_version": "0.2", "sop_id": "konro_inspection",
            "fps": 1.0, "n_frames": 16, "events": events}


GT_EVENTS = {
    "knob":     [{"start_idx": 1, "end_idx": 4}],    # 検出1-5 -> tIoU 0.8
    "flame":    [{"start_idx": 3, "end_idx": 3}],    # 一致 -> 1.0
    "pointing": [{"start_idx": 4, "end_idx": 5},     # 一致 -> 1.0
                 {"start_idx": 10, "end_idx": 13}],  # 検出10-14だが実一致は{10,12,13,14}(11は橋渡し) -> 0.6
    "grill":    [{"start_idx": 6, "end_idx": 8}],    # 検出7-8 -> 2/3
    "battery":  [{"start_idx": 12, "end_idx": 13}],  # 一致 -> 1.0
    "gloves":   None,                                # 起きていない(注釈済み)
}


def _row(ev, name, occurrence=None):
    return next(r for r in ev["events"]
                if r["event"] == name and r["occurrence"] == occurrence)


def test_tiou_math():
    r = lambda s, e: Run(start_idx=s, end_idx=e, t=0, hits=e - s + 1)
    assert tiou(r(1, 5), r(1, 5)) == 1.0
    assert tiou(r(0, 2), r(5, 8)) == 0.0
    assert tiou(r(1, 4), r(1, 5)) == 0.8       # 4/5
    assert tiou(r(6, 8), r(7, 8)) == 0.667     # 2/3
    # 検出が飛び飛び(yes,no,yes)の場合、橋渡しした隙間フレームは重なりにも母数にも入れない
    gappy = Run(start_idx=1, end_idx=5, t=0, hits=3, idxs=(1, 2, 5))
    assert tiou(r(1, 4), gappy) == 0.4         # {1,2} / {1,2,3,4,5}


def test_boundary_shift_reduces_tiou_but_stays_above_threshold():
    """境界が1〜2フレームずれた注釈: tIoUは1.0を切るが、ゆるいしきい値は全区間が超える。
    「境界ズレは注釈でなくしきい値側で吸収する」という切り分けの根拠。
    pointingは2回起きるので区間単位で2行になり、k番目どうしが突き合う。"""
    sop = load_sop(SOP)
    ev = evaluate(sop, make_gt(GT_EVENTS), load_answer_log(ANSWER_LOG))
    s = ev["summary"]

    assert _row(ev, "knob")["tiou"] == 0.8
    assert _row(ev, "grill")["tiou"] == 0.667
    assert _row(ev, "pointing", 1)["tiou"] == 1.0
    assert _row(ev, "pointing", 2)["tiou"] == 0.6   # 橋渡しフレーム(11)を重なりに数えない
    assert _row(ev, "gloves")["status"] == "true_absent"
    assert all(r["status"] in ("match", "true_absent") for r in ev["events"])

    assert s["mean_tiou"] < 1.0                      # 境界ズレはtIoUに出る
    assert s["tiou@0.3"] == s["n_gt_present"] == 6   # 全6区間がゆるいしきい値は超える


def test_miss_and_false_detection_statuses():
    """注釈と検出が食い違うケース: 見逃し(miss)・誤検出(false_detection)が区別される。"""
    sop = load_sop(SOP)
    events = dict(GT_EVENTS)
    events["gloves"] = [{"start_idx": 0, "end_idx": 1}]   # 起きたと注釈(検出は無し)
    events["battery"] = None                              # 起きてないと注釈(検出は有り)
    ev = evaluate(sop, make_gt(events), load_answer_log(ANSWER_LOG))

    assert _row(ev, "gloves")["status"] == "miss"
    assert _row(ev, "battery")["status"] == "false_detection"


def test_extra_occurrence_counts_as_miss():
    """GT側が3回、検出が2回なら、3回目の区間はmissになる(区間単位のペアリング)。"""
    sop = load_sop(SOP)
    events = dict(GT_EVENTS)
    events["pointing"] = [{"start_idx": 4, "end_idx": 5},
                          {"start_idx": 10, "end_idx": 13},
                          {"start_idx": 15, "end_idx": 15}]   # 3回目(検出は2回しかない)
    ev = evaluate(sop, make_gt(events), load_answer_log(ANSWER_LOG))
    assert _row(ev, "pointing", 3)["status"] == "miss"
    assert _row(ev, "pointing", 1)["status"] == "match"


def test_unannotated_event_is_excluded():
    """キーごと無い(未注釈)イベントは no_gt となり、tIoUの母数に入らない。"""
    sop = load_sop(SOP)
    events = {k: v for k, v in GT_EVENTS.items() if k != "flame"}
    ev = evaluate(sop, make_gt(events), load_answer_log(ANSWER_LOG))

    assert _row(ev, "flame")["status"] == "no_gt"
    assert _row(ev, "flame")["tiou"] is None
    assert ev["summary"]["n_gt_present"] == 5


def test_frame_level_diagnostics_derived_from_gt():
    """イベントごとのフレーム診断が正解区間から導出される。
    pointingは2回起きるので、正例は両区間の和集合になる。"""
    sop = load_sop(SOP)
    ev = evaluate(sop, make_gt(GT_EVENTS), load_answer_log(ANSWER_LOG))
    rows = {(r["question"], r["value"]): r for r in ev["frames"]}

    assert rows[("pointing", "yes")]["gt_frames"] == 2 + 4     # 4-5 と 10-13 の和集合
    assert rows[("gloves", "yes")]["gt_frames"] == 0           # null注釈 -> 正例なし
    for r in ev["frames"]:
        for key in ("precision", "recall"):
            assert r[key] is None or 0.0 <= r[key] <= 1.0


def test_load_ground_truth_accepts_v01_dict_spans(tmp_path):
    """旧v0.1(単一区間dict)のGTも読み込み時にリストへ正規化される。"""
    doc = {"schema_version": "0.1", "sop_id": "x", "fps": 1.0, "n_frames": 16,
           "events": {"knob": {"start_idx": 1, "end_idx": 4}, "gloves": None}}
    p = tmp_path / "gt.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    gt = load_ground_truth(p)
    assert gt["events"]["knob"] == [{"start_idx": 1, "end_idx": 4}]
    assert gt["events"]["gloves"] is None


def test_load_ground_truth_rejects_bad_span(tmp_path):
    bad = make_gt({"knob": [{"start_idx": 5, "end_idx": 2}]})
    p = tmp_path / "gt.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_ground_truth(p)
