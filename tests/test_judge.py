"""judge の回帰テスト。

VLM(mlx_vlm)を必要としない — examples/konro_inspection/sample_output/answer_log.json は
実際にQwen3-VL-4Bで観察した本物のデータ(2026-07実行、runコマンドで生成)。
これに対してjudgeロジックだけを検証するので、GPUもモデルダウンロードも不要でCIで回せる。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from sop import load_sop, load_answer_log
from judge import judge

EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "konro_inspection"
ANSWER_LOG = EXAMPLE_DIR / "sample_output" / "answer_log.json"


def test_correct_sop_passes():
    sop = load_sop(EXAMPLE_DIR / "sop.yaml")
    frames = load_answer_log(ANSWER_LOG)
    result = judge(sop, frames)
    assert result.verdict == "PASS", result.violations
    assert result.coverage == 1.0
    assert result.violations == []


def test_wrong_order_sop_fails_with_correct_reason():
    sop = load_sop(EXAMPLE_DIR / "sop_wrong_order.yaml")
    frames = load_answer_log(ANSWER_LOG)
    result = judge(sop, frames)
    assert result.verdict == "FAIL"
    assert any("battery_check" in v and "ignite" in v for v in result.violations)


def test_missing_step_sop_fails_as_not_detected():
    sop = load_sop(EXAMPLE_DIR / "sop_missing_step.yaml")
    frames = load_answer_log(ANSWER_LOG)
    result = judge(sop, frames)
    assert result.verdict == "FAIL"
    assert result.events["gloves_check"] is None
    assert result.coverage < 1.0


def test_occurrence_is_order_independent():
    """events の宣言順を入れ替えても、occurrence指定があれば結果は変わらない
    (このセッションで見つかった脆さ: occurrence未指定だと宣言順が結果を左右してしまう)。
    """
    sop = load_sop(EXAMPLE_DIR / "sop.yaml")
    frames = load_answer_log(ANSWER_LOG)

    reordered = dict(sop)
    events = dict(sop["events"])
    # point2 を point1 より先に持ってくる(わざと逆順)
    reordered["events"] = {
        "point2": events["point2"], "point1": events["point1"],
        **{k: v for k, v in events.items() if k not in ("point1", "point2")},
    }

    r1 = judge(sop, frames)
    r2 = judge(reordered, frames)
    assert r1.events["point1"].t == r2.events["point1"].t
    assert r1.events["point2"].t == r2.events["point2"].t
    assert r1.verdict == r2.verdict == "PASS"
