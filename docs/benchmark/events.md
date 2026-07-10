# Event definitions

イベントは動画unitごとのSOPで定義します。`questions:` がVLMへのフレームごとの質問、`events:` が回答からイベント区間を作る決定論的条件です。

## Konro Inspection

[正しい手順SOP](../../datasets/konro_inspection/sops/konro_inspection/correct.yaml)を正本とし、`wrong_order.yaml` と `missing_step.yaml` は同じquestions定義に対する違反条件です。

## Factory Ego

| unit | events | SOP |
|---|---|---|
| assembly | `hold_part`, `reach_rack`, `tray_visible` | [v001](../../datasets/factory_ego/sops/f051_w001_assembly/v001.yaml) |
| assembly cycle 2 | `hold_part`, `reach_rack`, `tray_visible` | [v001](../../datasets/factory_ego/sops/f051_w001_assembly_cycle2/v001.yaml) |
| board cables | `touch_board`, `move_board`, `hold_item` | [v001](../../datasets/factory_ego/sops/f051_w001_board_cables/v001.yaml) |
| cable tying | `hold_cable`, `seated_work`, `rack_visible` | [v001](../../datasets/factory_ego/sops/f051_w001_cable_tying/v001.yaml) |
| connector seated | `hold_connector`, `both_hands`, `rack_visible` | [v001](../../datasets/factory_ego/sops/f051_w001_connector_seated/v001.yaml) |
| part inspection | `reach_shelf`, `inspect_part`, `tray_visible` | [v001](../../datasets/factory_ego/sops/f051_w001_part_inspection/v001.yaml) |
| part pick | `reach_up`, `handle_part`, `grid_tray` | [v001](../../datasets/factory_ego/sops/f051_w001_part_pick/v001.yaml) |
| tray handoff | `walking`, `hold_tray`, `coworker_visible` | [v001](../../datasets/factory_ego/sops/f051_w001_tray_handoff/v001.yaml) |

Factory EgoのSOPはすべて `status: provisional` です。Fableの元の `events_def` はモデル出力なので、正式SOPではなくFable prediction runに保持します。
