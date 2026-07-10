# Factory Ego model comparison

## 現在地

8 unit × 20 framesを対象に、reference（Fable 5、Opus 4.8）とローカル小型VLM 3本の予測を、同一形式の不変prediction runとして保持しています。ローカル3本はKonroベンチマーク上位から選定しました（SmolVLM2-2.2Bはtransformersバックエンド限定のため未実行、Cosmos-Reason1-7Bは対象外の判断）。

| run | role | unit coverage | formal accuracy |
|---|---|---:|---|
| `20260710-factory_ego-fable5-reference-r1` | large-model reference prediction | 8/8 | 未評価（人手GTなし） |
| `20260710-factory_ego-opus48-reference-r1` | large-model reference prediction | 1/8、10 framesのみ | 未評価（人手GTなし） |
| `20260710-factory_ego-qwen3-4b-baseline-r1` | local small-VLM baseline | 8/8 | 未評価（人手GTなし） |
| `20260710-factory_ego-qwen2.5-3b-baseline-r1` | local small-VLM baseline | 8/8 | 未評価（人手GTなし） |
| `20260710-factory_ego-qwen3.5-4b-baseline-r1` | local small-VLM baseline | 8/8 | 未評価（人手GTなし） |

人手GT作成前に計算できるのは、一致率・回答分布・境界差などの予備比較です。precision、recall、F1、balanced accuracy、tIoUはhuman annotation revisionを入力にしたevaluation runで計算します。

## Reference tIoU（予備比較・精度ではない）

各runの回答から決定論的judgeでイベント区間を導き、reference予測の区間との重なり（mean tIoU）を測りました。referenceは人手GTではないため、これは「大型モデルとどれだけ同じ区間を見たか」というモデル間一致であり、精度として読まないでください。比較は共通unit・共通フレームidxに制限します。

再現: `python3 tools/benchmark/reference_tiou.py --reference <run_id>`。イベント別の詳細は [`reports/data/`](data/) のJSONにあります。

### vs Claude Fable 5（8 unit・24イベント）

| model | mean tIoU |
|---|---:|
| Claude Opus 4.8 † | 0.89 |
| Qwen3-VL-4B-Instruct 4-bit | 0.67 |
| Qwen3.5-4B 4-bit | 0.65 |
| Qwen2.5-VL-3B-Instruct 4-bit | 0.56 |

† Opusは共通1 unit（assembly）・先頭10フレームのみの比較。

なお、Qwen系はいずれも24イベント中1件だけ検出できなかったイベントがあり（Qwen3系: part_pickの`reach_up`、Qwen2.5: board_cablesの`move_board`）、その1件はtIoUの平均から除外しています。

### vs Claude Opus 4.8（1 unit・3イベント・先頭10フレーム）

| model | mean tIoU |
|---|---:|
| Claude Fable 5 | 0.89 |
| Qwen3-VL-4B-Instruct 4-bit | 0.83 |
| Qwen3.5-4B 4-bit | 0.73 |
| Qwen2.5-VL-3B-Instruct 4-bit | 0.46 |

## 読みかた

- 大型モデル同士（Fable 5 × Opus 4.8）の一致0.89が、この課題での実質的な一致上限のアンカーになります。
- ローカル勢ではQwen3-VL-4Bが両referenceに最も近く、Konroの人手GT評価（tIoU 0.80・判定3/3）での首位と整合します。
- Qwen3.5-4BとQwen2.5-VL-3Bの順位はKonroのGT評価（Qwen2.5が上）と入れ替わっており、単一動画の結果が別ドメインでそのまま保たれるわけではないことを示しています。
- 「イベントが起きたかどうか」の判断はほぼ全モデルで一致しており、差は区間の境界の取り方に出ています。
