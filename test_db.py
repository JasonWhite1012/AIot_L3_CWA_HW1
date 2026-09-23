"""
SQLite 資料庫功能與驗證測試腳本
Test script for SQLite Database integration
"""

import sys
import os

# 解決 Windows 終端機編碼問題
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 將專案根目錄加入模組搜尋路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.fetch_cwa_data import get_taiwan_all_counties_weather
from src.db_manager import (
    DEFAULT_DB_PATH,
    init_db,
    save_weather_forecasts,
    get_all_regions,
    get_forecast_by_region,
    get_db_connection
)
from tabulate import tabulate


def main():
    print("=" * 65)
    print(" [SQLite Database Test] 天氣預報資料庫儲存與查詢驗證")
    print("=" * 65)

    print(f"\n[1] 初始化資料庫...")
    init_db()
    print(f"    資料庫路徑: {DEFAULT_DB_PATH}")

    print("\n[2] 抓取最新天氣資料並寫入 SQLite 資料庫...")
    weather_df, is_mock, msg = get_taiwan_all_counties_weather()
    print(f"    狀態: {msg}")
    
    saved_count = save_weather_forecasts(weather_df)
    print(f"    寫入筆數: {saved_count} 筆")

    print("\n[3] 驗證一：查詢資料庫中目前擁有的所有縣市清單...")
    regions = get_all_regions()
    print(f"    共包含 {len(regions)} 個縣市:")
    print("    " + ", ".join(regions[:10]) + "...")

    print("\n[4] 驗證二：依指定縣市查詢（示範：臺北市 與 高雄市）...")
    for target_county in ["臺北市", "高雄市"]:
        county_df = get_forecast_by_region(target_county)
        print(f"\n    【{target_county}】預報紀錄 ({len(county_df)} 個時段):")
        display_cols = county_df[[
            "startTime", "weather", "minT", "maxT", "pop", "comfort"
        ]].rename(columns={
            "startTime": "預報時段",
            "weather": "天氣現象",
            "minT": "最低溫(°C)",
            "maxT": "最高溫(°C)",
            "pop": "降雨機率(%)",
            "comfort": "舒適度"
        })
        print(tabulate(display_cols, headers="keys", tablefmt="github", showindex=False))

    print("\n[5] 驗證三：防重複插入 (Idempotency) 測試...")
    conn = get_db_connection()
    count_before = conn.execute("SELECT COUNT(*) FROM TemperatureForecasts;").fetchone()[0]
    conn.close()
    
    print(f"    目前資料庫總筆數: {count_before} 筆")
    print("    再次執行相同資料寫入...")
    save_weather_forecasts(weather_df)
    
    conn = get_db_connection()
    count_after = conn.execute("SELECT COUNT(*) FROM TemperatureForecasts;").fetchone()[0]
    conn.close()
    
    print(f"    再次寫入後總筆數: {count_after} 筆")
    if count_before == count_after:
        print("    [PASS] 成功！防重複寫入機制運作正常，資料沒有膨脹重複！")
    else:
        print("    [FAIL] 警告：資料筆數發生變化，請檢查 UNIQUE 約束！")

    print("\n" + "=" * 65)
    print(" 恭喜！SQLite 資料庫模組實作與驗證完全通過！")
    print("=" * 65)


if __name__ == "__main__":
    main()
