# ADR 0001: Separate facts, predictions, and evaluations

- Status: accepted
- Date: 2026-07-10

## Context

動画、SOP、人手GT、モデル生成アノテーション、評価値が同じexampleディレクトリに混在すると、モデル予測を正解として扱ったり、後からGTを追加した際に過去runを書き換えたりしやすい問題がありました。

## Decision

- 入力媒体・SOP・人手GTは `datasets/`
- モデル予測は `runs/`
- GT revisionに対する採点は `evaluations/`
- 人向け比較結果は `reports/`
- 完了runは不変
- `examples/` は廃止し、完結デモもdatasetとして管理

Konroの既存モデルログは、VLMなしでUIとテストを再現するための互換fixtureとしてdataset内に隔離します。新しい実験結果はfixtureへ追加しません。

## Consequences

データの役割と追跡元がパスから分かるようになります。一方、KonroのCLI例ではSOPとGTが別revisionディレクトリになるため、汎用`eval`コマンドでは `--ground-truth` を明示します。
