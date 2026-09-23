"""
本地開發測試伺服器 (Local Development Server for Vercel Project)
用於在本地同時測試靜態前端 (public/) 與 Serverless API (api/weather)
"""

import sys
import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler

# 解決 Windows 終端機編碼問題
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 確保路徑正確認識
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
sys.path.append(BASE_DIR)

from src.fetch_cwa_data import get_taiwan_all_counties_weather, load_cwa_api_key

PORT = 3000

class LocalVercelHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def do_GET(self):
        # 攔截 /api/weather
        if self.path.startswith("/api/weather"):
            try:
                df, is_mock, msg = get_taiwan_all_counties_weather()
                records = df.to_dict(orient="records")
                
                payload = {
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
                self.end_headers()
                self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        # 攔截 /assets
        if self.path.startswith("/assets/"):
            asset_subpath = self.path[len("/assets/"):]
            local_asset_path = os.path.join(BASE_DIR, "assets", asset_subpath)
            if os.path.exists(local_asset_path):
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                with open(local_asset_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        # 其他路徑預設從 public/ 載入
        return super().do_GET()


def run():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, LocalVercelHandler)
    print("=" * 65)
    print(f" [Vercel Local Dev Server] 本地測試伺服器已啟動！")
    print(f" >>> 請在瀏覽器開啟: http://localhost:{PORT}")
    print(f" [Tip] 按下 Ctrl + C 可隨時停止伺服器")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止。")
        httpd.server_close()


if __name__ == "__main__":
    run()
