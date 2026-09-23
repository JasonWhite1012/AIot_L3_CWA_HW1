/**
 * Taiwan Weather Forecast - 前端互動核心邏輯
 * 整合 Vercel API / Leaflet.js 地圖 / Chart.js 雙軸圖表 / CSV 匯出
 */

// 台灣 22 縣市地理座標 (緯度, 經度)
const COUNTY_COORDINATES = {
    "基隆市": [25.1276, 121.7392],
    "臺北市": [25.0330, 121.5654],
    "新北市": [25.0170, 121.4628],
    "桃園市": [24.9936, 121.3010],
    "新竹市": [24.8138, 120.9675],
    "新竹縣": [24.8387, 121.0177],
    "宜蘭縣": [24.7021, 121.7377],
    "苗栗縣": [24.5602, 120.8214],
    "臺中市": [24.1477, 120.6736],
    "彰化縣": [24.0518, 120.5161],
    "南投縣": [23.9609, 120.9719],
    "雲林縣": [23.7092, 120.4313],
    "嘉義市": [23.4800, 120.4491],
    "嘉義縣": [23.4518, 120.2555],
    "臺南市": [22.9997, 120.2270],
    "高雄市": [22.6273, 120.3014],
    "屏東縣": [22.5519, 120.5487],
    "花蓮縣": [23.9872, 121.6016],
    "臺東縣": [22.7583, 121.1444],
    "澎湖縣": [23.5711, 119.5793],
    "金門縣": [24.4493, 118.3766],
    "連江縣": [26.1602, 119.9515]
};

// 全域狀態
let weatherData = [];
let availableTimes = [];
let selectedCounty = "ALL";
let selectedTime = null;
let overviewChartMode = "temp"; // 'temp' or 'rain'
let mapMode = "temperature";     // 'temperature' or 'rainfall'

// 圖表與地圖實例
let overviewChartInstance = null;
let singleCountyChartInstance = null;
let leafletMap = null;
let mapMarkersGroup = null;

// ==========================================================================
// 初始化與事件綁定
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
    initLeafletMap();
    initEventListeners();
    fetchWeatherData();
});

function initEventListeners() {
    // 頁籤切換
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            
            btn.classList.add("active");
            const targetId = btn.getAttribute("data-tab");
            const targetContent = document.getElementById(targetId);
            if (targetContent) targetContent.classList.add("active");
            
            // 若切換到地圖頁籤，需觸發 Leaflet 重新計算尺寸
            if (targetId === "tab-map" && leafletMap) {
                setTimeout(() => leafletMap.invalidateSize(), 200);
            }
        });
    });

    // 縣市選單變更
    const countySelect = document.getElementById("county-select");
    countySelect.addEventListener("change", (e) => {
        selectedCounty = e.target.value;
        renderMainView();
    });

    // 重新整理按鈕
    document.getElementById("refresh-btn").addEventListener("click", () => {
        fetchWeatherData(true);
    });

    // 全台總覽切換排行模式 (氣溫 vs 降雨)
    document.querySelectorAll("#overview-subtabs .toggle-pill").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#overview-subtabs .toggle-pill").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            overviewChartMode = btn.getAttribute("data-mode");
            renderOverviewChart();
        });
    });

    // 地圖模式切換 (氣溫熱度 vs 降雨機率)
    document.querySelectorAll("#map-mode-pills .toggle-pill").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#map-mode-pills .toggle-pill").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            mapMode = btn.getAttribute("data-map-mode");
            updateMapMarkers();
            renderMapLegend();
        });
    });

    // 表格搜尋過濾
    document.getElementById("table-search").addEventListener("input", (e) => {
        renderTable(e.target.value.trim());
    });

    // CSV 下載按鈕
    document.getElementById("download-csv-btn").addEventListener("click", exportCSV);
}

// ==========================================================================
// 資料獲取與 API 串接
// ==========================================================================
async function fetchWeatherData(isRefresh = false) {
    const statusBadge = document.getElementById("api-status-badge");
    const refreshBtn = document.getElementById("refresh-btn");
    
    statusBadge.className = "status-badge connecting";
    statusBadge.innerHTML = '<span class="status-indicator"></span><span class="status-text">連線更新中...</span>';
    refreshBtn.disabled = true;

    try {
        const response = await fetch("/api/weather?t=" + new Date().getTime());
        if (!response.ok) throw new Error("API 回應狀態碼: " + response.status);
        
        const resJson = await response.json();
        if (resJson.success && resJson.data) {
            weatherData = resJson.data;
            statusBadge.className = "status-badge online";
            const modeText = resJson.is_mock ? "離線示範模式" : "CWA 官方 API 正常";
            statusBadge.innerHTML = `<span class="status-indicator"></span><span class="status-text">🟢 ${modeText}</span>`;
        } else {
            throw new Error(resJson.error || "回傳格式不符");
        }
    } catch (err) {
        console.warn("無法取得 /api/weather，切換至本機備份示範資料：", err);
        weatherData = generateFallbackWeatherData();
        statusBadge.className = "status-badge online";
        statusBadge.innerHTML = `<span class="status-indicator"></span><span class="status-text">🟡 離線示範模式</span>`;
    } finally {
        refreshBtn.disabled = false;
        processWeatherData();
    }
}

// 整理時間戳與各項指標
function processWeatherData() {
    if (!weatherData || weatherData.length === 0) return;

    // 取得所有不重複時段
    const timeSet = new Set(weatherData.map(d => d.startTime));
    availableTimes = Array.from(timeSet).sort();
    if (!selectedTime || !availableTimes.includes(selectedTime)) {
        selectedTime = availableTimes[0];
    }

    // 填充縣市選單
    const countySelect = document.getElementById("county-select");
    const counties = Array.from(new Set(weatherData.map(d => d.locationName))).sort();
    
    countySelect.innerHTML = '<option value="ALL">全台灣總覽 (22 縣市)</option>';
    counties.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = `📍 ${c}`;
        if (c === selectedCounty) opt.selected = true;
        countySelect.appendChild(opt);
    });

    // 渲染時段膠囊標籤
    const timePillsContainer = document.getElementById("time-pills");
    timePillsContainer.innerHTML = "";
    availableTimes.forEach((t, idx) => {
        const btn = document.createElement("button");
        btn.className = `toggle-pill ${t === selectedTime ? "active" : ""}`;
        btn.textContent = `時段 ${idx + 1}：${t.slice(5, 16)}`;
        btn.addEventListener("click", () => {
            selectedTime = t;
            document.querySelectorAll("#time-pills .toggle-pill").forEach(p => p.classList.remove("active"));
            btn.classList.add("active");
            renderMainView();
        });
        timePillsContainer.appendChild(btn);
    });

    renderMainView();
}

// ==========================================================================
// 核心視圖渲染
// ==========================================================================
function renderMainView() {
    renderKPIs();
    
    const overviewBox = document.getElementById("overview-chart-container");
    const singleBox = document.getElementById("single-county-container");

    if (selectedCounty === "ALL") {
        overviewBox.style.display = "block";
        singleBox.style.display = "none";
        renderOverviewChart();
    } else {
        overviewBox.style.display = "none";
        singleBox.style.display = "block";
        renderSingleCountyView();
    }

    updateMapMarkers();
    renderMapLegend();
    renderTable();
}

// 渲染頂部 4 大 KPI 卡片
function renderKPIs() {
    const currentSlice = weatherData.filter(d => d.startTime === selectedTime);
    if (!currentSlice.length) return;

    // 全台最高溫
    const hottest = currentSlice.reduce((prev, curr) => (curr.maxT > prev.maxT ? curr : prev), currentSlice[0]);
    document.getElementById("val-hottest").textContent = `${hottest.maxT} °C`;
    document.getElementById("sub-hottest").textContent = `📍 ${hottest.locationName} (${hottest.weather})`;

    // 全台最低溫
    const coolest = currentSlice.reduce((prev, curr) => (curr.minT < prev.minT ? curr : prev), currentSlice[0]);
    document.getElementById("val-coolest").textContent = `${coolest.minT} °C`;
    document.getElementById("sub-coolest").textContent = `📍 ${coolest.locationName} (${coolest.weather})`;

    // 最高降雨機率
    const rainiest = currentSlice.reduce((prev, curr) => (curr.pop > prev.pop ? curr : prev), currentSlice[0]);
    document.getElementById("val-rain").textContent = `${rainiest.pop} %`;
    document.getElementById("sub-rain").textContent = `📍 ${rainiest.locationName} (${rainiest.pop >= 30 ? "建議攜帶雨具" : "晴朗穩定"})`;

    // 平均溫度
    const avgTemp = (currentSlice.reduce((sum, d) => sum + (d.avgT || (d.minT + d.maxT)/2), 0) / currentSlice.length).toFixed(1);
    document.getElementById("val-avg").textContent = `${avgTemp} °C`;
    document.getElementById("sub-avg").textContent = (avgTemp >= 20 && avgTemp <= 27) ? "涼爽舒適" : "偏熱微悶";
}

// 渲染全台總覽排行榜 (Chart.js 橫向長條圖)
function renderOverviewChart() {
    const ctx = document.getElementById("overviewChart").getContext("2d");
    const currentSlice = weatherData.filter(d => d.startTime === selectedTime);
    if (!currentSlice.length) return;

    if (overviewChartInstance) overviewChartInstance.destroy();

    if (overviewChartMode === "temp") {
        document.getElementById("overview-title").textContent = `📊 全台灣 22 縣市最高氣溫排行 (${selectedTime ? selectedTime.slice(5, 16) : ""})`;
        const sorted = [...currentSlice].sort((a, b) => a.maxT - b.maxT);
        
        overviewChartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels: sorted.map(d => d.locationName),
                datasets: [{
                    label: "最高氣溫 (°C)",
                    data: sorted.map(d => d.maxT),
                    backgroundColor: sorted.map(d => getTempColor(d.maxT)),
                    borderColor: "rgba(0, 229, 255, 0.4)",
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            afterLabel: (ctx) => {
                                const item = sorted[ctx.dataIndex];
                                return `最低溫: ${item.minT}°C | 天氣: ${item.weather}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.08)" },
                        ticks: { color: "#94a3b8" }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: "#e2e8f0", font: { weight: "bold" } }
                    }
                }
            }
        });
    } else {
        document.getElementById("overview-title").textContent = `💧 全台灣 22 縣市降雨機率排行 (${selectedTime ? selectedTime.slice(5, 16) : ""})`;
        const sorted = [...currentSlice].sort((a, b) => a.pop - b.pop);
        
        overviewChartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels: sorted.map(d => d.locationName),
                datasets: [{
                    label: "降雨機率 (%)",
                    data: sorted.map(d => d.pop),
                    backgroundColor: sorted.map(d => getRainColor(d.pop)),
                    borderColor: "rgba(56, 189, 248, 0.5)",
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        min: 0,
                        max: 100,
                        grid: { color: "rgba(255, 255, 255, 0.08)" },
                        ticks: { color: "#94a3b8", callback: (val) => `${val}%` }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: "#e2e8f0", font: { weight: "bold" } }
                    }
                }
            }
        });
    }
}

// 渲染單一縣市雙軸趨勢圖與預報卡片
function renderSingleCountyView() {
    const countyRecords = weatherData.filter(d => d.locationName === selectedCounty).sort((a, b) => a.startTime.localeCompare(b.startTime));
    if (!countyRecords.length) return;

    document.getElementById("single-chart-title").textContent = `📍 【${selectedCounty}】雙軸綜合趨勢：氣溫起伏與降雨機率`;

    const ctx = document.getElementById("singleCountyChart").getContext("2d");
    if (singleCountyChartInstance) singleCountyChartInstance.destroy();

    const labels = countyRecords.map(d => d.startTime.slice(5, 16));

    singleCountyChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    type: "bar",
                    label: "降雨機率 (%)",
                    data: countyRecords.map(d => d.pop),
                    yAxisID: "yRain",
                    backgroundColor: "rgba(56, 189, 248, 0.35)",
                    borderColor: "#38bdf8",
                    borderWidth: 1.5,
                    borderRadius: 6
                },
                {
                    type: "line",
                    label: "最高溫 (°C)",
                    data: countyRecords.map(d => d.maxT),
                    yAxisID: "yTemp",
                    borderColor: "#f43f5e",
                    backgroundColor: "rgba(244, 63, 94, 0.15)",
                    borderWidth: 3,
                    tension: 0.3,
                    pointBackgroundColor: "#f43f5e",
                    pointRadius: 5
                },
                {
                    type: "line",
                    label: "最低溫 (°C)",
                    data: countyRecords.map(d => d.minT),
                    yAxisID: "yTemp",
                    borderColor: "#00e5ff",
                    backgroundColor: "rgba(0, 229, 255, 0.15)",
                    borderWidth: 3,
                    tension: 0.3,
                    pointBackgroundColor: "#00e5ff",
                    pointRadius: 5
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: {
                    labels: { color: "#e2e8f0", font: { weight: "600" } }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.08)" },
                    ticks: { color: "#94a3b8" }
                },
                yTemp: {
                    type: "linear",
                    position: "left",
                    title: { display: true, text: "氣溫 (°C)", color: "#00e5ff" },
                    ticks: { color: "#00e5ff" },
                    grid: { color: "rgba(255, 255, 255, 0.08)" }
                },
                yRain: {
                    type: "linear",
                    position: "right",
                    min: 0,
                    max: 100,
                    title: { display: true, text: "降雨機率 (%)", color: "#38bdf8" },
                    ticks: { color: "#38bdf8", callback: (val) => `${val}%` },
                    grid: { display: false }
                }
            }
        }
    });

    // 渲染各時段卡片
    const cardsGrid = document.getElementById("period-cards-grid");
    cardsGrid.innerHTML = "";

    countyRecords.forEach(record => {
        const rainColor = record.pop < 30 ? "#38bdf8" : (record.pop < 60 ? "#f59e0b" : "#ec4899");
        const rainText = record.pop < 30 ? "降雨率低" : (record.pop < 60 ? "建議攜帶雨具" : "高機率有陣雨！");

        const card = document.createElement("div");
        card.className = "period-card";
        card.innerHTML = `
            <div class="card-time">📅 ${record.startTime.slice(5, 16)} ~ ${record.endTime ? record.endTime.slice(11, 16) : ""}</div>
            <div class="card-weather">${record.weather}</div>
            <div class="card-temp-row">
                <span class="card-temp-max">${record.maxT}°C</span>
                <span class="card-divider">/</span>
                <span class="card-temp-min">${record.minT}°C</span>
            </div>
            <div class="card-rain-row" style="color: ${rainColor};">
                💧 降雨機率: <b>${record.pop}%</b> (${rainText})
            </div>
            <div class="card-comfort">舒適度：${record.comfort || "普通"}</div>
        `;
        cardsGrid.appendChild(card);
    });
}

// ==========================================================================
// Leaflet 台灣互動地圖模組
// ==========================================================================
function initLeafletMap() {
    const mapElement = document.getElementById("taiwan-map");
    if (!mapElement) return;

    leafletMap = L.map("taiwan-map", {
        center: [23.85, 120.95],
        zoom: 7.5,
        zoomControl: true,
        attributionControl: false
    });

    // 載入免金鑰的 OpenStreetMap
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18
    }).addTo(leafletMap);

    mapMarkersGroup = L.layerGroup().addTo(leafletMap);
}

function updateMapMarkers() {
    if (!leafletMap || !mapMarkersGroup) return;
    mapMarkersGroup.clearLayers();

    const currentSlice = weatherData.filter(d => d.startTime === selectedTime);
    if (!currentSlice.length) return;

    currentSlice.forEach(row => {
        const county = row.locationName;
        if (!COUNTY_COORDINATES[county]) return;

        const coord = COUNTY_COORDINATES[county];
        const avgT = row.avgT || ((row.minT + row.maxT) / 2).toFixed(1);
        
        let markerColor = "";
        let badgeLabel = "";

        if (mapMode === "rainfall") {
            markerColor = getRainColor(row.pop);
            badgeLabel = `${county} <span style="color:${markerColor}">💧${row.pop}%</span>`;
        } else {
            markerColor = getTempColor(row.maxT);
            badgeLabel = `${county} <span style="color:${markerColor}">${avgT}°C</span>`;
        }

        // Popup HTML
        const popupHtml = `
            <div style="font-family: sans-serif; min-width: 170px; padding: 4px;">
                <h4 style="margin: 0 0 6px 0; color: ${markerColor}; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 4px;">
                    📍 ${county}
                </h4>
                <div style="font-size: 13px; line-height: 1.6;">
                    <div>💧 降雨機率: <b style="color:#38bdf8;">${row.pop}%</b></div>
                    <div>🔥 最高氣溫: <b style="color:#f43f5e;">${row.maxT}°C</b></div>
                    <div>❄️ 最低氣溫: <b style="color:#00e5ff;">${row.minT}°C</b></div>
                    <div style="margin-top: 4px; font-size: 11px; color:#94a3b8;">${row.weather} | ${row.comfort || ""}</div>
                </div>
            </div>
        `;

        // 圓形標記
        const circle = L.circleMarker(coord, {
            radius: 12,
            color: markerColor,
            fillColor: markerColor,
            fillOpacity: 0.85,
            weight: 2
        }).bindPopup(popupHtml);

        // 文字標籤 Marker
        const labelIcon = L.divIcon({
            className: "map-label-icon",
            html: `<div style="background: rgba(15, 23, 42, 0.88); border: 1px solid rgba(0,229,255,0.4); 
                                color: #f1f5f9; padding: 1px 6px; border-radius: 4px; font-size: 11px; 
                                font-weight: bold; white-space: nowrap; transform: translate(-50%, 14px);">
                        ${badgeLabel}
                   </div>`,
            iconSize: [0, 0]
        });
        const textMarker = L.marker(coord, { icon: labelIcon });

        mapMarkersGroup.addLayer(circle);
        mapMarkersGroup.addLayer(textMarker);
    });
}

function renderMapLegend() {
    const legendContainer = document.getElementById("map-legend");
    if (mapMode === "temperature") {
        legendContainer.innerHTML = `
            <span class="legend-item"><span class="legend-dot" style="background:#00e5ff;"></span> &lt; 20°C 冰藍 (涼爽/寒冷)</span>
            <span class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> 20~25°C 極光綠 (舒適)</span>
            <span class="legend-item"><span class="legend-dot" style="background:#f59e0b;"></span> 25~30°C 琥珀金 (偏暖)</span>
            <span class="legend-item"><span class="legend-dot" style="background:#f43f5e;"></span> &gt; 30°C 霓虹紅 (炎熱)</span>
        `;
    } else {
        legendContainer.innerHTML = `
            <span class="legend-item"><span class="legend-dot" style="background:#38bdf8;"></span> &lt; 20% 晴空天藍 (降雨低)</span>
            <span class="legend-item"><span class="legend-dot" style="background:#0ea5e9;"></span> 20~40% 海洋藍 (偶陣雨)</span>
            <span class="legend-item"><span class="legend-dot" style="background:#8b5cf6;"></span> 40~70% 電光紫 (降雨機率高)</span>
            <span class="legend-item"><span class="legend-dot" style="background:#ec4899;"></span> &gt; 70% 警戒桃紅 (豪大雨警戒)</span>
        `;
    }
}

// ==========================================================================
// 資料表格與 CSV 匯出
// ==========================================================================
function renderTable(searchTerm = "") {
    const tbody = document.getElementById("table-body");
    tbody.innerHTML = "";

    const filtered = weatherData.filter(d => {
        if (!searchTerm) return true;
        return d.locationName.includes(searchTerm) || (d.weather && d.weather.includes(searchTerm));
    });

    filtered.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><b>📍 ${row.locationName}</b></td>
            <td>${row.startTime ? row.startTime.slice(5, 16) : ""}</td>
            <td><span style="color:var(--accent-cyan);">${row.weather}</span></td>
            <td style="color:#00e5ff;"><b>${row.minT}°C</b></td>
            <td style="color:#f43f5e;"><b>${row.maxT}°C</b></td>
            <td>${row.avgT || ((row.minT + row.maxT)/2).toFixed(1)}°C</td>
            <td><b style="color:#38bdf8;">💧 ${row.pop}%</b></td>
            <td style="color:#94a3b8;">${row.comfort || "-"}</td>
        `;
        tbody.appendChild(tr);
    });
}

function exportCSV() {
    if (!weatherData.length) return;
    const headers = ["縣市名稱", "開始時間", "結束時間", "天氣現象", "最低溫(°C)", "最高溫(°C)", "平均溫(°C)", "降雨機率(%)", "舒適度"];
    const rows = weatherData.map(d => [
        d.locationName,
        d.startTime,
        d.endTime,
        `"${d.weather}"`,
        d.minT,
        d.maxT,
        d.avgT,
        d.pop,
        `"${d.comfort}"`
    ]);

    const csvContent = "\uFEFF" + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", `taiwan_weather_forecast_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 色彩計算輔助函式
function getTempColor(temp) {
    if (temp < 20) return "#00e5ff";
    if (temp < 25) return "#10b981";
    if (temp < 30) return "#f59e0b";
    return "#f43f5e";
}

function getRainColor(pop) {
    if (pop < 20) return "#38bdf8";
    if (pop < 40) return "#0ea5e9";
    if (pop < 70) return "#8b5cf6";
    return "#ec4899";
}

// 離線模擬資料備用
function generateFallbackWeatherData() {
    const counties = Object.keys(COUNTY_COORDINATES);
    const now = new Date();
    const t1 = now.toISOString().replace("T", " ").slice(0, 19);
    
    return counties.map((c, i) => ({
        locationName: c,
        startTime: t1,
        endTime: t1,
        weather: i % 3 === 0 ? "多雲短暫陣雨" : (i % 2 === 0 ? "晴時多雲" : "晴朗"),
        minT: 21 + (i % 5),
        maxT: 28 + (i % 6),
        avgT: 25 + (i % 4),
        pop: (i * 15) % 90,
        comfort: "舒適至悶熱"
    }));
}
