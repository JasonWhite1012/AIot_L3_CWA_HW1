# 🤖 AI Agent 協作指南 (Agent Guidelines)

本目錄存放用於引導 AI 輔助開發（如 Antigravity / Cursor / Copilot）之設定與專案規範。

---

## 📌 開發與協作守則

1. **架構遵循**：
   - 所有實作應嚴格遵循 [`myplan/design.md`](../myplan/design.md) 定義之分層架構與資料庫 Schema。
   - 階段執行進度請同步參照 [`myplan/workflow.md`](../myplan/workflow.md)。

2. **程式品質要求**：
   - 變數與函式命名採駝峰式（CamelCase）或蛇底式（snake_case）標準風格，並維持整體一致。
   - 關鍵邏輯（尤其是 API 請求與資料庫交易）必須加入適當的例外處理（`try-except`）。
   - 保持資料庫寫入冪等性（Idempotency），重複執行不產生重複資料。

3. **視覺化規範**：
   - Streamlit 佈局應保持簡潔現代，圖表色彩配置須遵循統一色調。
   - 地圖氣溫色標須使用專案定義之 4 階顏色標準。
