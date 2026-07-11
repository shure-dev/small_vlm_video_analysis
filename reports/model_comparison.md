# Factory Ego model comparison

## 現在地

データセットを刷新しました。旧構成（factory051/worker001の8 unit × 20フレーム）と、それに対するprediction run 5本・reference tIoU予備比較は廃止済みです（git履歴には残っています）。

現行データセットは **6工場・18 worker・20作業種類の20 unit（各10秒・1fps・10フレーム）** で、SOPは手順判定向けのイベント定義を持ちます（[データセットREADME](../datasets/factory_ego/README.md)参照）。

現時点のprediction runは、大型モデルのreference 2本です（Claude Codeのサブエージェントがunitごとにフレームを順に閲覧して回答）。

| run | model | unit coverage | formal accuracy |
|---|---|---:|---|
| `20260711-factory_ego-fable5-reference-r1` | Claude Fable 5 | 20/20 | 未評価（人手GTなし） |
| `20260711-factory_ego-opus48-reference-r1` | Claude Opus 4.8 | 20/20 | 未評価（人手GTなし） |

## Reference tIoU（予備比較・精度ではない）

Fable 5基準でのOpus 4.8の区間一致は **mean tIoU 0.631**（64イベント中、両者検出38・両者とも非検出16・片側のみ検出10。詳細は [`reports/data/reference_tiou_fable5.json`](data/reference_tiou_fable5.json)）。

読みかた:
- 旧factory051データ（同一作業の8 unit）での大型モデル間一致0.89に対し、**多様な20作業では0.63**まで下がる。作業の多様性が課題の難度を大きく上げることを示す
- 「両者とも非検出」16件は、窓内でそのイベントが実際に起きていない可能性が高い（例: `f002_w005_garment_ironing` の `iron_press` は両モデルとも全フレームnoで、transcription由来の窓見立てのズレを示唆）。**イベント定義レビューの主対象**
- 片側のみ検出10件は境界・解釈の割れであり、min_framesや質問文の曖昧さの点検対象

## 今後の予定

1. SOPイベント定義の人手レビュー（上記の非検出・片側検出イベントを重点に）
2. ローカル小型VLMのbaseline run作成（questionsが「直近数フレーム＋最新フレームの状態」を問う動画解析設計のため、回答収集は複数画像入力への拡張が必要）
3. モデル間一致・回答分布・境界差の予備比較の拡充（人手GTができるまで「精度」とは表記しない）

## 評価の原則（変わらない）

- 正式なprecision、recall、F1、tIoUは人手GT revisionを固定したevaluation runでのみ計算する
- reference予測との一致は「大型モデルとどれだけ同じ区間を見たか」であり精度ではない
- 再現: `python3 tools/benchmark/reference_tiou.py --reference <run_id>`（run作成後）
