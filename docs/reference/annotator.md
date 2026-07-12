# 注釈ツール（sop-annotate）

`sop-annotate` は、抽出済みフレームをブラウザに並べ、SOPの各イベントが動画中に**実際に起きた区間**を人手で記録するツールです。標準ライブラリのみで動くローカルHTTPサーバ（`http.server`）で、外部依存・ビルド工程はありません。付けた注釈は操作のたびに `ground_truth.json` へ自動保存されます。

注釈するのは事実（いつ何が起きたか＝区間）だけです。tIoUやフレーム一致などの評価は `sop-check eval` が別に行います（[評価ポリシー](../benchmark/data-contract.md)）。

## 起動

```bash
sop-annotate                      # datasets/ 配下のunitを台帳化し、一覧から選ぶ
sop-annotate --port 9000          # ポート変更
sop-annotate --no-browser         # 自動でブラウザを開かない
# 台帳を使わず単一unitだけ開く（後方互換）:
sop-annotate --sop path/to/sop.yaml --frames-dir path/to/frames --fps 2.0 \
             --out path/to/ground_truth.json
```

引数なしで起動すると `datasets/*/units/*/meta.json` を走査してunit台帳を作り、ヘッダのプルダウンで「データセット → unit」を切り替えられます。`--sop` を渡した場合は、そのunitを台帳の先頭に足して最初に開きます。

## 画面構成

| 領域 | 内容 |
|---|---|
| ヘッダー | データセット/unitセレクタ（注釈済みは `✓`）、保存状態チップ、保存先パス |
| フレームビューア | 大きなフレーム画像、再生バー、サムネイル帯（クリックでシーク） |
| ヒント欄 | `domain_hint`（撮影状況＝VLMにも渡すプロンプト）の編集欄。500msデバウンスで自動保存 |
| 参考情報 | factory_ego など上流のtranscript/活動列を読み取り専用で表示（GTではない） |
| イベントレーン | 各イベントを同一時間軸のタイムラインで縦に並べる。状態バッジ・日本語ラベル・質問文をその場で編集 |

## 区間の付け方

- **タイムラインをドラッグ**すると、その範囲を区間として引ける（フレーム境界にスナップ）。
- 既存区間の**両端ハンドルをつまんでドラッグ**すると開始/終了を伸縮できる。
- レーンの空白を**単クリック**すると再生位置だけ動く（区間は変えない）。
- ボタン **開始=ここ / 終了=ここ**、またはキーボード <kbd>i</kbd>/<kbd>o</kbd> でも現在フレームを端点にできる。
- 起きなかったイベントは **起きていない**（<kbd>n</kbd>）で `null` を記録、**クリア**（<kbd>x</kbd>）で未注釈に戻す。
- <kbd>←</kbd><kbd>→</kbd>=フレーム移動、<kbd>↑</kbd><kbd>↓</kbd>=イベント選択。

`occurrence` 付きイベント（1回目/2回目など）は、それぞれの出現を別イベントとして注釈します。

## イベント・SOPの編集

イベントの追加・削除、日本語ラベル・質問文・撮影状況ヒントの編集は、その場でSOP YAMLへ検証付きに書き戻されます（`core.sop.save_sop`。`'yes'/'no'` は自動クォートされYAML 1.1のブール化は起きません）。

- **追加**: 「＋ イベントを追加」→ 日本語ラベル・イベントID（英数字/`_`）・質問文を入力。質問（yes/no）を同IDで用意し、`evidence: <id>==yes` を張る。
- **削除**: 確認のうえ削除。そのイベントだけが参照していた質問と、`ground_truth.json` 内の同キーもカスケード削除して不整合を残さない。
- **編集**: ラベル/質問文はインラインで編集し、フォーカスを外すと保存。イベントIDは作成後リネームしない（runsのprediction・evidence・GTキーとの整合が壊れるため）。

## データモデル

`ground_truth.json`（スキーマ v0.1）は3状態を区別します。詳細は [評価の入力契約](../benchmark/data-contract.md) を参照。

```json
{
  "schema_version": "0.1",
  "sop_id": "konro_inspection",
  "fps": 1.0,
  "n_frames": 16,
  "events": {
    "ignite": {"start_idx": 1, "end_idx": 4},
    "gloves_worn": null
  }
}
```

- `{start_idx, end_idx}`（両端含む・フレームインデックス。秒は `t = idx / fps`）= 起きた区間
- `null` = 「起きていない」と明示注釈
- キーが無い = 未注釈（評価から除外）

## HTTP API（内部）

UIはこのローカルAPIを叩きます。書き込みは `threading.Lock` で直列化され、原子的に（tmp→`os.replace`）保存されます。

| メソッド・パス | 用途 |
|---|---|
| `GET /api/units` | unit台帳の一覧（データセット・注釈済みフラグ） |
| `GET /api/unit/<unit_id>` | 1 unitのページデータ（SOP・フレーム・保存済み注釈・参考情報） |
| `GET /frames/<unit_id>/<name>` | フレーム画像（既知の連番のみ配信＝パス走査対策） |
| `POST /api/gt` | 区間の保存（`{unit_id, events}`） |
| `POST /api/sop` | SOP編集（`op`: `set_hint` / `upsert_event` / `delete_event`） |

## 実装

- サーバ・台帳: `src/small_vlm_sop_check/apps/annotator.py`、`src/small_vlm_sop_check/apps/catalog.py`
- SOP読み書き・編集: `src/small_vlm_sop_check/core/sop.py`（`save_sop` / `set_domain_hint` / `upsert_event` / `delete_event`）
- 画面: `src/small_vlm_sop_check/apps/templates/annotator.html`（デザイントークン＋素のJS。フレームワーク不使用）
