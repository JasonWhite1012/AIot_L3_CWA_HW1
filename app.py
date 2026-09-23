"""
Taiwan Weather Forecast - 台灣即時天氣預報與空間視覺化儀表板
(Bahamut Dark Style & Arctic Aurora Background - 支援氣溫與降雨機率雙核心分析)
"""

import sys
import os
import base64
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import st_folium

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import importlib
import src.fetch_cwa_data
import src.db_manager
import src.map_visualizer

# 強制熱重載自訂模組，避免 Streamlit 記憶體中暫存舊版函式定義
importlib.reload(src.map_visualizer)
importlib.reload(src.db_manager)
importlib.reload(src.fetch_cwa_data)

from src.fetch_cwa_data import get_taiwan_all_counties_weather, load_cwa_api_key
from src.db_manager import (
    init_db,
    save_weather_forecasts,
    get_all_regions,
    get_forecast_by_region,
    get_all_latest_forecasts,
    DEFAULT_DB_PATH
)
from src.map_visualizer import create_taiwan_weather_map

# 1. 頁面設定
st.set_page_config(
    page_title="Taiwan Weather Forecast | 極光電競暗黑版",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 載入極光背景圖片 (Base64)
def get_base64_image(image_path: str):
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

aurora_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "aurora.jpg")
aurora_base64 = get_base64_image(aurora_path)

# 3. 巴哈姆特暗色調 + 北極極光自訂 CSS
aurora_bg_css = f"""
    background: linear-gradient(180deg, rgba(11, 15, 25, 0.88) 0%, rgba(11, 15, 25, 0.94) 100%),
                url("data:image/jpeg;base64,{aurora_base64}") no-repeat center center fixed;
    background-size: cover;
""" if aurora_base64 else "background-color: #0b0f19;"

st.markdown(f"""
<style>
    /* 全站背景與文字 */
    .stApp {{
        {aurora_bg_css}
        color: #e2e8f0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    
    /* 側邊欄半透明毛玻璃效果 */
    [data-testid="stSidebar"] {{
        background-color: rgba(15, 23, 42, 0.85) !important;
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(0, 229, 255, 0.15);
    }}
    
    /* 主標題青電光特效 */
    .cyber-title {{
        font-size: 2.3rem;
        font-weight: 800;
        letter-spacing: 0.5px;
        background: linear-gradient(90deg, #00e5ff 0%, #38bdf8 40%, #10b981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
        text-shadow: 0 0 20px rgba(0, 229, 255, 0.35);
    }}
    .cyber-subtitle {{
        color: #94a3b8;
        font-size: 0.95rem;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .aurora-badge {{
        background: rgba(0, 229, 255, 0.15);
        border: 1px solid rgba(0, 229, 255, 0.4);
        color: #00e5ff;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
    }}

    /* 巴哈風暗黑毛玻璃卡片 */
    .dark-card {{
        background: rgba(19, 27, 46, 0.78);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(0, 229, 255, 0.22);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
        border-radius: 12px;
        padding: 16px 20px;
        transition: all 0.25s ease-in-out;
    }}
    .dark-card:hover {{
        border-color: rgba(0, 229, 255, 0.6);
        box-shadow: 0 0 25px rgba(0, 229, 255, 0.25);
        transform: translateY(-2px);
    }}

    /* 圖例說明列 */
    .dark-legend-box {{
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        align-items: center;
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 10px 18px;
        border-radius: 8px;
        font-size: 13px;
        margin-bottom: 15px;
    }}
    .legend-dot {{
        height: 12px;
        width: 12px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 5px;
        box-shadow: 0 0 8px currentColor;
    }}
    
    iframe {{
        border-radius: 12px;
        border: 1px solid rgba(0, 229, 255, 0.3) !important;
        box-shadow: 0 8px 30px rgba(0,0,0,0.5);
    }}
</style>
""", unsafe_allow_html=True)


# 4. 資料載入與快取機制
@st.cache_data(ttl=600, show_spinner=False)
def load_or_sync_data(force_refresh=False):
    init_db()
    existing_df = get_all_latest_forecasts()
    
    if existing_df.empty or force_refresh:
        with st.spinner("正在向中央氣象署抓取最新資料並同步至 SQLite 資料庫..."):
            weather_df, is_mock, msg = get_taiwan_all_counties_weather()
            save_weather_forecasts(weather_df)
            existing_df = get_all_latest_forecasts()
            return existing_df, is_mock, msg
            
    return existing_df, False, "資料庫已備妥最新預報資料"


all_forecast_df, is_mock_mode, status_msg = load_or_sync_data()

# 5. 側邊欄 (Sidebar)
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
        <span style="font-size:32px;">🌌</span>
        <div>
            <h3 style="margin:0; color:#00e5ff; font-weight:800;">巴哈姆特風</h3>
            <span style="font-size:12px; color:#94a3b8;">氣溫 × 降雨機率預報</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # 手動更新按鈕
    if st.button("⚡ 即時同步氣象署最新數據", use_container_width=True, type="primary"):
        all_forecast_df, is_mock_mode, status_msg = load_or_sync_data(force_refresh=True)
        st.toast(status_msg, icon="🚀")
        st.rerun()
        
    st.divider()
    
    # 地區下拉選單
    regions = get_all_regions()
    if not regions:
        regions = ["臺北市", "新北市", "臺中市", "高雄市"]
        
    selected_region = st.selectbox(
        "📍 選擇預報縣市：",
        options=["全台灣總覽"] + sorted(regions),
        index=0
    )
    
    # 預報時段切換
    available_times = sorted(all_forecast_df["startTime"].unique().tolist()) if not all_forecast_df.empty else []
    selected_time = None
    if available_times:
        time_options = [f"時段 {i+1}：{t[5:16]}" for i, t in enumerate(available_times)]
        chosen_time_idx = st.radio("⏰ 選擇預報時段：", options=range(len(available_times)), format_func=lambda x: time_options[x])
        selected_time = available_times[chosen_time_idx]
        
    st.divider()
    
    # 狀態與金鑰指示
    api_key = load_cwa_api_key()
    if api_key:
        st.markdown('🟢 <span style="color:#10b981; font-weight:bold;">CWA 官方 API 連線正常</span>', unsafe_allow_html=True)
    else:
        st.markdown('🟡 <span style="color:#f59e0b; font-weight:bold;">離線示範模式</span>', unsafe_allow_html=True)
        
    st.caption(f"💾 本地資料庫：`data/data.db`")
    
    with st.expander("🌌 查看北極極光桌布"):
        if os.path.exists(aurora_path):
            st.image(aurora_path, caption="Arctic Aurora Wallpaper", use_container_width=True)


# 6. 主頁面內容
st.markdown('<div class="cyber-title">TAIWAN WEATHER & RAINFALL FORECAST</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="cyber-subtitle">'
    '<span class="aurora-badge">AURORA EDITION</span>'
    '中央氣象署 Open Data API × SQLite 本地資料庫 × 氣溫與降雨機率雙維度分析'
    '</div>',
    unsafe_allow_html=True
)

# 頂部關鍵指標卡片 (KPI Metrics)
if not all_forecast_df.empty:
    current_time_df = all_forecast_df[all_forecast_df["startTime"] == selected_time] if selected_time else all_forecast_df
    
    hottest_row = current_time_df.loc[current_time_df["maxT"].idxmax()]
    coolest_row = current_time_df.loc[current_time_df["minT"].idxmin()]
    rainiest_row = current_time_df.loc[current_time_df["pop"].idxmax()]
    avg_taiwan_temp = round(current_time_df["avgT"].mean(), 1)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            label="🔥 全台最高溫",
            value=f"{hottest_row['maxT']} °C",
            delta=f"{hottest_row['regionName']} ({hottest_row['weather']})"
        )
    with c2:
        st.metric(
            label="❄️ 全台最低溫",
            value=f"{coolest_row['minT']} °C",
            delta=f"{coolest_row['regionName']} ({coolest_row['weather']})",
            delta_color="inverse"
        )
    with c3:
        st.metric(
            label="💧 全台最高降雨機率",
            value=f"{rainiest_row['pop']} %",
            delta=f"{rainiest_row['regionName']} ({'留意雷雨/雨具' if rainiest_row['pop']>=30 else '降雨率低'})",
            delta_color="off" if rainiest_row['pop'] < 30 else "inverse"
        )
    with c4:
        st.metric(
            label="🌡️ 全台平均氣溫",
            value=f"{avg_taiwan_temp} °C",
            delta="涼爽舒適" if 20 <= avg_taiwan_temp <= 27 else "偏熱微悶"
        )

st.write("")

# 7. 分頁標籤導航
tab1, tab2, tab3 = st.tabs(["📈 氣溫與降雨機率圖表", "🗺️ 台灣互動地圖視覺化 (雙模式)", "🗄️ SQLite 資料庫即時檢視"])

# ================= TAB 1: 氣溫與降雨機率分析 =================
with tab1:
    if selected_region == "全台灣總覽":
        overview_subtab1, overview_subtab2 = st.tabs(["🔥 全台氣溫排行", "💧 全台降雨機率排行"])
        
        with overview_subtab1:
            st.subheader(f"📊 全台灣 22 縣市最高氣溫排行 ({selected_time})")
            sorted_temp_df = current_time_df.sort_values(by="maxT", ascending=True)
            fig_temp = px.bar(
                sorted_temp_df,
                x="maxT",
                y="regionName",
                orientation="h",
                color="maxT",
                color_continuous_scale=["#00e5ff", "#10b981", "#f59e0b", "#f43f5e"],
                labels={"maxT": "最高氣溫 (°C)", "regionName": "縣市"},
                text="maxT"
            )
            fig_temp.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(15,23,42,0.6)",
                font=dict(color="#e2e8f0"),
                height=650,
                margin=dict(l=0, r=20, t=20, b=0)
            )
            st.plotly_chart(fig_temp, use_container_width=True)
            
        with overview_subtab2:
            st.subheader(f"💧 全台灣 22 縣市降雨機率排行 ({selected_time})")
            sorted_rain_df = current_time_df.sort_values(by="pop", ascending=True)
            fig_rain = px.bar(
                sorted_rain_df,
                x="pop",
                y="regionName",
                orientation="h",
                color="pop",
                color_continuous_scale=["#38bdf8", "#0ea5e9", "#8b5cf6", "#ec4899"],
                range_color=[0, 100],
                labels={"pop": "降雨機率 (%)", "regionName": "縣市"},
                text="pop"
            )
            # 加入 30% 攜帶雨具警戒參考線
            fig_rain.add_vline(x=30, line_dash="dash", line_color="#ffd166", annotation_text="雨具警戒線 (30%)", annotation_position="top right")
            fig_rain.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(15,23,42,0.6)",
                font=dict(color="#e2e8f0"),
                height=650,
                margin=dict(l=0, r=20, t=20, b=0)
            )
            st.plotly_chart(fig_rain, use_container_width=True)
            
    else:
        st.subheader(f"📍 【{selected_region}】未來 36 小時氣溫與降雨機率趨勢")
        region_df = get_forecast_by_region(selected_region)
        
        if not region_df.empty:
            # 建立雙軸整合圖 (左軸: 氣溫折線，右軸: 降雨機率柱狀)
            fig_combined = go.Figure()
            
            # 降雨機率長條 (右軸)
            fig_combined.add_trace(go.Bar(
                x=region_df["startTime"],
                y=region_df["pop"],
                name="降雨機率 (PoP %)",
                yaxis="y2",
                marker=dict(
                    color="rgba(56, 189, 248, 0.4)",
                    line=dict(color="#38bdf8", width=1.5)
                ),
                text=[f"💧 {v}%" for v in region_df["pop"]],
                textposition="outside",
                textfont=dict(color="#38bdf8")
            ))
            
            # 最高溫霓虹紅折線 (左軸)
            fig_combined.add_trace(go.Scatter(
                x=region_df["startTime"],
                y=region_df["maxT"],
                mode="lines+markers+text",
                name="最高溫 (MaxT)",
                yaxis="y",
                line=dict(color="#f43f5e", width=3),
                marker=dict(size=9, color="#f43f5e"),
                text=[f"{v}°C" for v in region_df["maxT"]],
                textposition="top center",
                textfont=dict(color="#f43f5e", size=12)
            ))
            
            # 最低溫極光冰藍折線 (左軸)
            fig_combined.add_trace(go.Scatter(
                x=region_df["startTime"],
                y=region_df["minT"],
                mode="lines+markers+text",
                name="最低溫 (MinT)",
                yaxis="y",
                line=dict(color="#00e5ff", width=3),
                marker=dict(size=9, color="#00e5ff"),
                fill="tonexty",
                fillcolor="rgba(0, 229, 255, 0.12)",
                text=[f"{v}°C" for v in region_df["minT"]],
                textposition="bottom center",
                textfont=dict(color="#00e5ff", size=12)
            ))
            
            fig_combined.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(15,23,42,0.6)",
                font=dict(color="#e2e8f0"),
                title=f"{selected_region} 雙軸綜合趨勢：氣溫起伏與降雨機率",
                xaxis=dict(title="預報時段"),
                yaxis=dict(
                    title="氣溫 (°C)",
                    titlefont=dict(color="#00e5ff"),
                    tickfont=dict(color="#00e5ff"),
                    side="left"
                ),
                yaxis2=dict(
                    title="降雨機率 (%)",
                    titlefont=dict(color="#38bdf8"),
                    tickfont=dict(color="#38bdf8"),
                    overlaying="y",
                    side="right",
                    range=[0, 100]
                ),
                legend=dict(x=0.01, y=0.99, bgcolor="rgba(15,23,42,0.8)", bordercolor="rgba(0,229,255,0.3)", borderwidth=1),
                hovermode="x unified",
                height=450,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            st.plotly_chart(fig_combined, use_container_width=True)
            
            # 各時段暗色預報卡片展示
            st.markdown("#### 🕒 各時段預報卡片")
            cols = st.columns(len(region_df))
            for idx, (_, row) in enumerate(region_df.iterrows()):
                rain_color = "#38bdf8" if row['pop'] < 30 else ("#f59e0b" if row['pop'] < 60 else "#ec4899")
                rain_hint = "降雨機率低" if row['pop'] < 30 else ("建議攜帶雨具" if row['pop'] < 60 else "高機率有陣雨！")
                
                with cols[idx]:
                    st.markdown(f"""
                    <div class="dark-card">
                        <div style="font-size:12px; color:#94a3b8;">📅 {row['startTime'][5:16]}</div>
                        <h3 style="margin: 8px 0; color:#00e5ff; font-weight:bold;">{row['weather']}</h3>
                        <div style="font-size:20px; margin: 6px 0;">
                            <span style="color:#f43f5e; font-weight:bold;">{row['maxT']}°C</span>
                            <span style="color:#64748b;"> / </span>
                            <span style="color:#00e5ff; font-weight:bold;">{row['minT']}°C</span>
                        </div>
                        <div style="font-size:14px; color:{rain_color}; margin-top:6px; font-weight:bold;">
                            💧 降雨機率: {row['pop']}%
                        </div>
                        <div style="font-size:11px; color:{rain_color}; margin-bottom:4px;">
                            ({rain_hint})
                        </div>
                        <div style="font-size:12px; color:#cbd5e1; margin-top:6px; border-top:1px dashed rgba(255,255,255,0.1); padding-top:4px;">
                            {row['comfort']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info(f"尚無 {selected_region} 的預報資料。")

# ================= TAB 2: 台灣空間地圖視覺化 (雙模式) =================
with tab2:
    st.subheader("🗺️ 台灣空間地圖視覺化 (Folium)")
    
    # 模式切換器
    map_view_mode = st.radio(
        "切換地圖指標圖層：",
        options=["🌡️ 氣溫熱度分布", "💧 降雨機率分布"],
        horizontal=True
    )
    
    # 根據切換模式呈現對應圖例
    if "氣溫" in map_view_mode:
        current_map_mode = "temperature"
        st.markdown("""
        <div class="dark-legend-box">
            <b style="color:#00e5ff;">氣溫色標規範：</b>
            <span><span class="legend-dot" style="background:#00e5ff; color:#00e5ff;"></span> &lt; 20°C 冰藍 (涼爽/寒冷)</span>
            <span><span class="legend-dot" style="background:#10b981; color:#10b981;"></span> 20~25°C 極光綠 (舒適宜人)</span>
            <span><span class="legend-dot" style="background:#f59e0b; color:#f59e0b;"></span> 25~30°C 琥珀金 (偏暖微熱)</span>
            <span><span class="legend-dot" style="background:#f43f5e; color:#f43f5e;"></span> &gt; 30°C 霓虹紅 (炎熱警戒)</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        current_map_mode = "rainfall"
        st.markdown("""
        <div class="dark-legend-box">
            <b style="color:#38bdf8;">降雨機率色標規範：</b>
            <span><span class="legend-dot" style="background:#38bdf8; color:#38bdf8;"></span> &lt; 20% 晴空天藍 (降雨低)</span>
            <span><span class="legend-dot" style="background:#0ea5e9; color:#0ea5e9;"></span> 20~40% 海洋深藍 (偶有局部雨)</span>
            <span><span class="legend-dot" style="background:#8b5cf6; color:#8b5cf6;"></span> 40~70% 電光紫 (降雨機率高)</span>
            <span><span class="legend-dot" style="background:#ec4899; color:#ec4899;"></span> &gt; 70% 警戒桃紅 (易有豪大雨/強陣雨)</span>
        </div>
        """, unsafe_allow_html=True)
    
    weather_map = create_taiwan_weather_map(all_forecast_df, selected_time=selected_time, map_mode=current_map_mode)
    st_folium(weather_map, width="100%", height=620)

# ================= TAB 3: SQLite 資料庫即時檢視 =================
with tab3:
    st.subheader("🗄️ SQLite 本地資料庫檢視 (data/data.db)")
    st.caption("即時讀取本地 SQLite 資料表，支援搜尋與下載 CSV")
    
    col_mapping = {
        "id": "ID",
        "regionName": "縣市名稱",
        "startTime": "開始時間",
        "endTime": "結束時間",
        "weather": "天氣現象",
        "minT": "最低溫(°C)",
        "maxT": "最高溫(°C)",
        "avgT": "平均溫(°C)",
        "pop": "降雨機率(%)",
        "comfort": "舒適度"
    }
    cols_to_use = [c for c in col_mapping.keys() if c in all_forecast_df.columns]
    display_table = all_forecast_df[cols_to_use].rename(columns=col_mapping)
    
    st.dataframe(display_table, use_container_width=True, height=450)
    
    csv_data = display_table.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 匯出完整預報資料 (CSV)",
        data=csv_data,
        file_name="taiwan_weather_forecast.csv",
        mime="text/csv",
        use_container_width=False
    )
    
    with st.expander("🔍 檢視背後執行的 SQL 查詢語法"):
        st.code("""
-- 讀取特定縣市氣溫與降雨機率預報
SELECT regionName, startTime, endTime, weather, minT, maxT, avgT, pop, comfort
FROM TemperatureForecasts
WHERE regionName = '臺北市'
ORDER BY startTime ASC;

-- 寫入與防重複更新 (Upsert)
INSERT OR REPLACE INTO TemperatureForecasts 
(regionName, startTime, endTime, weather, minT, maxT, avgT, pop, comfort, updatedAt)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
        """, language="sql")

st.divider()
st.markdown(
    '<div style="text-align: center; color: #64748b; font-size: 13px;">'
    'AI 創新微課程 - Taiwan Weather Forecast | 指導講師：煥哥<br>'
    '<i>「技術可以解決問題，但更重要的是用技術創造更好的未來！」</i>'
    '</div>',
    unsafe_allow_html=True
)
