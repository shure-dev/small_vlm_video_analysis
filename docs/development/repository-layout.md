# Repository layout

## Python package

import可能なコードは `src/small_vlm_sop_check/` のみに置きます。rootのdataset、docs、toolsを偶然importできないsrc-layoutにすることで、checkout上だけ動いてinstall後に壊れる問題を防ぎます。

```text
src/small_vlm_sop_check/
├── core/       # PyYAML以外に依存しない判定・評価
├── inference/  # cv2 / mlx-vlm / transformers等のoptional backend
├── apps/       # annotator・replayとpackage dataのHTML
└── cli.py      # sop-check
```

- `sop-check`: VLMの回答収集、判定、評価
- `sop-annotate`: 人手ground truth作成
- `sop-replay`: self-contained replay HTML生成

entry pointと依存は `pyproject.toml` を唯一の正本とします。HTML templateはpackage外の相対パスに依存せず、`importlib.resources` で読みます。

参考: [PyPA src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)、[PyPA command-line tools](https://packaging.python.org/en/latest/guides/creating-command-line-tools/)、[setuptools package data](https://setuptools.pypa.io/en/stable/userguide/datafiles.html)

## Non-package code

`tools/` はrepositoryの保守にしか使わないscriptに限定します。

- `tools/benchmark/`: dataset移行・lock/hash検証
- `tools/quality/`: 文書リンクなどの静的検査

ユーザーが直接使う機能は `tools/` へ置かず、packageのentry pointとして公開します。

## Tests and schemas

- `tests/unit/`: coreロジックの振る舞い
- `tests/integration/`: dataset、run、docs、CLI境界
- `schemas/benchmark/v1/`: 公開データ契約。破壊的変更は既存fileを変更せず `v2/` を作る

pytestのimport pathは `pyproject.toml` で設定し、test file内で `sys.path` を変更しません。
