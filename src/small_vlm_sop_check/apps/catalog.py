"""アノテーション対象unitの台帳(datasets/*/units/*/meta.json を走査)。

annotatorがブラウザ上でデータセット→unitを切り替えられるよう、各unitの
SOP・フレーム・fps・人手GT保存先を1か所に集める。konroとfactory_egoで
meta.jsonのスキーマが少し違う(sop_refs=リスト vs sop_ref=dict、
ground_truth_refの有無)ため、その差はここで吸収する。
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path


GT_REVISION = "human-v001"   # 人手GTのリビジョンディレクトリ(datasets契約で固定)


@dataclass
class Unit:
    """1 unit(1本のクリップ)の注釈に必要なパス一式。"""
    dataset: str
    unit_id: str
    sop_path: Path
    frames_dir: Path
    fps: float
    gt_path: Path
    meta_path: Path | None = None    # 参考情報(transcript等)の読み出し元。adhocはNone

    def frame_files(self) -> list[str]:
        """連番フレーム(f000.jpg / f0000.jpg)をファイル名順に返す。"""
        return sorted(p.name for p in self.frames_dir.glob("f*.jpg"))

    def has_frames(self) -> bool:
        return any(self.frames_dir.glob("f*.jpg"))

    def has_gt(self) -> bool:
        return self.gt_path.exists()

    def summary(self) -> dict:
        """/api/units 用の軽い要約(GET一覧でフレームは読み込まない)。"""
        return {
            "dataset": self.dataset,
            "unit_id": self.unit_id,
            "fps": self.fps,
            "has_frames": self.has_frames(),
            "has_gt": self.has_gt(),
        }


def _sop_rel(meta: dict) -> str:
    """meta.json の sop_ref(dict) / sop_refs(リスト) / 文字列 から相対パスを取り出す。"""
    ref = meta.get("sop_ref", meta.get("sop_refs"))
    if isinstance(ref, dict):
        return ref["path"]
    if isinstance(ref, (list, tuple)):
        if not ref:
            raise ValueError("sop_refs が空です")
        first = ref[0]
        return first["path"] if isinstance(first, dict) else first
    if isinstance(ref, str):
        return ref
    raise ValueError("meta.json に sop_ref / sop_refs がありません")


def _gt_path(meta: dict, unit_dir: Path, dataset_root: Path, unit_id: str) -> Path:
    """人手GTの保存先。meta.ground_truth_ref があればそれ、無ければ規約のパス。"""
    ref = meta.get("ground_truth_ref")
    if ref:
        return (unit_dir / ref).resolve()
    return dataset_root / "annotations" / GT_REVISION / f"{unit_id}.json"


def unit_from_meta(meta_path: Path) -> Unit:
    """meta.json 1件から Unit を組み立てる(パスはすべて絶対に解決)。"""
    unit_dir = meta_path.parent
    dataset_root = unit_dir.parents[1]          # <dataset>/units/<unit>/meta.json
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    dataset = meta.get("dataset_id") or dataset_root.name
    unit_id = meta.get("unit_id", unit_dir.name)
    sampling = meta.get("sampling", {})
    return Unit(
        dataset=dataset,
        unit_id=unit_id,
        sop_path=(unit_dir / _sop_rel(meta)).resolve(),
        frames_dir=(unit_dir / sampling.get("frame_path", "frames")).resolve(),
        fps=float(sampling.get("fps", 1.0)),
        gt_path=_gt_path(meta, unit_dir, dataset_root, unit_id),
        meta_path=meta_path.resolve(),
    )


def adhoc_unit(unit_id: str, sop_path: Path, frames_dir: Path,
               fps: float, gt_path: Path) -> Unit:
    """CLIで --sop/--frames-dir を明示したとき用の、台帳に無い単発unit。"""
    return Unit("custom", unit_id, Path(sop_path).resolve(),
                Path(frames_dir).resolve(), fps, Path(gt_path).resolve())


class Catalog:
    """unitの一覧と、unit_idでの引き当てを提供する。"""

    def __init__(self, units: list[Unit]):
        # 同じunit_idが複数あっても最初の1件を採用(現状unit_idはグローバルに一意)
        self.units = units
        self._by_id: dict[str, Unit] = {}
        for u in units:
            self._by_id.setdefault(u.unit_id, u)

    def get(self, unit_id: str) -> Unit | None:
        return self._by_id.get(unit_id)

    def summaries(self) -> list[dict]:
        return [u.summary() for u in self.units]

    def datasets(self) -> list[str]:
        seen: list[str] = []
        for u in self.units:
            if u.dataset not in seen:
                seen.append(u.dataset)
        return seen


def discover(root: Path, extra: Unit | None = None) -> Catalog:
    """datasets/*/units/*/meta.json を走査して台帳を作る。

    dataset名→unit_id の順に安定ソートする。extra(CLI指定の単発unit)が
    あれば先頭に足す。壊れたmeta.jsonは台帳から静かに除外する
    (1件の不整合で全体が起動できなくなるのを防ぐ)。
    """
    units: list[Unit] = []
    for meta_path in sorted((root / "datasets").glob("*/units/*/meta.json")):
        try:
            units.append(unit_from_meta(meta_path))
        except (KeyError, ValueError, json.JSONDecodeError):
            continue
    units.sort(key=lambda u: (u.dataset, u.unit_id))
    if extra is not None:
        # 同一unit_idが台帳にもあれば、明示指定(extra)を優先する
        units = [extra] + [u for u in units if u.unit_id != extra.unit_id]
    return Catalog(units)
