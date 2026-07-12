"""イベント区間アノテーションツール(標準ライブラリのみ・自動保存)。

なにをするか:
  抽出済みフレームをブラウザに並べ、SOPの各イベントについて「実際に起きた区間」を
  タイムライン上のドラッグ、または開始・終了フレームの指定で注釈する。付けた注釈は
  操作のたびに即 ground_truth.json へ保存される(保存ボタンは無い)。
  ヘッダのプルダウンで データセット → unit を切り替えられるので、複数unitを
  1プロセスで続けて注釈できる。途中で閉じても再開できる。

  イベントの追加・削除、日本語ラベルや質問文、撮影状況のヒント(domain_hint)は
  ブラウザ上で編集でき、SOP YAML へ原子的に書き戻される(検証付き)。

注釈するのは事実(いつ何が起きたか=区間)だけ。評価(tIoU・フレーム一致)は
`sop-check eval` が行う。

使い方:
  sop-annotate            # datasets/ 配下のunitを台帳化して一覧から選ぶ
  # 台帳に無い単発unitを直接指定して開く:
  sop-annotate --sop path/to/sop.yaml --frames-dir path/to/frames
               --fps 2.0 --out path/to/ground_truth.json

前提: フレームは extract.py が吐く連番jpg(f000.jpg, ...)で、t = idx / fps とみなす。
同じ動作が動画内で複数回起こる場合は、同じレーンに区間を複数引くだけでよい
(GTには同じイベントidの区間リストとして時系列順に保存される)。
"""
from __future__ import annotations
import argparse
import json
import os
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from ..core.sop import (delete_event, load_sop, rename_event, save_sop,
                        set_domain_hint, upsert_event)
from . import catalog
from .resources import repository_root, template_text


ROOT = repository_root()
DEMO_ROOT = ROOT / "datasets" / "konro_inspection"
DEFAULT_SOP = DEMO_ROOT / "sops" / "konro_inspection" / "konro_inspection.yaml"
DEFAULT_FRAMES = DEMO_ROOT / "units" / "konro_inspection" / "frames"
DEFAULT_GT = DEMO_ROOT / "annotations" / "human-v001" / "konro_inspection.json"
PREFERRED_INITIAL = "konro_inspection"   # 引数なし起動時に最初に開くunit(あれば)


def display_path(p: Path) -> str:
    """ヘッダー表示用の短いパス(カレントディレクトリ相対。外なら絶対のまま)。"""
    try:
        return str(p.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(p)


# ---------------------------------------------------------------------------
# unitのページデータ組み立て(GET /api/unit/<id>、初期bootで使う)
# ---------------------------------------------------------------------------

def _events_view(sop_def: dict) -> list[dict]:
    """events定義を、UIが必要とする形(id・質問文・min_frames)に展開する。"""
    return [{"id": ev["id"], "question": ev.get("ask", ""),
             "min_frames": ev.get("min_frames")} for ev in sop_def["events"]]


def _reference_info(meta_path: Path | None) -> dict | None:
    """meta.json の selection から、注釈の手がかりになる読み取り専用情報を取り出す。

    factory_ego は上流のLLM生成transcript/活動列を持つ(GTではないが撮影状況の参考)。
    konro など持たないunitでは None。
    """
    if not meta_path or not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sel = meta.get("selection", {})
    ref = {}
    for key in ("main_process", "transcript_excerpt", "window_activities"):
        if sel.get(key):
            ref[key] = sel[key]
    return ref or None


def build_unit_data(unit: catalog.Unit) -> dict:
    """1 unit ぶんのページデータ(SOP全量・フレーム・保存済み注釈・参考情報)。"""
    sop_def = load_sop(unit.sop_path)
    frame_files = unit.frame_files()
    gt_events = {}
    if unit.gt_path.exists():
        gt_events = json.loads(unit.gt_path.read_text(encoding="utf-8")).get("events", {})
        # 旧v0.1(単一区間dict)は区間リストへ正規化してUIに渡す
        gt_events = {k: ([v] if isinstance(v, dict) else v) for k, v in gt_events.items()}
    return {
        "unit_id": unit.unit_id,
        "dataset": unit.dataset,
        "fps": unit.fps,
        "n_frames": len(frame_files),
        "sop": {
            "id": sop_def["sop"]["id"],
            "name": sop_def["sop"]["name"],
            "domain_hint": sop_def["sop"].get("domain_hint", ""),
        },
        "events": _events_view(sop_def),
        "frames": frame_files,
        "times": [round(i / unit.fps, 2) for i in range(len(frame_files))],
        "gt_events": gt_events,
        "reference": _reference_info(unit.meta_path),
        "out_path": display_path(unit.gt_path),
    }


# ---------------------------------------------------------------------------
# 保存(検証付き・原子的)。GTとSOPのどちらもtmp→os.replaceで書き込む
# ---------------------------------------------------------------------------

def validate_gt_events(sop_def: dict, frame_count: int, events: dict) -> None:
    """GTのeventsが、SOPの既知イベントかつ有効な区間リスト(各区間 0<=s<=e<n)かを確認する。

    値は null(起きていない) または 区間のリスト。同じイベントが複数回起きたら複数区間。
    """
    known = {ev["id"] for ev in sop_def["events"]}
    for name, spans in events.items():
        if name not in known:
            raise ValueError(f"SOPに無いイベント: {name}")
        if spans is None:
            continue
        if not isinstance(spans, list) or not spans:
            raise ValueError(f"{name} は区間のリストかnullで指定します: {spans!r}")
        for span in spans:
            s, e = span.get("start_idx"), span.get("end_idx")
            if not (isinstance(s, int) and isinstance(e, int) and 0 <= s <= e < frame_count):
                raise ValueError(f"{name} の区間が不正: {span}")


def save_gt(unit: catalog.Unit, sop_def: dict, events: dict) -> None:
    # 区間は常に時系列順で保存する(k番目=k回目)
    events = {k: (sorted(v, key=lambda sp: sp["start_idx"]) if isinstance(v, list) else v)
              for k, v in events.items()}
    n = len(unit.frame_files())
    validate_gt_events(sop_def, n, events)
    doc = {
        "schema_version": "0.2",
        "sop_id": sop_def["sop"]["id"],
        "fps": unit.fps,
        "n_frames": n,
        "annotated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": events,
    }
    unit.gt_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = unit.gt_path.parent / (unit.gt_path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, unit.gt_path)


def _drop_gt_key(unit: catalog.Unit, sop_def: dict, event_id: str) -> None:
    """SOPからイベントを消したとき、GT側の同キーもカスケード削除して不整合を残さない。"""
    if not unit.gt_path.exists():
        return
    doc = json.loads(unit.gt_path.read_text(encoding="utf-8"))
    if event_id in doc.get("events", {}):
        doc["events"].pop(event_id)
        save_gt(unit, sop_def, doc["events"])


def _rename_gt_key(unit: catalog.Unit, sop_def: dict, old_id: str, new_id: str) -> None:
    """イベントidの変更にGT側のキーも追随させる(注釈を失わない)。"""
    if not unit.gt_path.exists():
        return
    doc = json.loads(unit.gt_path.read_text(encoding="utf-8"))
    events = doc.get("events", {})
    if old_id in events:
        events = {new_id if k == old_id else k: v for k, v in events.items()}
        save_gt(unit, sop_def, events)


# ---------------------------------------------------------------------------
# HTTPサーバ
# ---------------------------------------------------------------------------

class Annotator(ThreadingHTTPServer):
    """台帳(catalog)を保持し、書き込みをLockで直列化するHTTPサーバ。"""

    def __init__(self, addr, cat: catalog.Catalog, initial: str | None):
        super().__init__(addr, Handler)
        self.catalog = cat
        self.initial = initial
        self.write_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server: Annotator

    def log_message(self, fmt, *args):  # フレーム毎のGETでターミナルを埋めない
        pass

    # --- 応答ヘルパ ---------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

    def _read_json(self) -> dict:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        return json.loads(body)

    # --- GET ---------------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._serve_index()
        elif path == "/api/units":
            self._send_json({"units": self.server.catalog.summaries(),
                             "datasets": self.server.catalog.datasets()})
        elif path.startswith("/api/unit/"):
            self._serve_unit(unquote(path[len("/api/unit/"):]))
        elif path.startswith("/frames/"):
            self._serve_frame(path[len("/frames/"):])
        else:
            self._send(404, b"not found", "text/plain")

    def _serve_index(self):
        cat = self.server.catalog
        initial = self.server.initial
        boot = {
            "units": cat.summaries(),
            "datasets": cat.datasets(),
            "initial_unit_id": initial,
            "initial_data": build_unit_data(cat.get(initial)) if initial and cat.get(initial) else None,
        }
        template = template_text("annotator.html")
        boot_json = json.dumps(boot, ensure_ascii=False).replace("</", "<\\/")
        html = template.replace('"__ANNOTATOR_BOOT__"', boot_json)
        self._send(200, html.encode(), "text/html; charset=utf-8")

    def _serve_unit(self, unit_id: str):
        unit = self.server.catalog.get(unit_id)
        if unit is None:
            self._send_json({"error": f"unknown unit: {unit_id}"}, code=404)
            return
        self._send_json(build_unit_data(unit))

    def _serve_frame(self, rest: str):
        # /frames/<unit_id>/<name>。unit_idの / 混入を防ぐため右から1回だけ割る
        if "/" not in rest:
            self._send(404, b"not found", "text/plain")
            return
        unit_id, name = rest.rsplit("/", 1)
        unit = self.server.catalog.get(unquote(unit_id))
        if unit is None or name not in unit.frame_files():   # パス走査対策: 既知の連番のみ
            self._send(404, b"not found", "text/plain")
            return
        self._send(200, (unit.frames_dir / name).read_bytes(), "image/jpeg")

    # --- POST --------------------------------------------------------------
    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/gt":
                self._post_gt()
            elif path == "/api/sop":
                self._post_sop()
            else:
                self._send(404, b"not found", "text/plain")
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            self._send_json({"ok": False, "error": str(e)}, code=400)

    def _post_gt(self):
        payload = self._read_json()
        unit = self._require_unit(payload)
        with self.server.write_lock:
            save_gt(unit, load_sop(unit.sop_path), payload["events"])
        self._send_json({"ok": True})

    def _post_sop(self):
        payload = self._read_json()
        unit = self._require_unit(payload)
        op = payload.get("op")
        with self.server.write_lock:
            sop_def = load_sop(unit.sop_path)
            if op == "set_hint":
                set_domain_hint(sop_def, payload.get("hint", ""))
            elif op == "upsert_event":
                upsert_event(sop_def, payload["event_id"],
                             ask=payload.get("ask"),
                             min_frames=payload.get("min_frames"))
            elif op == "delete_event":
                if delete_event(sop_def, payload["event_id"]):
                    save_sop(unit.sop_path, sop_def)
                    _drop_gt_key(unit, sop_def, payload["event_id"])
                self._send_json({"ok": True, "unit": build_unit_data(unit)})
                return
            elif op == "rename_event":
                if rename_event(sop_def, payload["event_id"], payload["new_id"]):
                    save_sop(unit.sop_path, sop_def)
                    _rename_gt_key(unit, sop_def, payload["event_id"], payload["new_id"])
                self._send_json({"ok": True, "unit": build_unit_data(unit)})
                return
            else:
                raise ValueError(f"未対応の操作: {op!r}")
            save_sop(unit.sop_path, sop_def)
        # SOP変更後の最新状態をエコーし、UIを再同期させる
        self._send_json({"ok": True, "unit": build_unit_data(unit)})

    def _require_unit(self, payload: dict) -> catalog.Unit:
        unit = self.server.catalog.get(payload.get("unit_id", ""))
        if unit is None:
            raise ValueError(f"unknown unit: {payload.get('unit_id')!r}")
        return unit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _adhoc_from_args(args) -> catalog.Unit:
    """--sop/--frames-dir を明示したときの単発unitを作る(旧CLIとの後方互換)。"""
    sop_path = Path(args.sop)
    if args.out:
        gt_path = Path(args.out)
    elif sop_path.resolve() == DEFAULT_SOP.resolve():
        gt_path = DEFAULT_GT
    else:
        gt_path = sop_path.parent / "ground_truth.json"
    unit_id = load_sop(sop_path)["sop"]["id"]
    return catalog.adhoc_unit(unit_id, sop_path, Path(args.frames_dir), args.fps, gt_path)


def _pick_initial(cat: catalog.Catalog) -> str | None:
    if cat.get(PREFERRED_INITIAL):
        return PREFERRED_INITIAL
    return cat.units[0].unit_id if cat.units else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sop", default=None,
                    help="単発unitを直接開く(台帳を使わず、このSOP1本だけ)")
    ap.add_argument("--frames-dir", default=str(DEFAULT_FRAMES),
                    help="--sop 指定時のフレームディレクトリ")
    ap.add_argument("--fps", type=float, default=1.0,
                    help="--sop 指定時のfps(t=idx/fpsの換算。既定: 1.0)")
    ap.add_argument("--out", default=None,
                    help="--sop 指定時の保存先(既定: SOPと同じディレクトリの ground_truth.json)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if args.sop:
        extra = _adhoc_from_args(args)
        cat = catalog.discover(ROOT, extra=extra)
        initial = extra.unit_id
    else:
        cat = catalog.discover(ROOT)
        initial = _pick_initial(cat)

    if not cat.units:
        raise SystemExit("[annotator] 注釈対象のunitが見つかりません(datasets/*/units/*/meta.json)")

    server = Annotator(("127.0.0.1", args.port), cat, initial)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"[annotator] {url} で待機中 "
          f"({len(cat.units)} unit / データセット: {', '.join(cat.datasets())})")
    print(f"[annotator] 最初に開くunit: {initial}  (操作のたびに自動保存。Ctrl-Cで終了)")
    if not args.no_browser:
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[annotator] 終了")


if __name__ == "__main__":
    main()
