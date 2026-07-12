"""detect_events(回答ログ→イベント区間リスト)の回帰テスト。

VLM(mlx_vlm)を必要としない — datasets/konro_inspection の固定回答ログは
実際にQwen3-VL-4Bが回答した本物のデータ(2026-07実行、runコマンドで生成)。
これに対して区間検出ロジックだけを検証するので、GPUもモデルダウンロードも不要でCIで回せる。
"""
from pathlib import Path

from small_vlm_sop_check.core.events import detect_events
from small_vlm_sop_check.core.sop import load_answer_log, load_sop

DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets" / "konro_inspection"
SOP_PATH = DATASET_DIR / "sops" / "konro_inspection" / "konro_inspection.yaml"
ANSWER_LOG = DATASET_DIR / "fixtures" / "reference_outputs" / "answer_log.json"


def _detect(sop, frames):
    return detect_events(sop["events"], frames, sop.get("defaults"))


def test_reference_log_detects_expected_spans():
    """基準の回答ログ(Qwen3-VL-4B)から、5工程すべての区間が検出され、
    動画に存在しない動作(gloves)は検出されない。
    pointing(指差し)は動画内で2回起きるので、区間が2つ検出される。"""
    sop = load_sop(SOP_PATH)
    events = _detect(sop, load_answer_log(ANSWER_LOG))

    spans = {name: [(r.start_idx, r.end_idx) for r in runs]
             for name, runs in events.items()}
    assert spans == {
        "knob": [(1, 5)],
        "flame": [(3, 3)],
        "pointing": [(4, 5), (10, 14)],
        "grill": [(7, 8)],
        "battery": [(12, 13)],
        "gloves": [],
    }


def test_detected_spans_are_in_temporal_order():
    """複数回起きるイベントの区間は、常に時系列順で返る。"""
    sop = load_sop(SOP_PATH)
    events = _detect(sop, load_answer_log(ANSWER_LOG))
    starts = [r.start_idx for r in events["pointing"]]
    assert starts == sorted(starts)


def test_all_no_answers_detect_nothing():
    """検出コードが「やった」とごまかさないこと: 全フレームnoならすべて未検出。"""
    sop = load_sop(SOP_PATH)
    frames = load_answer_log(ANSWER_LOG)
    for f in frames:
        f["answers"] = {q: "no" for q in f["answers"]}
    events = _detect(sop, frames)
    assert all(runs == [] for runs in events.values())


def test_min_frames_filters_single_frame_runs():
    """min_frames:2 のイベントは1フレームだけの一致では検出されない。"""
    sop = load_sop(SOP_PATH)
    frames = load_answer_log(ANSWER_LOG)
    for f in frames:                       # knob==yes を idx=3 の1フレームだけに潰す
        f["answers"]["knob"] = "yes" if f["idx"] == 3 else "no"
    events = _detect(sop, frames)
    assert events["knob"] == []


def test_declaration_order_does_not_change_results():
    """events の宣言順を入れ替えても検出結果は変わらない
    (各イベントは独立に自分の回答列だけを見るため)。"""
    sop = load_sop(SOP_PATH)
    frames = load_answer_log(ANSWER_LOG)

    r1 = detect_events(sop["events"], frames, sop.get("defaults"))
    r2 = detect_events(list(reversed(sop["events"])), frames, sop.get("defaults"))
    assert {k: [(x.start_idx, x.end_idx) for x in v] for k, v in r1.items()} \
        == {k: [(x.start_idx, x.end_idx) for x in v] for k, v in r2.items()}
