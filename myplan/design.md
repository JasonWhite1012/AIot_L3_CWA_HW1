# 📐 Taiwan Weather Forecast 系統設計文件 (Design Document)

---

## 1. 系統架構設計 (System Architecture)

本專案採分層式架構設計（Layered Architecture），將資料獲取、資料持久化與前端呈現解耦，確保程式碼的重用性與可維護性。

```
┌────────────────────────────────────────────────────────┐
│             Streamlit Web Dashboard (app.py)           │
│   ┌─────────────────────┐    ┌─────────────────────┐   │
│   │   地區選擇 & 折線圖  │    │  Folium 互動地圖組件 │   │
│   └─────────────────────┘    └─────────────────────┘   │
└───────────────────────────▲────────────────────────────┘
                            │ SQL Queries
┌───────────────────────────┴────────────────────────────┐
│              資料持久層 (Database Layer)                 │
│                 SQLite Database (data.db)              │
│               Table: TemperatureForecasts              │
└───────────────────────────▲────────────────────────────┘
                            │ ETL Insert / Upsert
┌───────────────────────────┴────────────────────────────┐
│              資料處理層 (ETL & Ingestion Layer)          │
│            fetch_cwa_data.py & db_manager.py           │
│         - JSON 解析  - Pandas 清洗  - 型態轉換          │
└───────────────────────────▲────────────────────────────┘
                            │ HTTP GET (with Auth Header)
┌───────────────────────────┴────────────────────────────┐
│      外部資料源：中央氣象署開放資料平台 (CWA Open Data)    │
└────────────────────────────────────────────────────────┘
```

---

## 2. 資料庫設計 (Database Design)

- **資料庫檔案**：`data.db`（SQLite 3）
- **主要資料表**：`TemperatureForecasts`

### 資料表結構定義 (Schema)

```sql
CREATE TABLE IF NOT EXISTS TemperatureForecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regionName TEXT NOT NULL,
    dataDate TEXT NOT NULL,
    minT REAL NOT NULL,
    maxT REAL NOT NULL,
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(regionName, dataDate) -- 確保同地區同日期不重複插入
);
```

### 欄位詳細說明
| 欄位名稱 | 資料類型 | 限制 | 說明 |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | 流水號主鍵 |
| `regionName` | `TEXT` | `NOT NULL` | 預報地區名稱（如北部、中部、南部、東部等） |
| `dataDate` | `TEXT` | `NOT NULL` | 預報日期，格式為 `YYYY-MM-DD` |
| `minT` | `REAL` | `NOT NULL` | 預報最低溫度（攝氏度 °C） |
| `maxT` | `REAL` | `NOT NULL` | 預報最高溫度（攝氏度 °C） |
| `createdAt`| `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | 寫入資料庫時間戳記 |

---

## 3. CWA API 規格與資料解析 (API Specification)

- **資料集**：全台鄉鎮天氣預報 - 未來一週天氣預報（或分區天氣預報）
- **API 端點 (Endpoint)**：
  ```http
  GET https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001
  Headers:
    Authorization: <CWA_API_KEY>
  ```
- **資料提取路徑**：
  1. 走訪 `records -> location` 陣列。
  2. 擷取 `locationName` 作為 `regionName`。
  3. 走訪 `weatherElement` 尋找 `elementName == 'MinT'` 與 `elementName == 'MaxT'`。
  4. 從 `time` 區塊中解析 `startTime` 轉換為 `YYYY-MM-DD` 日期格式。

---

## 4. 前端介面與互動設計 (UI / UX Design)

### 4.1 頁面佈局 (Layout)
- **側邊欄 (Sidebar)**：
  - API 金鑰狀態與更新資料按鈕 (`Fetch New Data`)。
  - 地區選取下拉式選單（多選/單選）。
  - 日期選取器（用於地圖視覺化）。
- **主要內容區 (Main Content)**：
  - **區域一：關鍵數據指標 (KPI Metrics)**：今日預報高低溫、平均溫、溫差警戒。
  - **區域二：氣溫趨勢圖**：一週最高溫（紅色折線）、最低溫（藍色折線）。
  - **區域三：台灣空間地圖**：Folium 地圖，依照當天溫度區間顯示各區顏色。
  - **區域四：原始資料檢視**：可展開的表格與搜尋過濾。

### 4.2 地圖色標規範 (Temperature Palette)
| 溫度範圍 | 色彩名稱 | Hex 代碼 | 語意 |
| :--- | :--- | :--- | :--- |
| `< 20°C` | 藍色 (Cool Blue) | `#3498db` | 寒冷 / 涼爽 |
| `20°C ~ 25°C` | 綠色 (Comfort Green) | `#2ecc71` | 舒適宜人 |
| `25°C ~ 30°C` | 橙色 (Warm Orange) | `#f39c12` | 偏暖 / 微熱 |
| `> 30°C` | 紅色 (Hot Red) | `#e74c3c` | 炎熱警戒 |

---

## 5. 異常處理與防禦機制 (Error Handling & Robustness)

1. **網路連線失敗**：若 CWA API 回應逾時或狀態碼非 `200`，應回退使用 SQLite 本地已快取的最新資料，並在 Streamlit 介面彈出警告通知。
2. **防重複寫入 (Idempotency)**：使用 `INSERT OR REPLACE INTO` 或 `ON CONFLICT DO UPDATE` 語法，防止定時重複抓取資料時產生冗餘或衝突資料。
3. **無資料保護**：當特定分區或日期缺乏氣溫數據時，以 `N/A` 顯示並在圖表上做平滑缺值處理，避免前端崩潰。
