"""
中央氣象署 (CWA) 天氣預報資料擷取與解析模組
Taiwan Weather Forecast - CWA Open Data Ingestion Module

支援全台 22 縣市的天氣預報資料取得、JSON 階層解析與 Pandas 結構化轉換。
包含 API Key 驗證、例外防禦機制與離線示範資料回退。
"""

import os
import json
import logging
from typing import Dict, Any, Tuple, Optional
import requests
import pandas as pd
from dotenv import load_dotenv

# 設定日誌格式
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# CWA 開放資料 API 設定
CWA_API_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
DATASET_36H_FORECAST = "F-C0032-001"  # 一般天氣預報-今明36小時天氣預報 (全台22縣市)

# 台灣 22 個主要縣市清單
TAIWAN_COUNTIES = [
    # 北部
    "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "宜蘭縣",
    # 中部
    "苗栗縣", "臺中市", "彰化縣", "南投縣", "雲林縣",
    # 南部
    "嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣",
    # 東部
    "花蓮縣", "臺東縣",
    # 離島
    "澎湖縣", "金門縣", "連江縣"
]


def load_cwa_api_key() -> Optional[str]:
    """
    從環境變數或 .env 檔案中讀取 CWA API Key
    """
    load_dotenv()
    api_key = os.getenv("CWA_API_KEY")
    if api_key and api_key != "your_cwa_api_key_here":
        return api_key.strip()
    return None


def fetch_cwa_raw_json(api_key: str, dataset_id: str = DATASET_36H_FORECAST) -> Dict[str, Any]:
    """
    發送 HTTP GET 請求至 CWA Open Data API 取得原始 JSON 資料

    :param api_key: CWA 授權碼
    :param dataset_id: 資料集代碼 (預設為 F-C0032-001)
    :return: 回傳原始 JSON 字典
    :raises requests.RequestException: 網路連線或 API 伺服器異常
    """
    url = f"{CWA_API_BASE_URL}/{dataset_id}"
    headers = {
        "Authorization": api_key,
        "Accept": "application/json"
    }
    
    logger.info(f"正在向中央氣象署 API 發送請求: {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.SSLError:
        logger.warning("偵測到 Windows SSL 憑證鏈結校驗限制，切換為相容模式連線...")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, headers=headers, timeout=10, verify=False)
    
    if response.status_code == 401 or response.status_code == 403:
        raise ValueError("CWA API Key 認證失敗，請確認授權碼是否正確或已啟用。")
    
    response.raise_for_status()
    data = response.json()
    
    if not data.get("success") == "true":
        error_msg = data.get("result", {}).get("message", "未知 API 錯誤")
        raise ValueError(f"CWA API 回傳失敗: {error_msg}")
        
    return data


def parse_cwa_36h_forecast(raw_json: Dict[str, Any]) -> pd.DataFrame:
    """
    解析 F-C0032-001 (36小時天氣預報) 的 JSON 結構，轉換為平坦化的 Pandas DataFrame

    :param raw_json: 氣象署回傳之原始 JSON
    :return: 包含全台各縣市預報的 Pandas DataFrame
    """
    records = raw_json.get("records", {})
    locations = records.get("location", [])
    
    if not locations:
        raise ValueError("氣象資料中未找到任何縣市 (location) 紀錄。")
        
    parsed_rows = []
    
    for loc in locations:
        county_name = loc.get("locationName", "")
        weather_elements = loc.get("weatherElement", [])
        
        # 建立天氣要素對照表: element_map[element_name] = [time_slots...]
        element_map = {}
        for elem in weather_elements:
            elem_name = elem.get("elementName", "")
            element_map[elem_name] = elem.get("time", [])
            
        # 取得時段數量 (一般為 3 個時段: 今早/今晚/明日)
        wx_times = element_map.get("Wx", [])
        num_slots = len(wx_times)
        
        for slot_idx in range(num_slots):
            # 取出該時段之起始與結束時間
            time_info = wx_times[slot_idx]
            start_time = time_info.get("startTime", "")
            end_time = time_info.get("endTime", "")
            
            # 天氣現象 (Wx)
            wx_val = time_info.get("parameter", {}).get("parameterName", "N/A")
            
            # 最低溫 (MinT)
            min_t_times = element_map.get("MinT", [])
            min_temp = float(min_t_times[slot_idx].get("parameter", {}).get("parameterName", 0.0)) if slot_idx < len(min_t_times) else None
            
            # 最高溫 (MaxT)
            max_t_times = element_map.get("MaxT", [])
            max_temp = float(max_t_times[slot_idx].get("parameter", {}).get("parameterName", 0.0)) if slot_idx < len(max_t_times) else None
            
            # 降雨機率 (PoP)
            pop_times = element_map.get("PoP", [])
            pop = int(pop_times[slot_idx].get("parameter", {}).get("parameterName", 0)) if slot_idx < len(pop_times) else 0
            
            # 舒適度 (CI)
            ci_times = element_map.get("CI", [])
            comfort = ci_times[slot_idx].get("parameter", {}).get("parameterName", "") if slot_idx < len(ci_times) else ""
            
            parsed_rows.append({
                "locationName": county_name,
                "startTime": start_time,
                "endTime": end_time,
                "weather": wx_val,
                "minT": min_temp,
                "maxT": max_temp,
                "avgT": round((min_temp + max_temp) / 2.0, 1) if (min_temp is not None and max_temp is not None) else None,
                "pop": pop,
                "comfort": comfort
            })
            
    df = pd.DataFrame(parsed_rows)
    return df


def get_mock_weather_data() -> pd.DataFrame:
    """
    提供全台 22 縣市高品質離線模擬天氣預報資料
    當無 API Key 或網路異常時作為穩定示範與回退測試使用
    """
    import datetime
    now = datetime.datetime.now()
    t1_start = now.strftime("%Y-%m-%d 12:00:00")
    t1_end = (now + datetime.timedelta(hours=12)).strftime("%Y-%m-%d 00:00:00")
    
    mock_base = [
        {"name": "臺北市", "wx": "多雲短暫雨", "min": 21.0, "max": 27.0, "pop": 30, "ci": "舒適至悶熱"},
        {"name": "新北市", "wx": "多雲短暫雨", "min": 21.0, "max": 27.0, "pop": 30, "ci": "舒適至悶熱"},
        {"name": "基隆市", "wx": "陰短暫雨", "min": 20.0, "max": 25.0, "pop": 50, "ci": "舒適"},
        {"name": "桃園市", "wx": "多雲", "min": 21.0, "max": 28.0, "pop": 20, "ci": "舒適至悶熱"},
        {"name": "新竹市", "wx": "晴時多雲", "min": 22.0, "max": 28.0, "pop": 10, "ci": "舒適"},
        {"name": "新竹縣", "wx": "晴時多雲", "min": 21.0, "max": 28.0, "pop": 10, "ci": "舒適"},
        {"name": "苗栗縣", "wx": "晴時多雲", "min": 21.0, "max": 28.0, "pop": 10, "ci": "舒適"},
        {"name": "臺中市", "wx": "晴天", "min": 22.0, "max": 30.0, "pop": 0, "ci": "悶熱"},
        {"name": "彰化縣", "wx": "晴天", "min": 22.0, "max": 29.0, "pop": 0, "ci": "舒適至悶熱"},
        {"name": "南投縣", "wx": "多雲午後局部雷陣雨", "min": 20.0, "max": 29.0, "pop": 40, "ci": "舒適至悶熱"},
        {"name": "雲林縣", "wx": "晴天", "min": 22.0, "max": 30.0, "pop": 0, "ci": "悶熱"},
        {"name": "嘉義市", "wx": "晴天", "min": 22.0, "max": 30.0, "pop": 0, "ci": "悶熱"},
        {"name": "嘉義縣", "wx": "晴天", "min": 22.0, "max": 30.0, "pop": 0, "ci": "悶熱"},
        {"name": "臺南市", "wx": "晴時多雲", "min": 23.0, "max": 31.0, "pop": 10, "ci": "悶熱"},
        {"name": "高雄市", "wx": "多雲時晴", "min": 24.0, "max": 31.0, "pop": 10, "ci": "悶熱"},
        {"name": "屏東縣", "wx": "多雲時晴", "min": 23.0, "max": 31.0, "pop": 20, "ci": "悶熱"},
        {"name": "宜蘭縣", "wx": "陰短暫雨", "min": 20.0, "max": 26.0, "pop": 60, "ci": "舒適"},
        {"name": "花蓮縣", "wx": "多雲短暫陣雨", "min": 21.0, "max": 27.0, "pop": 40, "ci": "舒適"},
        {"name": "臺東縣", "wx": "多雲短暫陣雨", "min": 22.0, "max": 28.0, "pop": 30, "ci": "舒適"},
        {"name": "澎湖縣", "wx": "晴時多雲", "min": 23.0, "max": 28.0, "pop": 10, "ci": "舒適"},
        {"name": "金門縣", "wx": "多雲", "min": 20.0, "max": 26.0, "pop": 20, "ci": "舒適"},
        {"name": "連江縣", "wx": "陰天", "min": 17.0, "max": 22.0, "pop": 30, "ci": "稍有寒意至舒適"}
    ]
    
    rows = []
    for item in mock_base:
        min_t = item["min"]
        max_t = item["max"]
        rows.append({
            "locationName": item["name"],
            "startTime": t1_start,
            "endTime": t1_end,
            "weather": item["wx"],
            "minT": min_t,
            "maxT": max_t,
            "avgT": round((min_t + max_t) / 2.0, 1),
            "pop": item["pop"],
            "comfort": item["ci"]
        })
        
    return pd.DataFrame(rows)


def get_taiwan_all_counties_weather(api_key: Optional[str] = None) -> Tuple[pd.DataFrame, bool, str]:
    """
    整合函式：取得全台灣所有縣市的天氣預報資料
    
    :param api_key: CWA API Key，若為 None 則嘗試從 .env 自動讀取
    :return: (DataFrame, is_mock: bool, message: str)
    """
    resolved_key = api_key or load_cwa_api_key()
    
    if not resolved_key:
        msg = "未檢測到有效的 CWA_API_KEY，已啟用「離線示範資料」供功能預覽與測試。"
        logger.warning(msg)
        df = get_mock_weather_data()
        return df, True, msg
        
    try:
        raw_json = fetch_cwa_raw_json(resolved_key)
        df = parse_cwa_36h_forecast(raw_json)
        msg = f"成功從中央氣象署 (CWA) 即時取得全台灣 {len(df['locationName'].unique())} 個縣市預報資料！"
        logger.info(msg)
        return df, False, msg
    except Exception as e:
        msg = f"連線至中央氣象署 API 時發生錯誤 ({str(e)})，已自動切換為「離線示範資料」保護運行。"
        logger.error(msg)
        df = get_mock_weather_data()
        return df, True, msg


if __name__ == "__main__":
    df, is_mock, message = get_taiwan_all_counties_weather()
    print(f"\n[{'離線示範' if is_mock else '即時API'}] {message}")
    print(f"資料筆數: {len(df)} 筆，涵蓋縣市數: {df['locationName'].nunique()} 個")
    print(df.head(10))
