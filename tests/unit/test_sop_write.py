"""save_sop と SOP編集ヘルパー(annotatorがブラウザから呼ぶ)の回帰テスト。

VLMもブラウザも不要。dict変換とYAML書き戻しの決定性だけを検証する。
"""
import copy

import pytest
import yaml

from small_vlm_sop_check.core.sop import (
    delete_event, load_sop, save_sop, set_domain_hint, upsert_event, validate_sop,
)


def _base_sop():
    return {
        "sop": {"id": "demo", "name": "Demo", "domain_hint": "工場の一人称視点"},
        "questions": [
            {"id": "assemble", "ask": "組み立てているか？", "values": ["yes", "no"]},
            {"id": "wrap", "ask": "袋を丸めているか？", "values": ["yes", "no"]},
        ],
        "events": {
            "assemble": {"name": "部品を組み立てる", "evidence": "assemble==yes", "min_frames": 4},
            "wrap": {"name": "袋を丸める", "evidence": "wrap==yes", "min_frames": 2},
        },
        "benchmark": {"status": "provisional", "version": "v001"},
    }


def test_save_sop_roundtrip_and_yes_no_quoting(tmp_path):
    """save→loadで同値に戻り、yes/no はブール化せず文字列のまま残る。"""
    sop = _base_sop()
    path = tmp_path / "sop" / "v001.yaml"
    save_sop(path, sop)

    text = path.read_text(encoding="utf-8")
    assert "'yes'" in text and "'no'" in text          # クォートされている
    reloaded = load_sop(path)
    assert reloaded == sop
    assert reloaded["questions"][0]["values"] == ["yes", "no"]
    assert all(isinstance(v, str) for v in reloaded["questions"][0]["values"])


def test_save_sop_preserves_unknown_blocks(tmp_path):
    """benchmarkブロック等の未知キーは書き戻しても保持される。"""
    sop = _base_sop()
    path = tmp_path / "v001.yaml"
    save_sop(path, sop)
    assert load_sop(path)["benchmark"] == {"status": "provisional", "version": "v001"}


def test_save_sop_is_atomic_no_tmp_left(tmp_path):
    """書き込み後に .tmp が残らない(原子的置き換え)。"""
    path = tmp_path / "v001.yaml"
    save_sop(path, _base_sop())
    assert not list(tmp_path.glob("*.tmp"))


def test_save_sop_rejects_invalid(tmp_path):
    """eventsが空など不正なSOPは書き込まず例外を投げる。"""
    sop = _base_sop()
    sop["events"] = {}
    with pytest.raises(ValueError):
        save_sop(tmp_path / "bad.yaml", sop)


def test_set_domain_hint_set_and_clear():
    sop = _base_sop()
    set_domain_hint(sop, "  新しいヒント  ")
    assert sop["sop"]["domain_hint"] == "新しいヒント"    # 前後空白は除去
    set_domain_hint(sop, "")
    assert "domain_hint" not in sop["sop"]                # 空文字でキーごと削除


def test_upsert_event_creates_event_and_question():
    """新規イベントは question(yes/no) と evidence=<id>==yes を自動生成する。"""
    sop = _base_sop()
    upsert_event(sop, "inspect", name="検査する", ask="検査しているか？", min_frames=3)

    assert sop["events"]["inspect"] == {
        "name": "検査する", "evidence": "inspect==yes", "min_frames": 3,
    }
    q = next(q for q in sop["questions"] if q["id"] == "inspect")
    assert q == {"id": "inspect", "ask": "検査しているか？", "values": ["yes", "no"]}


def test_upsert_event_updates_existing_without_clobbering_evidence():
    """既存イベントの編集は evidence を保持し name/min_frames/ask だけ更新する。"""
    sop = _base_sop()
    sop["events"]["assemble"]["evidence"] = "assemble==yes and wrap==no"  # 複合条件
    upsert_event(sop, "assemble", name="組立(改)", ask="組み立て中？", min_frames=6)

    assert sop["events"]["assemble"]["evidence"] == "assemble==yes and wrap==no"
    assert sop["events"]["assemble"]["name"] == "組立(改)"
    assert sop["events"]["assemble"]["min_frames"] == 6
    assert next(q for q in sop["questions"] if q["id"] == "assemble")["ask"] == "組み立て中？"


def test_upsert_event_rejects_bad_id():
    with pytest.raises(ValueError):
        upsert_event(_base_sop(), "not an id", name="x")


def test_delete_event_removes_event_and_orphan_question():
    """削除するとeventと、他eventが参照しない質問も消える。"""
    sop = _base_sop()
    assert delete_event(sop, "wrap") is True
    assert "wrap" not in sop["events"]
    assert all(q["id"] != "wrap" for q in sop["questions"])     # orphan質問も削除
    assert "assemble" in sop["events"]                           # 残りは無傷


def test_delete_event_keeps_shared_question():
    """他イベントがまだ参照している質問は残す。"""
    sop = _base_sop()
    # もう1つのeventが assemble 質問を参照
    sop["events"]["assemble2"] = {"name": "再組立", "evidence": "assemble==yes", "occurrence": 2}
    assert delete_event(sop, "assemble") is True
    assert any(q["id"] == "assemble" for q in sop["questions"])  # 共有質問は残る


def test_delete_event_missing_returns_false():
    assert delete_event(_base_sop(), "nope") is False


def test_delete_last_event_refused():
    sop = _base_sop()
    delete_event(sop, "wrap")
    with pytest.raises(ValueError):
        delete_event(sop, "assemble")   # 最後の1件は消せない


def test_validate_sop_accepts_base():
    assert validate_sop(copy.deepcopy(_base_sop())) is not None
