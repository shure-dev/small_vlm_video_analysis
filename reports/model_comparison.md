# Factory Ego model comparison

## 現在地

データセットを刷新しました。旧構成（factory051/worker001の8 unit × 20フレーム）と、それに対するprediction run 5本・reference tIoU予備比較は廃止済みです（git履歴には残っています）。

現行データセットは **6工場・18 worker・20作業種類の20 unit（各20秒・2fps・40フレーム）** で、SOPは手順判定向けのイベント定義を持ちます（[データセットREADME](../datasets/factory_ego/README.md)参照）。

イベント定義を全面改訂しました（2026-07-11）。当初のtranscription由来の英語定義は実フレームと照合するとズレが多く、Fable×Opusの予備比較でも64イベント中16件が「両者とも非検出」＝窓内で起きていない疑いが出たため、**抽出フレーム（2fps・20秒窓）の目視による日本語イベント定義**へ置き換えました（方法論は[イベント定義ガイド](../docs/benchmark/events.md)）。

これに伴い、旧英語SOPに対するreference run 2本（Fable 5・Opus 4.8、10フレーム時代）は廃止済みです（git履歴には残る）。

## prediction run

| run | model | 方式 | unit coverage | formal accuracy |
|---|---|---|---:|---|
| `20260711-factory_ego-opus48-online5-r1` | Claude Opus 4.8 | オンライン（直近5フレームの因果窓） | 20/20（40フレーム） | 未評価（人手GTなし） |

**Opus 4.8オンライン推論**: unitごとのエージェントが40フレームを順に閲覧し、各フレーム時点で「直近5枚（未来は見ない）」の動きから各イベントを true/false 判定した（1 unitあたり40回・計800フレーム判定）。`raw/` に true/false、`predictions/` に schema v1（true→yes / false→no）を保存。決定論的judgeでイベント区間を導くと、手順どおりの状態遷移をよく再現している（例: garment_ironing = 板を置く→板に沿って畳む→表に返す→山に重ねる、manual_lathe = ナット締め→スパナを置く→主軸起動→回転継続）。窓内で起きていない動作は false のままで、min_frames に満たない検出は未検出になる。

可視化は `sop-replay --runs-dir runs`（イベント検出を日本語ラベルで表示。回生する1枚HTML）。

今後の予定:

1. ローカル小型VLMのbaseline run作成（同じオンライン方式。回答収集は複数画像入力への拡張が必要）
2. 人手GTの作成と、それを入力にしたevaluation runでの正式評価
3. モデル間一致・回答分布・境界差の予備比較（人手GTができるまで「精度」とは表記しない）

## 評価の原則（変わらない）

- 正式なprecision、recall、F1、tIoUは人手GT revisionを固定したevaluation runでのみ計算する
- reference予測との一致は「大型モデルとどれだけ同じ区間を見たか」であり精度ではない
- 再現: `python3 tools/benchmark/reference_tiou.py --reference <run_id>`（run作成後）
