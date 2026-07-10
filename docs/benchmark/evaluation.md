# Evaluation policy

## Formal accuracy

正式なprecision、recall、F1、balanced accuracy、tIoUは、人手GT revisionを固定したevaluation runでのみ計算します。

prediction runとevaluation runを分けることで、後日GTが修正されても過去の予測を改変せず、どのGT版で測った数字かを追跡できます。

## Before human ground truth

人手GTがないunitでは、次だけを予備比較として扱えます。

- モデル間一致
- yes/no回答分布
- 境界差
- confidence分布

これらをaccuracy、正解率、教師一致とは表記しません。

## Split policy

分割はunit単位ではなくfactory/worker単位です。Factory Egoの現8 unitは同一factory/workerで、既に複数モデルが閲覧しているため、恒久的に `dev_seen` としtestへ昇格させません。
