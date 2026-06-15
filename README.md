# 寶雅 POYA 數位轉型研究報告網站

這是一個單頁式課堂研究報告網站，主題是「寶雅 POYA 數位轉型是否真正創造顧客經營價值？」。

## 啟動

```powershell
.\start_app.ps1
```

如果 Windows PowerShell 執行原則封鎖 `.ps1`，可改用：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_app.ps1
```

開啟：

```text
http://127.0.0.1:8765
```

## 部署到 GitHub Pages

這個網站本體是 `static/` 裡的純靜態檔案，因此可以用 GitHub Pages 上線，不需要在 GitHub 上跑 `server.py`。

1. 在 GitHub 建立一個新 repository。
2. 把這個資料夾推到 GitHub，主要分支請使用 `main`。
3. 到 repository 的 `Settings` -> `Pages`。
4. 在 `Build and deployment` 的 `Source` 選擇 `GitHub Actions`。
5. 推送到 `main` 後，`.github/workflows/pages.yml` 會自動把 `static/` 部署到 GitHub Pages。

上線網址通常會是：

```text
https://你的帳號.github.io/你的倉庫名/
```

## 內容

- 研究問題與分析故事線
- 產業轉型壓力
- 寶雅數位轉型做法
- 營收、電商、會員成效圖表
- 顧客旅程切換
- 寶雅、屈臣氏、康是美比較
- 價值判斷、風險與建議
- 資料來源
