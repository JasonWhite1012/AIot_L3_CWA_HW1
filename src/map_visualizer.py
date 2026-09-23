"""
台灣氣象地圖視覺化模組 (暗色調 / 極光電競風)
支援 氣溫分布 與 降雨機率 雙模式切換
"""

from typing import Dict, Any, Optional
import folium
import pandas as pd

# 台灣 22 縣市地理座標 (緯度, 經度)
COUNTY_COORDINATES = {
    # 北部
    "基隆市": [25.1276, 121.7392],
    "臺北市": [25.0330, 121.5654],
    "新北市": [25.0170, 121.4628],
    "桃園市": [24.9936, 121.3010],
    "新竹市": [24.8138, 120.9675],
    "新竹縣": [24.8387, 121.0177],
    "宜蘭縣": [24.7021, 121.7377],
    # 中部
    "苗栗縣": [24.5602, 120.8214],
    "臺中市": [24.1477, 120.6736],
    "彰化縣": [24.0518, 120.5161],
    "南投縣": [23.9609, 120.9719],
    "雲林縣": [23.7092, 120.4313],
    # 南部
    "嘉義市": [23.4800, 120.4491],
    "嘉義縣": [23.4518, 120.2555],
    "臺南市": [22.9997, 120.2270],
    "高雄市": [22.6273, 120.3014],
    "屏東縣": [22.5519, 120.5487],
    # 東部
    "花蓮縣": [23.9872, 121.6016],
    "臺東縣": [22.7583, 121.1444],
    # 離島
    "澎湖縣": [23.5711, 119.5793],
    "金門縣": [24.4493, 118.3766],
    "連江縣": [26.1602, 119.9515]
}


def get_temperature_color(temp: float) -> str:
    """
    極光暗黑風格氣溫四階色標
    """
    if temp < 20.0:
        return "#00e5ff"  # 涼爽 / 寒冷 (冰藍)
    elif 20.0 <= temp < 25.0:
        return "#10b981"  # 舒適 (極光綠)
    elif 25.0 <= temp < 30.0:
        return "#f59e0b"  # 偏暖 (金黃)
    else:
        return "#f43f5e"  # 炎熱 (霓紅)


def get_rainfall_color(pop: int) -> str:
    """
    降雨機率 (PoP) 四階色標
    < 20%: 晴空微雨機率低 (#38bdf8 淺天藍)
    20~40%: 局部陣雨可能 (#0ea5e9 海洋藍)
    40~70%: 降雨機率偏高 (#8b5cf6 電光紫)
    > 70%: 豪大雨/強降雨警戒 (#ec4899 警戒桃紅)
    """
    if pop < 20:
        return "#38bdf8"
    elif 20 <= pop < 40:
        return "#0ea5e9"
    elif 40 <= pop < 70:
        return "#8b5cf6"
    else:
        return "#ec4899"


def create_taiwan_weather_map(df: pd.DataFrame, selected_time: Optional[str] = None, map_mode: str = "temperature") -> folium.Map:
    """
    根據氣象預報資料建立 Folium 台灣暗黑風格互動式地圖
    
    :param df: 包含各縣市預報的 DataFrame
    :param selected_time: 指定篩選的時段
    :param map_mode: "temperature" (氣溫分布) 或 "rainfall" (降雨機率分布)
    :return: folium.Map 物件
    """
    taiwan_center = [23.85, 120.95]
    
    m = folium.Map(
        location=taiwan_center,
        zoom_start=7.5,
        tiles="OpenStreetMap",
        control_scale=True
    )
    
    if selected_time and "startTime" in df.columns:
        filtered_df = df[df["startTime"] == selected_time]
    else:
        filtered_df = df.drop_duplicates(subset=["regionName"])
        
    for _, row in filtered_df.iterrows():
        county = row["regionName"]
        if county not in COUNTY_COORDINATES:
            continue
            
        coord = COUNTY_COORDINATES[county]
        avg_t = row.get("avgT", (row.get("minT", 25) + row.get("maxT", 25)) / 2)
        min_t = row.get("minT", "N/A")
        max_t = row.get("maxT", "N/A")
        weather = row.get("weather", "N/A")
        pop = row.get("pop", 0)
        comfort = row.get("comfort", "")
        
        # 依視圖模式選取主色調與標籤
        if map_mode == "rainfall":
            color = get_rainfall_color(pop)
            badge_text = f"{county} <span style='color:{color}; font-size:9pt;'>💧{pop}%</span>"
        else:
            color = get_temperature_color(avg_t)
            badge_text = f"{county} <span style='color:{color}; font-size:9pt;'>{avg_t}°C</span>"
        
        # 暗色調巴哈風彈窗 (Popup)
        popup_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    background-color: #131b2e; color: #e2e8f0; min-width: 190px; 
                    padding: 10px; border-radius: 8px; border: 1px solid {color}; 
                    box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-bottom: 6px;">
                <b style="font-size: 15px; color: {color};">📍 {county}</b>
                <span style="font-size: 11px; background: rgba(0,229,255,0.15); color: #00e5ff; padding: 2px 6px; border-radius: 4px;">{weather}</span>
            </div>
            <div style="font-size: 13px; line-height: 1.6;">
                <div>💧 降雨機率：<span style="color:#38bdf8; font-weight:bold; font-size:14px;">{pop}%</span></div>
                <div>🔥 最高氣溫：<span style="color:#f43f5e; font-weight:bold;">{max_t}°C</span></div>
                <div>❄️ 最低氣溫：<span style="color:#00e5ff; font-weight:bold;">{min_t}°C</span></div>
            </div>
            <div style="margin-top: 6px; font-size: 11px; color: #94a3b8; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 4px;">
                舒適度指標：{comfort}
            </div>
        </div>
        """
        
        # 標註發光圓形標記
        folium.CircleMarker(
            location=coord,
            radius=13,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{county} | {weather} | 💧降雨率: {pop}% | 氣溫: {min_t}~{max_t}°C",
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.88,
            weight=3
        ).add_to(m)
        
        # 顯示縣市名稱文字標籤 (發光暗底文字)
        folium.map.Marker(
            location=[coord[0] - 0.08, coord[1]],
            icon=folium.DivIcon(
                html=f"""
                <div style="font-size: 10pt; font-weight: bold; color: #e2e8f0; 
                            background: rgba(15, 23, 42, 0.85); padding: 1px 6px; border-radius: 4px;
                            border: 1px solid rgba(0, 229, 255, 0.4); text-align: center;
                            box-shadow: 0 2px 5px rgba(0,0,0,0.5); white-space: nowrap;">
                    {badge_text}
                </div>
                """
            )
        ).add_to(m)
        
    return m
