"""SOP定義ファイル(YAML)の読み込み・検証・書き戻し。

読み込み(load_sop)と検証(validate_sop)に加え、annotatorがブラウザから
SOPを編集するための決定論的なdict変換(set_domain_hint / upsert_event /
delete_event)と、原子的なYAML書き出し(save_sop)を提供する。

編集ヘルパーはsop_defを直接書き換えて返す。書き出しはPyYAMLの
safe_dumpを使うため 'yes'/'no' は自動でクォートされ、YAML 1.1の
ブール化(裸のyes/noがTrue/Falseになる)は起きない。
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import yaml

from .events import parse_clauses


REQUIRED_TOP_KEYS = ("sop", "questions", "events")


def validate_sop(doc: dict[str, Any], path: str | Path = "<sop>") -> dict[str, Any]:
    """SOP dictが最低限の構造を満たすか確認する(満たさなければValueError)。"""
    missing = [k for k in REQUIRED_TOP_KEYS if k not in doc]
    if missing:
        raise ValueError(f"{path}: 必須キーが不足しています: {missing}")
    if "id" not in doc["sop"] or "name" not in doc["sop"]:
        raise ValueError(f"{path}: sop.id / sop.name は必須です")
    if not doc["questions"]:
        raise ValueError(f"{path}: questions が空です(VLMへのプロンプトを生成できません)")
    if not doc["events"]:
        raise ValueError(f"{path}: events が空です(検出対象がありません)")
    return doc


def load_sop(path: str | Path) -> dict[str, Any]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return validate_sop(doc, path)


def save_sop(path: str | Path, sop_def: dict[str, Any]) -> None:
    """SOP dictを検証してYAMLへ原子的に書き込む(tmpに書いてから置き換え)。

    'yes'/'no' はsafe_dumpが自動でクォートするのでYAML 1.1のブール化は起きない。
    benchmarkブロック等の未知キーもそのまま保存される(dictを丸ごとdumpするため)。
    """
    validate_sop(sop_def, path)
    path = Path(path)
    text = yaml.safe_dump(sop_def, sort_keys=False, allow_unicode=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_answer_log(path: str | Path) -> list[dict[str, Any]]:
    """observe が出力したログを読み込み、detect_events が使う形に整形する。"""
    import json
    from ..inference.observe import confidence_to_answers

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    frames = []
    for r in raw:
        frames.append({"idx": r["idx"], "t": r["t"], "answers": confidence_to_answers(r["confidence"])})
    return frames


# ---------------------------------------------------------------------------
# SOP編集(annotatorがブラウザから呼ぶ決定論的なdict変換)
# ---------------------------------------------------------------------------
#
# UIで作るイベントは「1イベント = 1質問(yes/no)」の素直な対応にする:
#   event_id と同じidのquestionを yes/no で用意し、evidenceに <id>==yes を張る。
# 既存イベント(evidenceが複合条件やoccurrence付き)を編集するときは、
# evidence/occurrenceは保持し、name/min_frames/質問文だけを更新する。


def _primary_question_id(evidence: str) -> str:
    """evidence式(<id>==yes [and ...])の最初のquestion idを返す。"""
    return parse_clauses(evidence)[0][0]


def _ensure_question(sop_def: dict[str, Any], qid: str, ask: str) -> None:
    """指定idの質問が無ければ yes/no で追加。あればaskだけ更新する。"""
    for q in sop_def["questions"]:
        if q["id"] == qid:
            if ask:
                q["ask"] = ask
            return
    sop_def["questions"].append({"id": qid, "ask": ask, "values": ["yes", "no"]})


def _questions_referenced(sop_def: dict[str, Any]) -> set[str]:
    """いずれかのeventのevidenceから参照されている質問idの集合。"""
    used: set[str] = set()
    for spec in sop_def["events"].values():
        evidence = spec if isinstance(spec, str) else spec.get("evidence", "")
        if evidence:
            used.update(qid for qid, _ in parse_clauses(evidence))
    return used


def set_domain_hint(sop_def: dict[str, Any], hint: str) -> dict[str, Any]:
    """sop.domain_hint(撮影状況などのヒント文)を設定する。空文字ならキーごと削除。"""
    hint = (hint or "").strip()
    if hint:
        sop_def["sop"]["domain_hint"] = hint
    else:
        sop_def["sop"].pop("domain_hint", None)
    return sop_def


def upsert_event(sop_def: dict[str, Any], event_id: str, *, name: str | None = None,
                 ask: str | None = None, min_frames: int | None = None) -> dict[str, Any]:
    """イベントを追加、または既存イベントのname/質問文/min_framesを更新する。

    新規時は question(yes/no) を同idで用意し evidence に <id>==yes を張る。
    既存時は evidence/occurrence を保持し、渡された項目だけ更新する
    (name/min_framesはそのeventのspec、askはevidenceが指す質問のask)。
    """
    if not event_id or not event_id.isidentifier():
        raise ValueError(f"イベントidが不正です(識別子のみ可): {event_id!r}")
    events = sop_def["events"]
    existing = events.get(event_id)

    if existing is None:
        _ensure_question(sop_def, event_id, ask or "")
        spec: dict[str, Any] = {}
        if name:
            spec["name"] = name
        spec["evidence"] = f"{event_id}==yes"
        if min_frames is not None:
            spec["min_frames"] = min_frames
        events[event_id] = spec
    else:
        spec = {"evidence": existing} if isinstance(existing, str) else dict(existing)
        if name is not None:
            if name:
                spec["name"] = name
            else:
                spec.pop("name", None)
        if min_frames is not None:
            spec["min_frames"] = min_frames
        events[event_id] = spec
        if ask is not None:
            _ensure_question(sop_def, _primary_question_id(spec["evidence"]), ask)
    return sop_def


def delete_event(sop_def: dict[str, Any], event_id: str) -> bool:
    """イベントを削除する。そのeventだけが参照していた質問も併せて削除する。

    削除したらTrue、元から無ければFalse。最後の1イベントは削除しない
    (eventsが空だとSOPとして不正になるため)。
    """
    events = sop_def["events"]
    if event_id not in events:
        return False
    if len(events) <= 1:
        raise ValueError("最後のイベントは削除できません(eventsが空になります)")
    spec = events.pop(event_id)
    evidence = spec if isinstance(spec, str) else spec.get("evidence", "")
    if evidence:
        qid = _primary_question_id(evidence)
        if qid not in _questions_referenced(sop_def):
            sop_def["questions"] = [q for q in sop_def["questions"] if q["id"] != qid]
    return True
