#!/usr/bin/env python3
"""
aim.py — AIM (Autonomous Investment Mandate) 機械層。CHARTER §6。
只搬、算、列；不做判斷。所有判斷欄由模型填。

安裝:  pip install google-api-python-client google-auth-oauthlib yfinance pandas requests
用法:  python aim.py <指令> [選項]
    init                  建 aim_config.json 範本與本地目錄
    sync --role <角色> [--push charter funnel ledger]
                          正本預設拉；--push 指定者改推回同一 fileId（遠端較新則拒推）；
                          work 產物拉新的、推本地新增的；
                          代移：inbox 之 CONSUMED_<名>（連同標記檔）→ old；work 之 DUP_<名> → old；
                          work 之 USED_<名> → archive_work；work 之 DONE_<名> 代為改名
                          USED_<名> 移入 archive_work、標記檔移 old（GK 無改名與搬移工具）；
                          （inbox 用 CONSUMED_、work 用 DONE_：故意用不同字，同一前綴不得在
                          不同資料夾代表不同事——inbox 之義為「已消化、清掉」，work 之義為
                          「已結案、待歸檔」，混用會讓人只看前綴就會判斷錯）；
                          只有 --role PM 會拉／推 LEDGER（CHARTER §4：非 PM 不碰 AIM/pm/）；
                          LEDGER 本地路徑＝pm/LEDGER.md（不得寫入 AIM 根目錄）；
                          成功後覆寫 query/MECH.md（版本、UTC、本輪 fileId），CHARTER §6；
                          寫 MECH 用暫存檔＋API，不寫根目錄 MECH.md；
                          代移根目錄 stray：AIM/MECH.md、AIM/LEDGER.md（非正本 fileId）
                          改名 STRAY_root_* 移入 old/；本機根目錄同名檔一併移 aside
    benchmark             計算基準 (a) 70/30 季再平衡、(b) S&P 500 TR，寫 data/benchmarks.csv
    ledger                由 data/cashflows.csv + data/trades.csv + 價格算月末 NAV/TWR/對數成長，寫 LEDGER.md
    milestones            掃 work/M_*.md 之里程碑日期，列逾期未解析
    sec --cik 0001769628  列 data.sec.gov 該發行人自 --since 起之 8-K/10-Q
    scorecard             產 SCORECARD 之數字段（A/B/C 部位層與現金拖累/D 之 Brier）
    check-load            核對擬載入 Project knowledge 之檔案位元組數 ≤ 30,000

資料檔格式（UTF-8 CSV，首列為欄名）:
    data/cashflows.csv : date,amount            # 轉入正、轉出負；起算日一筆
    data/trades.csv    : date,symbol,qty,price  # 買正賣負；選擇權以 OCC 代碼，價格=每股（合約乘數 100 自動套用）
    data/marks.csv     : date,symbol,price      # 手填月末價（yfinance 取不到者，如選擇權）
    work/M_<代碼>.md   : 里程碑表列格式 | M-x | YYYY-MM-DD | 來源 | 事前機率 | 極性 | 結果(空=未解析) |
"""
import argparse, csv, json, math, os, re, sys, tempfile, unicodedata
from datetime import date, datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "aim_config.json"
DATA, WORK, OUT = ROOT / "data", ROOT / "work", ROOT / "out"
LOAD_CAP = 30_000
UA = "AIM aim.py Andy Chang kimiochang@yahoo.com.tw"  # SEC 要求 User-Agent 含姓名與 email，否則 403；請改為你的

# ---------- 共用 ----------
def cfg():
    if not CFG.exists():
        sys.exit("缺 aim_config.json，先跑 `aim.py init`")
    return json.loads(CFG.read_text(encoding="utf-8"))

def read_csv(p):
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))

def month_ends(start, end):
    """回傳 start..end 之間每個月末日期（含 end 所在月之月末若 ≤ end）。"""
    import pandas as pd
    return [d.date() for d in pd.date_range(start, end, freq="ME")]

# ---------- init ----------
def cmd_init(a):
    for d in (DATA, WORK, OUT, ROOT / "pm", ROOT / "query"):
        d.mkdir(exist_ok=True)
    if not CFG.exists():
        CFG.write_text(json.dumps({
            "start_date": "2026-10-15",
            "charter_file_id": "", "funnel_file_id": "", "ledger_file_id": "",
            "folders": {"work": "", "inbox_CL": "", "inbox_GK": "", "query": "", "old": "",
                        "pm": "", "archive": "", "archive_work": ""},
            "benchmark_a": {"VTI": 0.7, "BTC-USD": 0.3, "rebalance": "Q"},
            "benchmark_b": "^SP500TR",
            "load_files": ["AIM_CHARTER.md", "AIM_FUNNEL.md"]
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已建 aim_config.json，請填 Drive fileId／資料夾 ID")
    for name, hdr in (("cashflows.csv", "date,amount"), ("trades.csv", "date,symbol,qty,price"),
                      ("marks.csv", "date,symbol,price")):
        p = DATA / name
        if not p.exists():
            p.write_text(hdr + "\n", encoding="utf-8")
    print("目錄就緒：data/ work/ out/ pm/ query/")

def _nfc(s):
    """Unicode 正規化（NFC），避免看起來一樣、底層編碼不同的符號（例如全形／半形底線、不同種連字號）
    導致 DONE_／DUP_ 字串比對明明肉眼一致卻判定不相等而悄悄不生效。"""
    return unicodedata.normalize("NFC", s)

def _move_to_old(svc, file_obj, src_folder, old_folder, label):
    """把單一檔案自 src_folder 移至 old_folder；失敗只印出來，不讓整個 sync 崩潰
    （避免一筆命名異常的檔案擋掉其餘正常項目的搬移與後續步驟）。"""
    try:
        svc.files().update(fileId=file_obj["id"], addParents=old_folder,
                           removeParents=src_folder).execute()
        print(f"代移 Old（{label}）：", file_obj["name"])
        return True
    except Exception as e:
        print(f"⚠ 代移 Old 失敗（{label}）：{file_obj['name']}｜{e}", file=sys.stderr)
        return False

# ---------- Drive ----------
def secrets_dir():
    """credentials.json／token.json 存放處。優先讀環境變數 AIM_SECRETS_DIR（每台機器各自設定、
    不寫進 aim_config.json——因為那份設定檔會被 Drive 同步到兩台機器，路徑寫死在裡面反而互相打架）。
    沒設就退回 ROOT，並印警告：這代表兩個裝置會共用同一份 Drive 上的憑證，容易發生「一邊搬走／刪除，
    另一邊也跟著消失」的同步連動。"""
    env = os.environ.get("AIM_SECRETS_DIR")
    if env:
        d = Path(env); d.mkdir(parents=True, exist_ok=True); return d
    _warn_if_secrets_in_synced_root()
    return ROOT

def _warn_if_secrets_in_synced_root():
    """token.json／credentials.json 若落在 Drive 桌面版掛載路徑下，會被同步進雲端、進而被
    兩個 Project 共讀之 AIM/ 正本樹狀結構間接暴露；多裝置時還會發生互相覆寫／連動刪除。
    只警告，不阻擋（ROOT 判定為啟發式）。"""
    hints = ("雲端硬碟", "google drive", "my drive", "googledrive")
    root_l = str(ROOT).lower()
    if any(h in root_l for h in hints):
        print("⚠ 未設定 AIM_SECRETS_DIR，token.json／credentials.json 會落在 Drive 桌面版掛載路徑下、"
              "跨裝置共用同一份。建議設定環境變數 AIM_SECRETS_DIR 指向本機專屬、不同步的資料夾，"
              "每台裝置各自一份、各自獨立授權。", file=sys.stderr)

def drive():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    sd = secrets_dir()
    scopes = ["https://www.googleapis.com/auth/drive"]
    tok = sd / "token.json"
    creds = Credentials.from_authorized_user_file(tok, scopes) if tok.exists() else None
    # access token 壽命一小時。只判 creds.valid 的話，過期就重跑完整 OAuth，
    # token.json 裡的 refresh_token 永遠用不到——這是每次都跳瀏覽器的原因。
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            tok.write_text(creds.to_json())
            print("token 已續期（未開瀏覽器）")
        except Exception as e:
            print(f"⚠ token 續期失敗，改走完整授權：{e}", file=sys.stderr)
            creds = None
    if not creds or not creds.valid:
        creds = InstalledAppFlow.from_client_secrets_file(sd / "credentials.json", scopes).run_local_server(port=0)
        tok.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)

def drive_list(svc, folder):
    q = f"'{folder}' in parents and trashed = false"
    return svc.files().list(q=q, fields="files(id,name,size,modifiedTime,parents)").execute().get("files", [])

def drive_find(svc, folder, name):
    """在 folder 內依檔名找單一檔案，找不到回 None。"""
    for f in drive_list(svc, folder):
        if f["name"] == name:
            return f
    return None

def drive_pull(svc, fid, dest):
    from googleapiclient.http import MediaIoBaseDownload
    import io
    buf = io.BytesIO(); dl = MediaIoBaseDownload(buf, svc.files().get_media(fileId=fid))
    done = False
    while not done:
        _, done = dl.next_chunk()
    dest.write_bytes(buf.getvalue())

def drive_push_new(svc, path, folder):
    """只新建，不覆寫（CHARTER §6 之 Drive 寫入原則；正本原地更新用 drive_update）。"""
    from googleapiclient.http import MediaFileUpload
    meta = {"name": path.name, "parents": [folder]}
    return svc.files().create(body=meta, media_body=MediaFileUpload(str(path), mimetype="text/markdown"),
                              fields="id").execute()["id"]

def drive_update(svc, fid, path):
    """正本（CHARTER/FUNNEL/LEDGER）原地更新，fileId 不變。"""
    from googleapiclient.http import MediaFileUpload
    svc.files().update(fileId=fid, media_body=MediaFileUpload(str(path), mimetype="text/markdown")).execute()

def drive_push_canonical(svc, fid, path, label):
    """把本地正本推回 Drive 同一 fileId。推之前比對時間：遠端較新就不推——
    兩個平台、兩台裝置都會改同一份 FUNNEL，無條件覆蓋遲早會無聲吃掉一次修改。"""
    meta = svc.files().get(fileId=fid, fields="modifiedTime,name").execute()
    remote = datetime.fromisoformat(meta["modifiedTime"].replace("Z", "+00:00"))
    local = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    if remote > local:
        print(f"⚠ 略過推 {label}：Drive 版本較新（{meta['modifiedTime']}），"
              f"請先不帶 --push 拉一次再改", file=sys.stderr)
        return False
    drive_update(svc, fid, path)
    print(f"推 {label}（fileId 不變）")
    return True

def _rename_and_move(svc, file_obj, src_folder, dst_folder, new_name, label):
    """改名並搬移，一次 API 呼叫完成——分兩步會在失敗時留下改了名卻沒搬走的中間態。
    fileId 不變，故既有的 fileId 引用不會斷。"""
    try:
        svc.files().update(fileId=file_obj["id"], body={"name": new_name},
                           addParents=dst_folder, removeParents=src_folder).execute()
        print(f"代移 {label}：", file_obj["name"], "→", new_name)
        return True
    except Exception as e:
        print(f"⚠ 代移 {label} 失敗：{file_obj['name']}｜{e}", file=sys.stderr)
        return False

def canon_path(tag, name):
    """正本本地路徑。CHARTER／FUNNEL 在 AIM 根；LEDGER 在 AIM/pm/（CHARTER §4）。
    寫到根目錄的 LEDGER.md／MECH.md 會被 Drive 桌面版建成第二個 fileId。"""
    if tag == "ledger":
        p = ROOT / "pm" / name
        p.parent.mkdir(exist_ok=True)
        return p
    return ROOT / name

def _unique_name(existing, base):
    """在 existing（名稱集合）內產生不衝突的檔名：base、stem_2.ext、stem_3.ext…"""
    if base not in existing:
        return base
    if "." in base:
        stem, ext = base.rsplit(".", 1)
        ext = "." + ext
    else:
        stem, ext = base, ""
    n = 2
    while True:
        cand = f"{stem}_{n}{ext}"
        if cand not in existing:
            return cand
        n += 1

def _aim_root_id(svc, c):
    """AIM 根目錄 ID＝CHARTER／FUNNEL 之 parent；缺則用 work 資料夾之 parent。"""
    for key in ("charter_file_id", "funnel_file_id"):
        fid = c.get(key)
        if not fid:
            continue
        try:
            parents = svc.files().get(fileId=fid, fields="parents").execute().get("parents") or []
        except Exception as e:
            print(f"⚠ 取 {key} parent 失敗：{e}", file=sys.stderr)
            continue
        if parents:
            return parents[0]
    work = (c.get("folders") or {}).get("work")
    if work:
        try:
            parents = svc.files().get(fileId=work, fields="parents").execute().get("parents") or []
            if parents:
                return parents[0]
        except Exception as e:
            print(f"⚠ 取 work parent 失敗：{e}", file=sys.stderr)
    return None

def _retire_local_root_strays():
    """本機 AIM 根目錄的 MECH.md／LEDGER.md 不是正本。移到本地 old/，避免 Drive 桌面版
    在 API 代移後又把根目錄檔重新上傳成新 fileId。"""
    old_dir = ROOT / "old"
    old_dir.mkdir(exist_ok=True)
    for name in ("MECH.md", "LEDGER.md"):
        src = ROOT / name
        if not src.is_file():
            continue
        dest = old_dir / f"STRAY_root_{name}"
        dest = old_dir / _unique_name({p.name for p in old_dir.iterdir()}, dest.name)
        src.replace(dest)
        print(f"本地根目錄 stray 已移：{name} → {dest.relative_to(ROOT)}")

def _sweep_root_strays(svc, c):
    """Drive AIM 根目錄之 MECH.md／LEDGER.md，若 fileId 不是 query/MECH、pm/LEDGER 正本，
    改名 STRAY_root_* 移 old/。不 trash。"""
    folders = c.get("folders") or {}
    old_fid = folders.get("old")
    root_fid = _aim_root_id(svc, c)
    if not root_fid or not old_fid:
        print("⚠ 無法掃根目錄 stray：缺 AIM 根或 folders.old", file=sys.stderr)
        return
    q_folder = folders.get("query")
    mech_canon = None
    if q_folder:
        found = drive_find(svc, q_folder, "MECH.md")
        mech_canon = found["id"] if found else None
    ledger_canon = c.get("ledger_file_id") or None
    canon_ids = {i for i in (mech_canon, ledger_canon) if i}
    old_names = {f["name"] for f in drive_list(svc, old_fid)}
    for f in drive_list(svc, root_fid):
        if f["name"] not in ("MECH.md", "LEDGER.md"):
            continue
        if f["id"] in canon_ids:
            print(f"⚠ 正本 {f['name']} fileId {f['id']} 出現在 AIM 根目錄，不代移", file=sys.stderr)
            continue
        stem = f["name"].rsplit(".", 1)[0]
        new_name = _unique_name(old_names, f"STRAY_root_{stem}.md")
        if _rename_and_move(svc, f, root_fid, old_fid, new_name, "root stray"):
            old_names.add(new_name)

CANON = {"charter": ("charter_file_id", "AIM_CHARTER.md"),
         "funnel":  ("funnel_file_id",  "AIM_FUNNEL.md"),
         "ledger":  ("ledger_file_id",  "LEDGER.md")}

def cmd_sync(a):
    c, svc = cfg(), drive()
    WORK.mkdir(exist_ok=True)
    (ROOT / "pm").mkdir(exist_ok=True)
    (ROOT / "query").mkdir(exist_ok=True)
    touched = {}
    # 0. 根目錄 stray：先移本機、再 API 代移。否則步驟 1／5 即使改走正確路徑，
    #    Drive 桌面版仍會把殘留的根目錄 MECH.md／LEDGER.md 再上傳成新 fileId。
    _retire_local_root_strays()
    _sweep_root_strays(svc, c)
    # 1. 正本：預設拉；--push 指定者改推。CHARTER §4：非 PM 不碰 LEDGER，拉推皆然。
    push = set(getattr(a, "push", None) or [])
    if "ledger" in push and a.role != "PM":
        sys.exit("只有 PM 可推 LEDGER（CHARTER §4）")
    for tag, (key, name) in CANON.items():
        if tag == "ledger" and a.role != "PM":
            print(f"角色 {a.role}：略過 LEDGER（CHARTER §4 非 PM 不下載）")
            continue
        if not c.get(key):
            continue
        path = canon_path(tag, name)
        rel = path.relative_to(ROOT).as_posix()
        if tag in push:
            if not path.exists():
                sys.exit(f"缺本地 {rel}，無法推")
            if drive_push_canonical(svc, c[key], path, rel):
                touched[name] = c[key]
        else:
            drive_pull(svc, c[key], path); print("拉", rel); touched[name] = c[key]
    # 2. work 資料夾的三種前綴（載入器第 12 條：先完成、後加前綴、再搬移；腳本不判斷是否結案，
    #    只執行角色已經下過的標記）：
    #      DUP_<名>  誤植之重複產出，本檔本身即錯誤            → old（原檔留在 work）
    #      USED_<名> 已結案，CL 自行改名                        → archive_work
    #      DONE_<名> GK 之結案標記（GK 無改名與搬移工具）       → 原檔改名 USED_<名> 移入
    #                archive_work，標記檔移 old
    #    三者本地若已存在，也不再被步驟末的「推(新建)」誤送回 Drive。
    archived_names = set()
    if c["folders"].get("work"):
        work_fid = c["folders"]["work"]
        old_fid = c["folders"]["old"]
        arch_fid = c["folders"].get("archive_work")
        if not arch_fid:
            print("⚠ aim_config.json 缺 folders.archive_work，USED_／DONE_ 不搬", file=sys.stderr)
        remote = {f["name"]: f for f in drive_list(svc, work_fid)}
        norm_remote = {_nfc(n): n for n in remote}
        for name in list(remote):
            if name.startswith("DUP_"):
                if _nfc(name[4:]) in norm_remote:
                    if _move_to_old(svc, remote[name], work_fid, old_fid, "work DUP_"):
                        archived_names.add(name)
            elif name.startswith("USED_"):
                if arch_fid and _rename_and_move(svc, remote[name], work_fid, arch_fid,
                                                 name, "archive_work"):
                    archived_names.add(name)
            elif name.startswith("DONE_"):
                stem = _nfc(name[5:])
                if stem not in norm_remote:
                    print(f"⚠ work 有 {name}，但找不到對應原檔（已試 NFC 正規化比對），略過",
                          file=sys.stderr)
                    continue
                orig_name = norm_remote[stem]
                if arch_fid and _rename_and_move(svc, remote[orig_name], work_fid, arch_fid,
                                                 "USED_" + orig_name, "archive_work"):
                    _move_to_old(svc, remote[name], work_fid, old_fid, "work DONE_標記")
                    archived_names.update({name, orig_name})
        for name in archived_names:
            remote.pop(name, None)
        # 拉 work 資料夾產物；推本地新增之產物
        for f in remote.values():
            if not (WORK / f["name"]).exists():
                drive_pull(svc, f["id"], WORK / f["name"]); print("拉", f["name"])
        for p in WORK.glob("*.md"):
            if p.name in archived_names or p.name.startswith(("DUP_", "USED_", "DONE_")):
                continue
            if p.name not in remote:
                drive_push_new(svc, p, work_fid); print("推(新建)", p.name)
    # 3. 收件匣：GK 無搬移 → 見 CONSUMED_<名> 即把原檔與 CONSUMED_ 標記檔一併移 old
    #    （標記檔的任務只是告訴 sync「這份已處理」，搬完 old 後留著沒有用途，一併清掉才不會讓
    #    inbox 隨時間一直堆積用過的標記。故意不叫 DONE_：work/ 的 DONE_ 是「結案待歸檔」，
    #    inbox 的這個是「已消化待清除」，語意不同、下場也不同，同名會誤導只看前綴的判讀）
    for box in ("inbox_CL", "inbox_GK"):
        fid = c["folders"].get(box)
        if not fid:
            continue
        files = {f["name"]: f for f in drive_list(svc, fid)}
        norm_files = {_nfc(n): n for n in files}
        for name in list(files):
            if not name.startswith("CONSUMED_"):
                continue
            stem = _nfc(name[9:])
            if stem not in norm_files:
                print(f"⚠ {box} 有 {name}，但找不到對應原檔（已試 NFC 正規化比對），略過", file=sys.stderr)
                continue
            orig = files[norm_files[stem]]
            done = files[name]
            _move_to_old(svc, orig, fid, c["folders"]["old"], f"{box} 原檔")
            _move_to_old(svc, done, fid, c["folders"]["old"], f"{box} CONSUMED_標記")
    # 4. 推本地 LEDGER（由 cmd_ledger 產出；只有 PM 推，理由同 §1 之下載限制）
    if (a.role == "PM" and "ledger" not in push and c.get("ledger_file_id")
            and (OUT / "LEDGER.md").exists()):
        drive_update(svc, c["ledger_file_id"], OUT / "LEDGER.md"); print("更新 LEDGER 正本（fileId 不變）")
        touched["LEDGER.md"] = c["ledger_file_id"]
    # 5. MECH 心跳（CHARTER §6：每次成功覆寫 query/MECH.md：版本、UTC、本輪 fileId）
    q_folder = c["folders"].get("query")
    if q_folder:
        ver = "unknown"
        chp = ROOT / "AIM_CHARTER.md"
        if chp.exists():
            m = re.search(r"AIM-C[\d.]+@\w+", chp.read_text(encoding="utf-8"))
            if m:
                ver = m.group(0)
        mech = "\n".join([
            "# MECH — 機械層心跳（aim.py sync 自動生成；手寫無效）",
            f"version: {ver}",
            f"role: {a.role}",
            f"last_sync_utc: {datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')}",
            "synced_fileIds:",
            *[f"  {k}: {v}" for k, v in touched.items()],
        ]) + "\n"
        # 暫存檔＋API 更新 query/MECH.md。不得寫 ROOT/MECH.md：Drive 桌面版會在 AIM 根目錄
        # 另建一個 fileId，與 query/MECH.md 正本並存。
        with tempfile.TemporaryDirectory(prefix="aim_mech_") as td:
            mech_path = Path(td) / "MECH.md"
            mech_path.write_text(mech, encoding="utf-8")
            existing = drive_find(svc, q_folder, "MECH.md")
            if existing:
                drive_update(svc, existing["id"], mech_path); print("更新 MECH 心跳（fileId 不變）")
            else:
                new_id = drive_push_new(svc, mech_path, q_folder)
                print("建立 MECH 心跳，fileId：", new_id, "— 請視需要記入 aim_config.json（非必要，sync 每次會自行按檔名找回）")
        _sweep_root_strays(svc, c)
    else:
        print("⚠ aim_config.json 缺 folders.query，無法寫 MECH 心跳")

# ---------- 價格 ----------
def prices(symbols, start, end):
    """月末收盤。取不到者回 NaN；marks.csv 之手填值優先。"""
    import pandas as pd, yfinance as yf
    idx = pd.DatetimeIndex(month_ends(start, end))
    px = pd.DataFrame(index=idx)
    for s in symbols:
        try:
            h = yf.download(s, start=start, end=end, progress=False, auto_adjust=True)["Close"]
            h = h.squeeze() if hasattr(h, "squeeze") else h
            px[s] = h.resample("ME").last().reindex(idx)
        except Exception as e:  # noqa
            px[s] = float("nan")
    for r in read_csv(DATA / "marks.csv"):
        d = pd.Timestamp(r["date"]).to_period("M").to_timestamp("M")
        px.loc[d, r["symbol"]] = float(r["price"])
    return px

# ---------- benchmark ----------
def cmd_benchmark(a):
    import pandas as pd
    c = cfg(); start, end = c["start_date"], date.today().isoformat()
    ba = c["benchmark_a"]; wts = {k: v for k, v in ba.items() if k != "rebalance"}
    px = prices(list(wts) + [c["benchmark_b"]], start, end)
    ret = px.pct_change().fillna(0.0)
    # (a) 固定權重，季再平衡：每季末重設權重，季內權重隨價格漂移
    nav_a, w = 1.0, dict(wts); out = []
    for i, (d, r) in enumerate(ret.iterrows()):
        if i == 0:
            out.append((d.date(), 1.0, 1.0)); continue
        g = sum(w[s] * (1 + r[s]) for s in w)
        nav_a *= g
        w = {s: w[s] * (1 + r[s]) / g for s in w}
        if ba.get("rebalance") == "Q" and d.month in (3, 6, 9, 12):
            w = dict(wts)
        nav_b = (1 + ret[c["benchmark_b"]].iloc[:i + 1]).prod()
        out.append((d.date(), nav_a, float(nav_b)))
    OUT.mkdir(exist_ok=True)
    with (OUT / "benchmarks.csv").open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f); wr.writerow(["date", "nav_a", "nav_b"]); wr.writerows(out)
    print("寫 out/benchmarks.csv，", len(out), "列")

# ---------- ledger ----------
def twr_and_log(navs, flows):
    """時間加權報酬鏈：每期 r = (NAV_t - flow_t) / NAV_{t-1} - 1；對數成長 = Σ ln(1+r)。"""
    chain, logs = 1.0, 0.0
    for i in range(1, len(navs)):
        prev = navs[i - 1]
        if prev <= 0:
            break
        r = (navs[i] - flows[i]) / prev - 1
        chain *= 1 + r; logs += math.log(1 + r)
    return chain - 1, logs

def _ledger_local_path():
    """LEDGER 本地正本路徑（CHARTER §4：AIM/pm/LEDGER.md）。cmd_ledger 讀它取得「標頭」
    「預設袋」「### 部位」「### 執行回填」等由 PM／使用者維護之欄位；只重算並取代「## 數字表」
    主表本身（CHARTER §3.1：覆寫數字表節時不得動前兩節；### 部位／執行回填為使用者依實際成交
    回填之資料，CHARTER §9，aim.py 同樣不得覆寫，原樣保留）。"""
    return canon_path("ledger", "LEDGER.md")

def _split_ledger_sections(text):
    """把本地 LEDGER 正本切成三段：(a) 開頭至「## 數字表」之前（標頭＋預設袋，原樣保留）、
    (b) 「## 數字表」起至「### 部位」之前（本函式重算取代的範圍）、
    (c) 「### 部位」起至檔尾（部位／執行回填子表與結尾備註，原樣保留）。
    回傳 (prefix, suffix)；找不到任一標記即報錯——寧可停下也不要用錯誤假設覆寫使用者資料。"""
    i_num = text.find("## 數字表")
    if i_num == -1:
        sys.exit("本地 pm/LEDGER.md 找不到「## 數字表」標記，結構不符預期，先跑 `aim.py sync --role PM` 拉最新正本")
    i_pos = text.find("### 部位", i_num)
    if i_pos == -1:
        sys.exit("本地 pm/LEDGER.md 找不到「### 部位」標記，結構不符預期，先跑 `aim.py sync --role PM` 拉最新正本")
    return text[:i_num], text[i_pos:]

def cmd_ledger(a):
    import pandas as pd
    c = cfg(); start, end = c["start_date"], date.today().isoformat()
    local = _ledger_local_path()
    if not local.exists():
        sys.exit(f"缺本地 {local.relative_to(ROOT).as_posix()}，先跑 `aim.py sync --role PM` 拉正本")
    prefix, suffix = _split_ledger_sections(local.read_text(encoding="utf-8"))
    bm = read_csv(OUT / "benchmarks.csv")
    if not bm:
        sys.exit("缺 out/benchmarks.csv，先跑 `aim.py benchmark`")
    bm_by_date = {r["date"]: r for r in bm}

    ba = c["benchmark_a"]
    basket_syms = {k for k in ba if k != "rebalance"}  # 假設：trades.csv 內屬於此集合者一律計為預設袋部位，
                                                        # 其餘計為主動部位（見本次修補說明的已知限制）
    flows = read_csv(DATA / "cashflows.csv"); trades = read_csv(DATA / "trades.csv")
    syms = sorted({t["symbol"] for t in trades})
    px = prices(syms, start, end)

    rows, navs, fl = [], [], []
    for d in px.index:
        dd = d.date()
        cash = sum(float(f["amount"]) for f in flows if date.fromisoformat(f["date"]) <= dd)
        pos = {}
        for t in trades:
            if date.fromisoformat(t["date"]) <= dd:
                mult = 100 if re.search(r"\d{6}[CP]\d{8}$", t["symbol"]) else 1  # OCC 選擇權代碼
                q, p = float(t["qty"]), float(t["price"])
                pos[t["symbol"]] = pos.get(t["symbol"], 0) + q
                cash -= q * p * mult
        basket_mv = active_mv = 0.0
        for s, q in pos.items():
            mult = 100 if re.search(r"\d{6}[CP]\d{8}$", s) else 1
            p = px.loc[d, s] if s in px.columns else float("nan")
            if q and math.isnan(p):
                print(f"⚠ {dd} {s} 無價格，請填 data/marks.csv"); p = 0.0
            mv = q * p * mult
            if s in basket_syms:
                basket_mv += mv
            else:
                active_mv += mv
        nav = cash + basket_mv + active_mv
        fin = sum(float(f["amount"]) for f in flows if date.fromisoformat(f["date"]) <= dd
                  and (not navs or date.fromisoformat(f["date"]) > rows[-1][0]))
        rows.append((dd, round(cash, 2), round(basket_mv, 2), round(active_mv, 2), round(nav, 2)))
        navs.append(nav); fl.append(fin if navs[:-1] else 0.0)

    twr, lg = twr_and_log(navs, fl)
    mdd = max(((max(navs[:i + 1]) - navs[i]) / max(navs[:i + 1]) if max(navs[:i + 1]) > 0 else 0.0)
              for i in range(len(navs))) if navs else 0.0

    lines = ["## 數字表（`aim.py` 覆寫區；起算前為空）", "",
             f"**起算至今：** 時間加權對數成長率 {twr:.2%}　最大回撤 {mdd:.1%}"
             f"（本次由 aim.py 於 {date.today()} 重算）", "",
             "| 月末 | 池NAV | 預設袋市值 | 主動部位市值 | 結算現金 | 結算現金/NAV | (a) 月末值 | (b) 月末值 | 當月對數成長 |",
             "|---|---|---|---|---|---|---|---|---|"]
    prev_nav = None
    for i, (dd, cash, basket_mv, active_mv, nav) in enumerate(rows):
        r = bm_by_date.get(dd.isoformat())
        a_val = f"{float(r['nav_a']):.4f}" if r else "—"
        b_val = f"{float(r['nav_b']):.4f}" if r else "—"
        cash_ratio = f"{cash / nav:.1%}" if nav else "—"
        if prev_nav and prev_nav > 0 and (nav - fl[i]) > 0:
            per_s = f"{math.log((nav - fl[i]) / prev_nav):+.4f}"
        else:
            per_s = "—"
        lines.append(f"| {dd} | {nav:,.0f} | {basket_mv:,.0f} | {active_mv:,.0f} | "
                      f"{cash:,.0f} | {cash_ratio} | {a_val} | {b_val} | {per_s} |")
        prev_nav = nav
    numeric_block = "\n".join(lines) + "\n\n"

    OUT.mkdir(exist_ok=True)
    (OUT / "LEDGER.md").write_text(prefix + numeric_block + suffix, encoding="utf-8")
    print("寫 out/LEDGER.md（已保留標頭／預設袋／部位／執行回填）；TWR", f"{twr:.2%}", "log", round(lg, 4))

# ---------- milestones ----------
ROW = re.compile(r"^\|\s*(M-[\w′']+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|")
def cmd_milestones(a):
    today, hits = date.today(), []
    for p in sorted(WORK.glob("M_*.md")):
        for line in p.read_text(encoding="utf-8").splitlines():
            m = ROW.match(line)
            if not m:
                continue
            mid, d, src, prior, pol, res = [x.strip() for x in m.groups()]
            due = date.fromisoformat(d)
            if not res and due <= today:
                hits.append((p.name, mid, d, src, prior, pol))
    if not hits:
        print("無逾期未解析里程碑"); return
    print("逾期未解析（ANALYST 須解析，PM 依 CHARTER §3-M 階梯）：")
    for h in hits:
        print(" | ".join(h))

# ---------- SEC ----------
def cmd_sec(a):
    import requests
    cik = a.cik.zfill(10); since = a.since or cfg()["start_date"]
    r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status(); j = r.json(); f = j["filings"]["recent"]
    print(j["name"], "| 自", since)
    n = 0
    for form, dt, acc, doc in zip(f["form"], f["filingDate"], f["accessionNumber"], f["primaryDocument"]):
        if dt >= since and form in ("8-K", "8-K/A", "10-Q", "10-K", "10-Q/A"):
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
            print(f"{dt} {form:6} {url}"); n += 1
    print(n, "筆。腳本不判內容；由 ANALYST 讀。")

# ---------- scorecard ----------
def cmd_scorecard(a):
    """A 績效 / B 相對績效 / C 部位層與現金拖累 / D Brier。決策層歸因之選券與表達工具欄由 PM 補。"""
    import pandas as pd
    bm = read_csv(OUT / "benchmarks.csv")
    if not (OUT / "LEDGER.md").exists() or not bm:
        sys.exit("先跑 ledger 與 benchmark")
    led = [l for l in (OUT / "LEDGER.md").read_text(encoding="utf-8").splitlines() if l.startswith("| 20")]
    navs = [float(l.split("|")[2].replace(",", "")) for l in led]  # 新 9 欄格式：欄2＝池NAV（舊格式為欄4）
    dates = [l.split("|")[1].strip() for l in led]
    a_nav = [float(r["nav_a"]) for r in bm][:len(navs)]; b_nav = [float(r["nav_b"]) for r in bm][:len(navs)]
    def lg(x): return math.log(x[-1] / x[0]) if len(x) > 1 and x[0] > 0 and x[-1] > 0 else float("nan")
    mdd = max((max(navs[:i + 1]) - navs[i]) / max(navs[:i + 1]) for i in range(len(navs))) if navs else 0
    # D: Brier 自 work/M_*.md 已解析列（結果欄 1/0）
    n, brier = 0, 0.0
    for p in WORK.glob("M_*.md"):
        for line in p.read_text(encoding="utf-8").splitlines():
            m = ROW.match(line)
            if m and m.group(6).strip() in ("1", "0"):
                pr = float(m.group(4).strip().rstrip("%")) / 100; y = int(m.group(6).strip())
                brier += (pr - y) ** 2; n += 1
    txt = [f"# SCORECARD 數字段（腳本；{date.today()}）", "",
           "## A 績效", f"起算至今對數成長 {lg(navs):.4f}；最大回撤 {mdd:.1%}；期間 {dates[0]} → {dates[-1]}", "",
           "## B 相對績效", f"vs (a) 70/30：{lg(navs) - lg(a_nav):+.4f}（對數差）；vs (b) S&P 500 TR：{lg(navs) - lg(b_nav):+.4f}", "",
           "## C 歸因（部位層與現金拖累由 LEDGER 逐月 weight×return 計；選券／尺碼／表達工具欄由 PM 填）",
           "（部位層明細見 out/attribution.csv — 本版待 LEDGER 含逐部位月報酬後啟用）", "",
           "## D 校準", f"Brier {brier / n:.3f}（n={n}）" if n else "Brier —（n=0，統計上不可分辨）", "",
           "## E 判讀", "（PM 填，≤ 400 字；含 §5 必答題）"]
    (OUT / "SCORECARD_numbers.md").write_text("\n".join(txt) + "\n", encoding="utf-8"); print("\n".join(txt))

# ---------- check-load ----------
def cmd_check(a):
    tot = 0
    for name in cfg()["load_files"]:
        p = ROOT / name
        if not p.exists():
            print("缺", name); continue
        b = p.stat().st_size; tot += b; print(f"{name}: {b:,} B")
    print(f"合計 {tot:,} B / {LOAD_CAP:,}", "✅" if tot <= LOAD_CAP else "❌ 超載，CHARTER §8")
    if tot > LOAD_CAP:
        sys.exit(1)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("init", cmd_init), ("benchmark", cmd_benchmark), ("ledger", cmd_ledger),
                     ("milestones", cmd_milestones), ("scorecard", cmd_scorecard), ("check-load", cmd_check)):
        sub.add_parser(name).set_defaults(fn=fn)
    sy = sub.add_parser("sync")
    sy.add_argument("--role", required=True, choices=["SCOUT", "ANALYST", "AUDITOR", "PM"],
                     help="CHARTER §4 之角色；只有 PM 會拉/推 LEDGER")
    sy.add_argument("--push", nargs="*", default=[], choices=["charter", "funnel", "ledger"],
                    help="把本地該正本推回 Drive 同一 fileId；未列者一律拉")
    sy.set_defaults(fn=cmd_sync)
    s = sub.add_parser("sec"); s.add_argument("--cik", required=True); s.add_argument("--since"); s.set_defaults(fn=cmd_sec)
    args = ap.parse_args(); args.fn(args)
