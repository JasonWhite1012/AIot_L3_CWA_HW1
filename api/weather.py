"""
Vercel Serverless Function: Weather Data API
Endpoint: /api/weather
"""

import sys
import os
import json
from http.server import BaseHTTPRequestHandler

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetch_cwa_data import get_taiwan_all_counties_weather, load_cwa_api_key
from src.db_manager import save_weather_forecasts


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 抓取氣象資料
            df, is_mock, msg = get_taiwan_all_counties_weather()
            
            # 若在非唯讀環境嘗試寫入快取
            try:
                save_weather_forecasts(df, db_path="/tmp/data.db")
            except Exception:
                pass
                
            records = df.to_dict(orient="records")
            
            response_payload = {
                "success": True,
                "is_mock": is_mock,
                "has_api_key": bool(load_cwa_api_key()),
                "message": msg,
                "total": len(records),
                "counties_count": df["locationName"].nunique(),
                "data": records
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, s-maxage=300, stale-while-revalidate=600")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode("utf-8"))
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            err_payload = {
                "success": False,
                "error": str(e)
            }
            self.wfile.write(json.dumps(err_payload, ensure_ascii=False).encode("utf-8"))
