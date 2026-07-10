# Factory Ego benchmark tools

設計・評価・データ追加の正本は[ベンチマーク運用ガイド](../../docs/benchmark/operations.md)です。このページはコマンド固有のメモだけを扱います。

## Fetch media

```bash
python3 tools/benchmark/fetch_factory_ego.py          # dry-run
python3 tools/benchmark/fetch_factory_ego.py --apply  # 照合済みフレームを配置
```

gated accessに同意済みのHFアカウント（`hf auth login`）が前提。unit metaが参照する5clipだけをtarヘッダ走査で取り出し、1fps抽出して `frames.sha256.json` と照合する。不一致は書き込まない。抽出仕様を変えてmanifest側を作り直す時だけ `--apply --update-manifest` を使う（runsの `inputs.lock.json` は当時の記録として変更しない）。

## New prediction run (local mlx-vlm)

```bash
../../../.venv-vlm/bin/python tools/benchmark/run_local_prediction.py \
  --model qwen2.5-3b \
  --model-name "Qwen2.5-VL-3B-Instruct 4-bit" \
  --run-id 20260710-factory_ego-qwen2.5-3b-baseline-r1
```

ローカルモデルでFactory Ego全unitの回答を収集し、既存runと同形式の不変prediction run（raw・正規化predictions・run.yaml・inputs.lock・index追記）を作る。rawはフレームごとに逐次保存するので、GPU Hang等で落ちても再実行すれば途中から再開する。`run.yaml` が既にあるrun IDは不変として拒否する。要mlx-vlm（Apple Silicon）。

## Reference tIoU (予備比較)

```bash
python3 tools/benchmark/reference_tiou.py \
  --reference 20260710-factory_ego-fable5-reference-r1 --json out/tiou.json
```

各runの回答から決定論的judgeでイベント区間を導き、reference run（Fable/Opus）との区間tIoUを測る。比較は共通unit・共通フレームidxに制限し、mean tIoUは両run検出ペアのみの平均（`core.evaluate` と同じ流儀）。referenceは人手GTではないため精度ではなく、[評価ポリシー](../../docs/benchmark/evaluation.md)の予備比較（モデル間一致・境界差）に当たる。VLM不要。

## Validate

```bash
python3 tools/benchmark/validate.py
```

フレームSHA-256、unit/SOP lock、factory/worker split、prediction coverage、run不変条件、`runs/index.jsonl`を検査する。VLMやネットワークは不要。

## Re-run the legacy migration

移行コマンドは既定でdry-runになり、既存ファイルと1byteでも異なる場合は上書きせず停止する。

```bash
python3 tools/benchmark/migrate_factory_ego.py \
  --legacy-examples /path/to/legacy/examples \
  --scratchpad /path/to/ego10k

# dry-run確認後のみ
python3 tools/benchmark/migrate_factory_ego.py \
  --legacy-examples /path/to/legacy/examples \
  --scratchpad /path/to/ego10k \
  --apply
```

必要なscratchpad構造は `frames_00000` 等の1fpsフレームと、`vlm_unit_a`〜`vlm_unit_h` の `sop.yaml` / `answer_log.json`。移行後のベンチはscratchpadへ依存しない。
