# PM 季輪（排程：每年 01-15／04-15／07-15／10-15 09:47 台北；CHARTER §5、§8）

無人在場時不問問題。只發 CHARTER §8 准許之訊息：EXECUTE、SCORECARD。不可逆且兩可之事寫 HEALTH 後停。

## 0. 準備
- clone `YinchenChang/aim`（規則、FUNNEL、`cards/` 之凍結 L／M）與 `YinchenChang/aim-pm`（LEDGER、P、data）。
- 讀 `aim/AIM_CHARTER.md` → `aim-pm/CLAUDE.md` → `aim-pm/pm/LEDGER.md` → `aim/AIM_FUNNEL.md`。

## 1. 分支
- **起算日（`data/cashflows.csv` 無資料列，且今日＝`aim_config.json` 之 `start_date`）→ 起算 EXECUTE：**
  - 資本轉入單：US$20,000（§2-1）一次到位（§2-7）。
  - 預設袋建倉單：依 `aim_config.json` `benchmark_a`（VTI 0.70／IBIT 0.30），結算現金 ≤ NAV 5%（§5）。股數＝floor(權重 × 可投資金額 ÷ 參考價)，可投資金額＝US$20,000（整股取整之餘額即結算現金，須 ≤ 5%；若超過，以餘額加買 1 股 VTI 後再檢）；成交時段＝起算日美股盤中（台北時間當晚 21:30 起）；參考價＝最近一個美股收盤價（WebSearch／WebFetch 取，列來源 URL 與時間）；限價區間＝參考價 ±1%（買單上緣為限價）。
  - 主動部位：只有 `aim/cards/` 中「稽核維持」之 L／M 且 PM 已凍結 P 者才可下單；否則全額為預設袋（§5：未過門檻時持 (a)，不視為缺陷）。
- **其他季切日 → 季修輪：**
  1. 預設袋再平衡：依 LEDGER 最新部位與參考價，偏離 70／30 者出再平衡 EXECUTE；無偏離不出單。
  2. SCORECARD：數字段取 `out/SCORECARD_numbers.md`（GitHub Actions 月初產出）；PM 補 C 決策層／論點層、D 計數（自 `aim/query/RUNLOG.tsv`、`aim/AIM_FUNNEL.md`、`aim/query/ARCH_matrix.md`）、E 判讀 ≤ 400 字並回答 §5 必答題。三層加總 ≠ A 即標「未完成」。
  3. §5 觸發：Brier 檢討條件依 `aim.py scorecard` 數字判定。
  4. 章程季修：只改 PM 職權內之條文；§2 只由使用者改。修訂寫 `aim/AIM_CHARTER.md`＋`aim/query/CHARTER_HIST.md`。

## 2. 寫入
- `pm/EXECUTE_YYYYMMDD_CL.md`（≤ 2 KB：標的、方向、口數、限價區間、到期）；`pm/SCORECARD_YYYYQn_CL.md`（≤ 8 KB）。
- commit＋push 兩個 repo（各一 commit）。

## 3. 最終回覆（即推播給使用者）
首行 BOOT 行。其後只放 EXECUTE 全文及／或 SCORECARD 摘要。末附一行：「成交後直接回覆本對話（標的、數量、成交價、日期），PM 會寫入 `data/trades.csv` 與 `data/cashflows.csv`；不下單請回『未執行』。」

## 4. 使用者回填（同一對話後續）
使用者回覆成交 → 追加 `data/trades.csv`（`date,symbol,qty,price`）與 `data/cashflows.csv`（`date,amount`；起算轉入一筆），commit＋push（觸發 Actions 重算 LEDGER）。只記錄，不評論。
