<!-- BY: PM@CL | MODEL: Claude Opus 5.5【自報】 | CHARTER: AIM-C1.2 | CONSUMES: aim/AIM_CHARTER.md；aim-pm/runbooks/PM_QUARTER.md；aim-pm/aim_config.json；aim-pm/pm/LEDGER.md | EMITS: pm/EXECUTE_20261015_CL.md -->
# EXECUTE 20261015-01 — 起算日（CHARTER §2-1、§2-7、§5）

**時段：** 2026-10-15 美股盤中（台北 21:30 起）；當日有效（DAY）。帳戶：Firstrade。

| # | 動作 | 標的 | 方向 | 數量 | 限價區間（USD） | 到期 |
|---|---|---|---|---|---|---|
| 1 | 資本轉入 | USD 現金 | 轉入 | US$20,000 | — | 2026-10-15 前到帳 |
| 2 | 預設袋建倉 | VTI | 買 | 37 股 | 373.11–380.65（限價 380.65） | DAY |
| 3 | 預設袋建倉 | IBIT | 買 | 129 股 | 45.78–46.70（限價 46.70） | DAY |

**參考價（最近美股收盤，2026-10-14 16:00 EDT）：** VTI 376.88、IBIT 46.24 — 來源 https://stockanalysis.com/etf/vti/ 、https://stockanalysis.com/etf/ibit/ （2026-10-15 01:50 UTC 取）；前收 381.32／47.13 與 https://stockinvest.us/stock-price/VTI 、https://stockinvest.us/stock-price/IBIT 之 10-13 收盤一致。
**尺寸：** floor(0.70×20,000÷376.88)=37；floor(0.30×20,000÷46.24)=129。按參考價計 19,909.52，結算現金 90.48（0.45% ≤ 5%）。
**順序：** 先 #2 後 #3。若 #2 成交後現金不足 129 股 IBIT，#3 數量改為 floor(剩餘現金÷IBIT 限價)（兩單皆觸及限價上緣時合計 20,108.35 > 20,000）。
**主動部位：** 無（`aim/cards/` 無稽核維持之 L／M，未凍結任何 P）→ 全額預設袋。
