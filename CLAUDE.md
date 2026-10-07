# aim-pm — PM 專用（CHARTER C1.2 §4）

- 只有 `ROLE: PM` 之互動 session 可 clone 本 repo。排程研究輪（SCOUT／ANALYST／AUDITOR）不得 attach。
- 規則來源＝repo `YinchenChang/aim` 之 `AIM_CHARTER.md`；同時 clone 兩個 repo，研究狀態讀 `aim`。
- `pm/LEDGER.md` 正本；P 檔置 `pm/P_<碼>_CL.md`（每次變動另存，§3）；EXECUTE 置 `pm/EXECUTE_YYYYMMDD_CL.md`。
- `aim.py`：`benchmark`／`ledger`／`scorecard`／`sec`／`milestones`／`check-load` 仍可用（需 yfinance、pandas、requests）。**`sync` 已廢**（Drive 時期），勿執行。
- 價格計算在 GitHub Actions（`.github/workflows/ledger.yml`）：每月 1 日及 `data/` 變動時跑 `benchmark`／`ledger`／`scorecard`，回寫 `out/` 與 `pm/LEDGER.md`。雲端 Claude 容器連不到 Yahoo，勿在 session 內跑這三個指令。
- 季輪與起算日 EXECUTE：見 `runbooks/PM_QUARTER.md`（排程「AIM PM quarter」）。
