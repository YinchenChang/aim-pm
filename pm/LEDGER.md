<!-- BY: PM@CL | MODEL: Claude Opus 5【自報】 | CHARTER: AIM-C1.1 | NOTE: 定稿自 PM@GK 擬稿 1aKgwxslikOV-2Bk5yUsUlACM6EqDtdd2（使用者 09-16 追認預設袋）；PM@CL 補齊 CHARTER §3 欄位 | CONSUMES: 12K5eqBNP6OMkM_c35ko4hqO8vMDbPuBi；1aKgwxslikOV-2Bk5yUsUlACM6EqDtdd2；17pxTe8XkUvYInPgOf8rKq8d7CAHPiQkd | EMITS: 1uKfYqf1Dr3uyMTI84Sgq0Pw2gU4Ldlmm -->
# LEDGER — 委託資本帳本

**正本：** `AIM/pm/LEDGER.md` fileId `1uKfYqf1Dr3uyMTI84Sgq0Pw2gU4Ldlmm`（非 PM 之 `sync` 不下載）
**寫入：** 2026-09-16 PM@CL　**起算日：** 2026-10-15　**地位：** 標頭定稿；數字表空（起算前）
**規則：** 「標頭」與「預設袋」兩節由 PM 維護；「數字表」節由 `aim.py` 覆寫，覆寫時不得動前兩節。

## 標頭

| 項 | 值 | 來源 |
|---|---|---|
| 委託資本上限 | US$20,000 `[V-使用者]` | CHARTER §2-1 |
| 資本進出 | 起算日一次到位；無補注、無加減碼 | §2-2、§2-7、§5 |
| 基準 (a) | 預設袋同一對 ETF 之總報酬，70／30，季再平衡 | §2-6；`aim_config.benchmark_a` 已為 `{"VTI":0.7,"IBIT":0.3,"rebalance":"Q"}`（09-16 核） |
| 基準 (b) | S&P 500 總報酬（config `^SP500TR`） | §2-5 |
| 季切 | 01-15／04-15／07-15／10-15，共 40 季 | §2-4 |
| 結算現金 | ≤ 池 NAV 5%；空方／選擇權保證金計為該部位佔用 | §5 |
| 計分 | 時間加權對數成長率；資本流不改計分 | §5 |

## 預設袋 ＝ 基準 (a)

| 權重 | 代號 | 名稱 | 註 |
|---|---|---|---|
| 0.70 | VTI | Vanguard Total Stock Market ETF | 美股寬基；≠ (b) |
| 0.30 | IBIT | iShares Bitcoin Trust ETF | BTC ETF（§2-8）；仍在申報（10-Q，期末 2026-06-30）`[V]` |

- 再平衡與季切同日；主動部位自預設袋按比例撥出（§3.1）。
- 主動部位：無（起算前）。

## 數字表（`aim.py` 覆寫區；起算前為空）

**起算至今：** 時間加權報酬 —　對數成長率 —　最大回撤 —

| 月末 | 池 NAV | 預設袋市值 | 主動部位市值 | 結算現金 | 結算現金／NAV | (a) 月末值 | (b) 月末值 | 池月對數成長 |
|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — |

### 部位

| 代碼 | 標的 | 方向 | 數量 | 成本 | 市值 | P 檔 fileId |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

### 執行回填（§9：實際成交或「未執行」）

| 日期 | EXECUTE 編號 | 標的 | 成交數量 | 成交價 | 狀態 |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

EXECUTE（資本轉入＋VTI／IBIT 建倉）僅於 2026-10-15 發出。

**（LEDGER 結束。）**
