# SOPフォーマット

SOPは、VLMに聞く質問、回答から検出するイベント、イベント間の規則をYAMLで定義します。動画で実際に起きたことを記録する人手アノテーションとは分離します。

## 最小例

```yaml
sop:
  id: konro_inspection
  name: コンロ始業前点検
  domain_hint: "ガスコンロの点検作業を上から撮った動画"

questions:
  - id: knob
    ask: "手がコンロ手前のつまみを操作しているか"
    values: ["yes", "no"]
  - id: pointing
    ask: "人が対象を指差しているか"
    values: ["yes", "no"]

events:
  ignite:
    evidence: "knob==yes"
    min_frames: 2
  point1:
    evidence: "pointing==yes"
    occurrence: 1

relations:
  - ignite before point1

expect:
  verdict: PASS
```

YAML 1.1の処理系では裸の `yes` / `no` が真偽値として解釈されることがあるため、値はクォートします。

## relations

本プロジェクトでは、1 fpsのサンプリングとVLMの境界ノイズに耐えられるよう、時間関係を次の3種類に絞っています。

| relation | 意味 | 実装 |
|---|---|---|
| `A before B` | Aの後にBを行う | 区間の代表時刻を、`order_tolerance_s` の許容差付きで比較 |
| `A overlaps B` | AとBが同時期に起きる | 検出区間が交差するかを確認 |
| `not A` | Aを行わない | Aが一度も検出されないことを確認 |

### occurrence

同じ質問が動画内で複数回 `yes` になる場合に、「何回目の動作か」を指定します。

```yaml
events:
  point1:
    evidence: "pointing==yes"
    occurrence: 1
  point2:
    evidence: "pointing==yes"
    occurrence: 2
```

複数回の動作には明示的な `occurrence` を推奨します。省略すると、イベントの宣言順が割り当てに影響します。

## expect

`expect` は、その動画とSOPの組み合わせに対する期待判定です。判定の評価に使います。FAILでは、違反理由まで指定できます。

```yaml
expect:
  verdict: FAIL
  because:
    - relation: "battery_check before ignite"
      kind: order_reversed
```

`kind` は次の5種類です。

| kind | 意味 |
|---|---|
| `order_reversed` | `before` の順序が逆転した |
| `missing` | 必要なイベントを検出できなかった |
| `overlap_missing` | 重なるべきイベントが離れていた |
| `overlap_forbidden` | 重なってはいけないイベントが重なった |
| `forbidden` | `not A` に反してAを検出した |

## イベント検出の調整

| フィールド | 用途 |
|---|---|
| `min_frames` | Nフレーム以上続いた回答だけをイベントとして扱う |
| `max_gap_frames` | 短い回答の揺れをまたいで区間を接続する |
| `defaults` | 複数イベントの既定値をまとめて指定する |

動画ごとにイベント語彙がどこで定義されるかは、[動画ごとのイベント定義](../benchmark/events.md)を参照してください。実例は [`datasets/konro_inspection/sops/konro_inspection/`](../../datasets/konro_inspection/sops/konro_inspection/) にあります。
