# Operations

## Quick regression

```bash
python3 -m pip install -e ".[test]"
python3 tools/benchmark/validate.py
python3 tools/quality/check_docs.py
python3 tools/quality/check_public.py
python3 -m pytest -q
```

Factory Egoのgated媒体を取得済みのローカル環境では、`python3 tools/benchmark/validate.py --require-media` で160フレームのSHAまで検証します。公開cloneでは媒体なしが正常です。

## Konro demo

```bash
sop-check judge \
  --sop datasets/konro_inspection/sops/konro_inspection/correct.yaml \
  --answer-log datasets/konro_inspection/fixtures/reference_outputs/answer_log.json

sop-check eval \
  --sop datasets/konro_inspection/sops/konro_inspection/correct.yaml \
  --ground-truth datasets/konro_inspection/annotations/human-v001/konro_inspection.json \
  --answer-log datasets/konro_inspection/fixtures/reference_outputs/answer_log.json
```

注釈toolとreplay viewerは引数なしでKonro datasetを開きます。

## Factory Ego media fetch

gated媒体は再配布しないため、各自がupstreamから取得します。

1. Hugging Faceで [builddotai/Egocentric-10K](https://huggingface.co/datasets/builddotai/Egocentric-10K) のgated accessに同意する（連絡先共有が必要）
2. `hf auth login` 済みの環境で取得スクリプトを実行する

```bash
python3 -m pip install -e ".[fetch]"                    # huggingface_hub + opencv
python3 tools/benchmark/fetch_factory_ego.py            # dry-run: 取得・抽出・SHA照合のみ
python3 tools/benchmark/fetch_factory_ego.py --apply    # 照合済みフレームを配置
python3 tools/benchmark/validate.py --require-media     # 160フレームのSHAまで検証
```

スクリプトはunit metaのsampling条件（clip・秒区間・1fps）から必要な5clipだけをtarのヘッダ走査で取り出すため、worker全体のtarをダウンロードしません。抽出結果が `frames.sha256.json` と一致しない場合は書き込まず終了します（manifest側を作り直す場合のみ `--apply --update-manifest`）。

## Adding a local model prediction run

mlx-vlmが動く環境で、Konroベンチ上位モデルなどをFactory Egoへ追加するときは専用ツールを使います（run形式・lock・indexを自動で揃える）。

```bash
../../../.venv-vlm/bin/python tools/benchmark/run_local_prediction.py \
  --model <alias|HF ID> --model-name "<表示名>" \
  --run-id <日付>-factory_ego-<モデル>-baseline-r1
python3 tools/benchmark/validate.py
```

reference run（Fable/Opus）との区間一致は `tools/benchmark/reference_tiou.py` で測ります。人手GTがないため、この数値は精度ではなく予備比較として扱います。

## Factory Ego migration

移行は既定dry-run・差分上書き拒否です。詳細は[benchmark tool README](../../tools/benchmark/README.md)を参照してください。

## Adding data

1. `dataset.yaml` とunit metaを追加する
2. 媒体・sampling条件・hashを固定する
3. SOPをversion付きで追加する
4. factory/worker単位でsplitを事前確定する
5. モデル出力はdatasetではなく新しいprediction runへ保存する（run_idは `{日付}-{dataset}-{モデル}-{役割}-r{通し番号}`）
6. validatorとpytestを通す
