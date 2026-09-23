"""
SQLite 資料庫管理模組
Database Manager for Taiwan Weather Forecast

負責 SQLite 本地資料庫 (data/data.db) 的初始化、資料表建立、
防重複寫入 (Upsert) 以及高效 SQL 查詢函式。
"""

import os
import sqlite3
import logging
from typing import List, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# 預設資料庫路徑
DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "data.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    取得 SQLite 資料庫連線，若目錄不存在則自動建立
    """
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return sqlite3.connect(db_path)


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    初始化資料庫並建立 TemperatureForecasts 資料表 (若不存在)
    設定 UNIQUE(regionName, startTime) 確保重複抓取時不重複插入資料
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS TemperatureForecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        regionName TEXT NOT NULL,
        startTime TEXT NOT NULL,
        endTime TEXT NOT NULL,
        weather TEXT,
        minT REAL NOT NULL,
        maxT REAL NOT NULL,
        avgT REAL,
        pop INTEGER,
        comfort TEXT,
        updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(regionName, startTime)
    );
    """
    cursor.execute(create_table_sql)
    conn.commit()
    conn.close()
    logger.info(f"資料庫與資料表 TemperatureForecasts 初始化完成: {db_path}")


def save_weather_forecasts(df: pd.DataFrame, db_path: str = DEFAULT_DB_PATH) -> int:
    """
    將 Pandas DataFrame 的氣象預報資料寫入 SQLite 資料庫。
    使用 INSERT OR REPLACE 達成防重複插入（當地區與時段相同時自動更新數據）。

    :param df: 包含氣象資料的 DataFrame
    :param db_path: 資料庫路徑
    :return: 寫入/更新的筆數
    """
    if df.empty:
        logger.warning("DataFrame 為空，無資料寫入。")
        return 0
        
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    upsert_sql = """
    INSERT OR REPLACE INTO TemperatureForecasts 
    (regionName, startTime, endTime, weather, minT, maxT, avgT, pop, comfort, updatedAt)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
    """
    
    records = []
    for _, row in df.iterrows():
        records.append((
            str(row.get("locationName", "")),
            str(row.get("startTime", "")),
            str(row.get("endTime", "")),
            str(row.get("weather", "")),
            float(row.get("minT", 0.0)),
            float(row.get("maxT", 0.0)),
            float(row.get("avgT", 0.0)) if pd.notnull(row.get("avgT")) else None,
            int(row.get("pop", 0)) if pd.notnull(row.get("pop")) else 0,
            str(row.get("comfort", ""))
        ))
        
    cursor.executemany(upsert_sql, records)
    conn.commit()
    inserted_count = cursor.rowcount
    conn.close()
    
    logger.info(f"成功儲存/更新 {len(records)} 筆氣象資料至 {db_path}")
    return len(records)


def get_all_regions(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """
    查詢資料庫中所有的縣市/地區名稱（供 Streamlit 下拉式選單使用）
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT regionName FROM TemperatureForecasts ORDER BY regionName;")
    rows = cursor.fetchall()
    conn.close()
    
    return [row[0] for row in rows]


def get_forecast_by_region(region_name: str, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    依指定縣市名稱查詢該地區未來的氣象預報，回傳 Pandas DataFrame
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    query_sql = """
    SELECT regionName, startTime, endTime, weather, minT, maxT, avgT, pop, comfort, updatedAt
    FROM TemperatureForecasts
    WHERE regionName = ?
    ORDER BY startTime ASC;
    """
    df = pd.read_sql_query(query_sql, conn, params=(region_name,))
    conn.close()
    return df


def get_all_latest_forecasts(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    讀取所有縣市的預報資料，回傳 Pandas DataFrame
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    query_sql = """
    SELECT id, regionName, startTime, endTime, weather, minT, maxT, avgT, pop, comfort
    FROM TemperatureForecasts
    ORDER BY startTime ASC, regionName ASC;
    """
    df = pd.read_sql_query(query_sql, conn)
    conn.close()
    return df
