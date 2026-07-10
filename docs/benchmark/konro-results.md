# Konroベンチマーク結果

ガスコンロの始業前点検を撮影した同一の16フレームに対し、3種類のSOP条件とローカルVLM 15モデルを評価しました。

| 条件 | 正解 |
|---|---|
| 正しい手順 | PASS |
| 順序違反 | FAIL。順序逆転を理由として指摘 |
| ステップ欠落 | FAIL。欠落を理由として指摘 |

判定は、PASS / FAILだけでなく違反理由まで一致した場合を正答とします。VLMの回答は、人手アノテーションに対するrelation正答数、mean tIoU、フレーム一致率で評価します。指標の定義は[評価ポリシー](evaluation.md)を参照してください。

> この結果は、同一の短いデモ動画に対する比較です。一般的な製造現場での性能を示すものではありません。

## 回答の評価

| モデル | relations<br>正答 | mean tIoU | 総合 | 点火<br>`knob` | 炎<br>`flame` | 指差し<br>`pointing` | グリル<br>`grill` | 電池<br>`battery` | 手袋<br>`gloves` |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3-VL-4B | 6/6 | 0.80 | 96% | 94% | 100% | 81% | 100% | 100% | 100% |
| Qwen2.5-VL-3B | 5/6 | 0.62 | 83% | 50% | 100% | 75% | 94% | 81% | 100% |
| SmolVLM2-2.2B† | 4/6 | 0.60 | 69% | 62% | 100% | 88% | 75% | 88% | 0% |
| Cosmos-Reason1-7B | 4/6 | 0.59 | 81% | 44% | 100% | 100% | 62% | 81% | 100% |
| Qwen3.5-4B | 4/6 | 0.53 | 77% | 38% | 100% | 75% | 50% | 100% | 100% |
| LFM2.5-VL-1.6B | 4/6 | 0.32 | 50% | 31% | 100% | 44% | 12% | 12% | 100% |
| InternVL3-2B | 4/6 | 0.32 | 50% | 31% | 100% | 25% | 12% | 31% | 100% |
| Qwen3.5-2B | 4/6 | 0.31 | 47% | 25% | 100% | 31% | 12% | 12% | 100% |
| Gemma4-E2B | 3/6 | 0.56 | 82% | 88% | 100% | 31% | 88% | 88% | 100% |
| Molmo-7B | 3/6 | 0.30 | 68% | 50% | 100% | 31% | 31% | 94% | 100% |
| Qwen3.5-0.8B | 3/6 | 0.17 | 67% | 62% | 94% | 31% | 38% | 75% | 100% |
| SmolVLM2-256M† | 3/6 | 0.14 | 17% | 44% | 6% | 19% | 12% | 19% | 0% |
| Qwen3-VL-2B | 3/6 | 0.05 | 77% | 75% | 94% | 88% | 44% | 62% | 100% |
| MiniCPM-V 4.6 | 2/6 | 0.55 | 83% | 44% | 100% | 69% | 88% | 100% | 100% |
| SmolVLM2-500M† | 1/6 | — | 71% | 75% | 94% | 81% | 88% | 88% | 0% |

relationsを6/6正答したのはQwen3-VL-4Bだけでした。指差しには3フレームの過検出がありましたが、relationの結論は変わらず、判定には影響していません。一方、フレーム一致率が83%でもrelationsが2/6のモデルがあり、フレーム一致率だけでは判定性能を選べません。

## 判定の評価

| モデル | サイズ | 正しい手順<br>→ PASS | 順序違反<br>→ 順序逆転 | ステップ欠落<br>→ 欠落 | 正答 |
|---|---:|:---:|:---:|:---:|:---:|
| Qwen3-VL-4B | 4B | ✅ | ✅ | ✅ | 3/3 |
| Qwen3.5-4B | 4B | ❌ | ✅ | ✅ | 2/3 |
| Qwen2.5-VL-3B | 3B | ❌ | ✅ | ✅ | 2/3 |
| MiniCPM-V 4.6 | 1.3B | ❌ | ✅ | ✅ | 2/3 |
| InternVL3-2B | 2B | ❌ | ✅ | ✅ | 2/3 |
| Molmo-7B | 7B | ❌ | ✅ | ✅ | 2/3 |
| Gemma4-E2B | 2B | ❌ | ❌ | ✅ | 1/3 |
| Cosmos-Reason1-7B | 7B | ❌ | ❌ | ✅ | 1/3 |
| Qwen3.5-2B | 2B | ❌ | ❌ | ✅ | 1/3 |
| Qwen3.5-0.8B | 0.8B | ❌ | ❌ | ✅ | 1/3 |
| LFM2.5-VL-1.6B | 1.6B | ❌ | ❌ | ✅ | 1/3 |
| Qwen3-VL-2B | 2B | ❌ | ❌ | ✅ | 1/3 |
| SmolVLM2-2.2B† | 2.2B | ❌ | ❌ | ✅ | 1/3 |
| SmolVLM2-500M† | 0.5B | ❌ | ❌ | ✅ | 1/3 |
| SmolVLM2-256M† | 0.26B | ❌ | ❌ | ❌ | 0/3 |

正しい手順をPASSと判定し、2種類の違反理由も特定できたのはQwen3-VL-4Bだけでした。このデモでは、違反を見つけることよりも、起きていない動作に yes と答える過検出が招く偽陽性FAILを避けることが難所でした。

## 再現方法

```bash
for m in qwen3-4b qwen3-2b qwen3.5-4b qwen3.5-2b qwen3.5-0.8b lfm2.5-1.6b \
         gemma4-e2b cosmos-7b qwen2.5-3b minicpm-4.6 internvl3-2b molmo-7b; do
  sop-check observe \
    --sop datasets/konro_inspection/sops/konro_inspection/correct.yaml \
    --frames-dir datasets/konro_inspection/units/konro_inspection/frames \
    --model "$m" --out "out/al_$m.json"

  for condition in correct wrong_order missing_step; do
    sop-check judge \
      --sop "datasets/konro_inspection/sops/konro_inspection/$condition.yaml" \
      --answer-log "out/al_$m.json"
  done

  sop-check eval \
    --sop datasets/konro_inspection/sops/konro_inspection/correct.yaml \
    --ground-truth datasets/konro_inspection/annotations/human-v001/konro_inspection.json \
    --answer-log "out/al_$m.json"
done
```

SmolVLM2は公式transformers実装で回答を収集します。`torch`、`torchvision`、`num2words` が別途必要です。

```bash
for m in HuggingFaceTB/SmolVLM2-256M-Video-Instruct \
         HuggingFaceTB/SmolVLM2-500M-Video-Instruct \
         HuggingFaceTB/SmolVLM2-2.2B-Instruct; do
  sop-check observe --backend transformers \
    --sop datasets/konro_inspection/sops/konro_inspection/correct.yaml \
    --frames-dir datasets/konro_inspection/units/konro_inspection/frames \
    --model "$m" --out "out/al_$(basename "$m").json"
done
```

3条件でquestionsは共通なので、モデルごとの回答収集（`observe`）は1回だけ実行します。人手アノテーションは [`datasets/konro_inspection/annotations/human-v001/konro_inspection.json`](../../datasets/konro_inspection/annotations/human-v001/konro_inspection.json) です。

† SmolVLM2の3モデルは `--backend transformers` で計測しています。`gloves` の値が空のJSONになったため、その列は無回答として0%になっています。
