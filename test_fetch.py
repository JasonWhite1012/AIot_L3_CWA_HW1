"""
全台 22 縣市天氣預報讀取測試腳本
Test script for fetching Taiwan Weather Forecast data
"""

import sys
import os

# 解決 Windows 終端機預設 CP950 編碼問題，強制使用 UTF-8
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 將專案根目錄加入模組搜尋路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.fetch_cwa_data import get_taiwan_all_counties_weather, load_cwa_api_key

def main():
    print("=" * 65)
    print(" [Taiwan Weather Forecast] 全台 22 縣市天氣預報讀取測試")
    print("=" * 65)

    api_key = load_cwa_api_key()
    if api_key:
        masked_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else "***"
        print(f"[Key] 檢測到 CWA API Key: {masked_key}")
    else:
        print("[Info] 提示：尚未於 .env 設定 CWA_API_KEY，將啟用離線示範資料進行功能展示。")
        print("       (若要串接即時氣象，請在 .env 檔案中填寫 CWA_API_KEY=你的授權碼)")

    print("\n[...] 正在獲取氣象預報資料...")
    df, is_mock, message = get_taiwan_all_counties_weather()

    print(f"\n[Status] {message}")
    print(f"[Summary] 總筆數: {len(df)} 筆 | 包含縣市數: {df['locationName'].nunique()} 個縣市\n")

    # 挑選關鍵欄位並重命名，方便在終端機漂亮展示
    display_df = df[[
        "locationName", "weather", "minT", "maxT", "avgT", "pop", "comfort"
    ]].rename(columns={
        "locationName": "縣市名稱",
        "weather": "天氣現象",
        "minT": "最低溫(°C)",
        "maxT": "最高溫(°C)",
        "avgT": "平均溫(°C)",
        "pop": "降雨機率(%)",
        "comfort": "舒適度指標"
    })

    # 嘗試使用 tabulate 美化終端表格，若無則用 pandas 原生輸出
    try:
        from tabulate import tabulate
        print(tabulate(display_df, headers="keys", tablefmt="github", showindex=False))
    except ImportError:
        print(display_df.to_string(index=False))

    print("\n" + "=" * 65)
    print("[Success] 測試完成！資料管線與 Pandas 解析運作正常。")
    print("=" * 65)

if __name__ == "__main__":
    main()
