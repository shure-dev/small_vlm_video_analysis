# Factory Ego model comparison

## 現在地

データセットを刷新しました。旧構成（factory051/worker001の8 unit × 20フレーム）と、それに対するprediction run 5本・reference tIoU予備比較は廃止済みです（git履歴には残っています）。

現行データセットは **6工場・18 worker・20作業種類の20 unit（各20秒・2fps・40フレーム）** で、SOPは手順判定向けのイベント定義を持ちます（[データセットREADME](../datasets/factory_ego/README.md)参照）。

参照predictionとしてClaude Opus 4.8のオンライン推論run（20/20 unit）が1本あり、それに対して**ローカル小型VLM（≤6B）12本のpilot run（6工場×各1 unit = 6 unit）**を追加しました。人手GTがないため、以下はすべて「精度」ではなく **Opus参照との一致（予備比較）** です。

## prediction run

| 種別 | run | model | 方式 | unit |
|---|---|---|---|---:|
| 参照 | `20260711-factory_ego-opus48-online5-r1` | Claude Opus 4.8 | オンライン（直近5フレームの因果窓） | 20 |
| ローカル | `20260711-factory_ego-<alias>-pilot6-r1` × 12 | 下表の12モデル | **単一フレーム入力**（最新1フレームのみ・時間文脈なし） | 6 |

ローカルrunは `tools/benchmark/run_local_prediction.py --subset pilot6-v001` で作成。対象6 unitは各工場から「Opus参照が定義イベントを全検出した最もクリーンなunit」を選定（[pilot6-v001.json](../datasets/factory_ego/subsets/pilot6-v001.json)）。mlxモデルは4bit・mlx-vlm 0.6.3、SmolVLM2は公式transformers実装（fp32）。

## pilot6 予備比較（Opus 4.8参照との一致・6 unit・全21イベント）

Opus参照の回答分布は **yes 20% / no 80%**、Opusが検出したイベントは6 unitで計21個。

挙動でグループ分けして並べた（tIoU/一致率の単純な降順は下記の落とし穴で誤読しやすいため）。yes率はOpusの20%に近いほど分布が素直。

| 挙動 | model | サイズ | backend | yes率 | 回答一致率 | mean tIoU | Opus21中の検出 | peak_mb | 所見 |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| 健全・Opus寄り | Qwen3-VL-4B-Instruct | 4B | mlx | 14% | 82% | 0.34 | 11 | 4271 | Opus分布に最も近い。保守的で崩れなし |
| 健全・Opus寄り | Gemma4-E2B-it | E2B | mlx | 15% | 79% | 0.28 | 11 | 4541 | Opus分布に近い |
| 健全・Opus寄り | SmolVLM2-2.2B-Instruct | 2.2B | transformers/fp32 | 27% | 72% | 0.27 | 16 | — | Opus分布寄り。fp32必須（下記） |
| 健全・Opus寄り | MiniCPM-V-4.6 | 1.3B | mlx | 14% | 64% | 0.32 | 9 | 3647 | f006で値のクォート欠落→unclear化（5/6 unitは健全） |
| yes過剰 | Qwen3-VL-2B-Instruct | 2B | mlx | 41% | 64% | 0.29 | 18 | 2854 | 0.6.3のJSON崩壊懸念はprefillで回避 |
| yes過剰 | Qwen2.5-VL-3B-Instruct | 3B | mlx | 46% | 48% | 0.20 | 14 | 4131 | unclear 10% |
| yes過剰 | InternVL3-2B | 2B | mlx | 50% | 55% | 0.27 | 16 | 2458 | yes過剰傾向 |
| yes過剰 | Qwen3.5-4B-MLX | 4B | mlx | 59% | 53% | 0.25 | **21** | 5369 | Opusの全21イベントを検出するがyes過剰で区間が膨張 |
| yes過剰 | Qwen3.5-2B-MLX | 2B | mlx | 62% | 51% | 0.23 | 20 | 3331 | yes過剰 |
| ⚠退化 | Qwen3.5-0.8B-MLX | 0.8B | mlx | 8% | 81% | 0.38 | 11 | 2237 | ほぼ全no（91%）。高一致・高tIoUはno基準率の産物で識別力ではない |
| ⚠退化 | SmolVLM2-500M-Video | 0.5B | transformers/fp32 | 66% | 19% | 0.17 | 14 | — | 多くのunitで全yes/unclear・全40フレーム同一 |
| ⚠退化 | SmolVLM2-256M-Video | 0.26B | transformers/fp32 | 55% | 12% | 0.14 | 16 | — | f002は全unclear・f003は76%unclear |
| 未計測 | LFM2.5-VL-1.6B | 1.6B | mlx | — | — | — | — | — | mlx-vlm 0.6.3の `lfm2_vl` layer_normバグでロード不可。修正版0.6.4はwheel入手不可 |

「挙動」は yes率とunclear率・全40フレーム同一の有無から分類した診断的ラベル（Opusの yes 20%/no 80% を基準に、極端に偏るか定数出力へ退化しているか）。「Opus21中の検出」= Opusが検出した全21イベントのうち、そのモデルも検出できた数（both_detected）。

### この表の読み方（重要・数値の落とし穴）

- **これは精度ではなくOpus参照との一致**。Opusも人手GTではないので、上位＝正しいとは限らない。
- **回答一致率はno基準率で水増しされる**。質問の実際の答えは8割が"no"なので、退化して"no"を連発するモデル（Qwen3.5-0.8B: no 91%）は一致率が高く出る。yes率がOpusの20%から大きく離れるモデル（0.8B=8%、500M=66%）は、一致率が高くても低くても額面どおり受け取らない。
- **mean tIoUは両者が検出したイベント対のみの平均**。検出が疎なモデル（0.8B・MiniCPM）は対の数が少なく、少数の当たりで平均が跳ねるため不安定。「Opus21中の検出」列（both_detected）と併読する。
- **yes率をOpus(20%)と比べるのが最も素直な健全性指標**。Opus分布に近いのは Qwen3-VL-4B(14%)・Gemma4-E2B(15%)・MiniCPM(14%)・SmolVLM2-2.2B(27%)。

### 所見（単一フレーム入力・pilot6での予備的傾向）

- **単一フレーム入力の限界**: ローカル勢はどれもmean tIoUが0.14–0.38と低い。Opus参照は「直近5フレームの因果窓」で手順の状態遷移を追えたが、ローカルは最新1フレームのみで時間文脈が無く、動作の途中/完了の区別や短い動作の検出でOpusと区間がずれる。2枚以上入力の効果検証は次フェーズ。
- **中量級（2–4B）が総じてOpusに近い**。特にQwen3-VL-4Bは分布・一致・被覆のバランスが良い。Qwen3.5系（2B/4B）はyes過剰でOpusの全イベントを拾う一方、区間が膨らみtIoU・一致率が下がる。
- **1B未満は識別力が崩れる**。Qwen3.5-0.8Bは実質全noへ、SmolVLM2-500M/256Mは全yes/unclearへ退化。手順判定の解像度に達していない。
- **SmolVLM2はbfloat16×MPSで視覚が壊れる**（自由記述が「A--」など全フレーム文字化け）。**fp32で視覚が正常化**することを1フレーム自由記述で確認し、fp32で計測した（`observe.py` TransformersObserver）。2.2Bは健全だが500M/256Mはfp32でもタスクに追従できない。

可視化は `sop-replay --runs-dir runs`（イベント検出を日本語ラベルで表示。1枚HTMLでdataset/sample/model切替）。

再現: `python3 tools/benchmark/reference_tiou.py --reference 20260711-factory_ego-opus48-online5-r1 --json reports/data/reference_tiou_pilot6_vs_opus48.json`

今後の予定:

1. 複数フレーム入力（2枚〜）への拡張と、単一フレームからの精度変化の検証（`observe.py` は現在単一画像入力）
2. pilot6を残り14 unitへ拡大
3. 人手GTの作成と、それを入力にしたevaluation runでの正式評価（precision/recall/F1/tIoU）

## 評価の原則（変わらない）

- 正式なprecision、recall、F1、tIoUは人手GT revisionを固定したevaluation runでのみ計算する
- reference予測との一致は「大型モデルとどれだけ同じ区間を見たか」であり精度ではない
- Factory Egoのモデル出力（Opus含む）をground truthへ昇格しない
