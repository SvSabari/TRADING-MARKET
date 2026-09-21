import { useEffect, useRef } from "react";
import { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } from "lightweight-charts";
import { calculateEMA, calculateSMA, calculateBollingerBands, calculateVWAP } from "./indicators";

export default function CandleChart({ data, symbol, interval, indicators = [] }) {
  const chartContainerRef = useRef(null);
  const legendRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  
  // Track dynamically added series
  const indicatorSeriesRef = useRef({});

  const loadedRef = useRef(false);
  const lastTimeRef = useRef(0);

  // Colors for indicators
  const getIndicatorColor = (type, index) => {
    if (type === 'VWAP') return '#9C27B0'; // Purple
    const colors = ['#2196F3', '#FF9800', '#E91E63', '#00BCD4', '#4CAF50', '#795548'];
    return colors[index % colors.length];
  };

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#333",
      },
      grid: {
        vertLines: { color: "#e0e0e0" },
        horzLines: { color: "#e0e0e0" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      rightPriceScale: { scaleMargins: { top: 0.15, bottom: 0.25 } },
      autoSize: true,
    });
    chartRef.current = chart;

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a", downColor: "#ef5350", borderVisible: true,
      borderUpColor: "#26a69a", borderDownColor: "#ef5350",
      wickUpColor: "#26a69a", wickDownColor: "#ef5350",
    });
    seriesRef.current = candlestickSeries;

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#26a69a', priceFormat: { type: 'volume' }, priceScaleId: '',
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    volumeSeriesRef.current = volumeSeries;

    chart.subscribeCrosshairMove((param) => {
      if (!legendRef.current) return;
      if (param.point === undefined || !param.time) return;

      const currentData = param.seriesData.get(candlestickSeries);
      const volumeData = param.seriesData.get(volumeSeries);

      if (currentData) {
        const { open, high, low, close } = currentData;
        const color = close >= open ? '#26a69a' : '#ef5350';
        const change = close - open;
        const changePct = (change / open) * 100;
        const sign = change >= 0 ? '+' : '';
        
        let volFmt = '0';
        if (volumeData) {
          const v = volumeData.value;
          if (v >= 1000000) volFmt = (v / 1000000).toFixed(2) + 'M';
          else if (v >= 1000) volFmt = (v / 1000).toFixed(2) + 'k';
          else volFmt = v.toString();
        }

        // Generate indicator legend HTML dynamically
        let indHtml = '';
        Object.entries(indicatorSeriesRef.current).forEach(([id, obj]) => {
           let valStr = '';
           if (obj.type === 'BOLL') {
             // Bollinger has upper, lower, basis
             const basisD = param.seriesData.get(obj.series[0]);
             const upperD = param.seriesData.get(obj.series[1]);
             const lowerD = param.seriesData.get(obj.series[2]);
             const b = basisD ? basisD.value.toFixed(2) : 'N/A';
             const u = upperD ? upperD.value.toFixed(2) : 'N/A';
             const l = lowerD ? lowerD.value.toFixed(2) : 'N/A';
             valStr = `basis: ${b} upper: ${u} lower: ${l}`;
           } else {
             const d = param.seriesData.get(obj.series);
             valStr = d ? d.value.toFixed(2) : 'N/A';
           }
           indHtml += `<span style="color: ${obj.color}">${obj.type}${obj.period ? obj.period : ''} <strong>${valStr}</strong></span>`;
        });

        legendRef.current.innerHTML = `
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; line-height: 1;">
              <div style="font-weight: 600; font-size: 13px; display: flex; align-items: center; gap: 4px; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff;">
                ${symbol || 'SYMBOL'} <span style="color: #888">·</span> ${interval}m <span style="color: #888">·</span> NSE
                <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background-color:${color}; margin-left: 2px;"></span>
              </div>
              <div style="font-size: 12px; font-family: monospace; display: flex; gap: 8px; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff;">
                <span>O <span style="color: ${color}">${open.toFixed(2)}</span></span>
                <span>H <span style="color: ${color}">${high.toFixed(2)}</span></span>
                <span>L <span style="color: ${color}">${low.toFixed(2)}</span></span>
                <span>C <span style="color: ${color}">${close.toFixed(2)} <span style="margin-left: 4px;">${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)</span></span></span>
              </div>
            </div>
            <div style="font-size: 11px; font-family: monospace; display: flex; gap: 8px; flex-wrap: wrap; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff;">
              <span style="color: #333">Vol <span style="color: #26a69a">${volFmt}</span></span>
              ${indHtml}
            </div>
          </div>
        `;
      }
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      volumeSeriesRef.current = null;
      indicatorSeriesRef.current = {};
      loadedRef.current = false;
      lastTimeRef.current = 0;
    };
  }, [symbol, interval]);

  // Sync Indicators (add/remove series when indicators array changes)
  useEffect(() => {
    if (!chartRef.current) return;
    const chart = chartRef.current;
    const currentIds = new Set(indicators.map(i => i.id));
    
    // Remove deleted ones
    Object.keys(indicatorSeriesRef.current).forEach(id => {
      if (!currentIds.has(id)) {
        const obj = indicatorSeriesRef.current[id];
        if (Array.isArray(obj.series)) {
           obj.series.forEach(s => chart.removeSeries(s));
        } else {
           chart.removeSeries(obj.series);
        }
        delete indicatorSeriesRef.current[id];
      }
    });

    // Add new ones
    indicators.forEach((ind, index) => {
      if (!indicatorSeriesRef.current[ind.id]) {
        const color = getIndicatorColor(ind.type, index);
        if (ind.type === 'BOLL') {
           const basis = chart.addSeries(LineSeries, { color, lineWidth: 1, crosshairMarkerVisible: false, priceLineVisible: false, lastValueVisible: true, autoscaleInfoProvider: () => ({ priceRange: null }) });
           const upper = chart.addSeries(LineSeries, { color, lineWidth: 1, crosshairMarkerVisible: false, priceLineVisible: false, lastValueVisible: true, autoscaleInfoProvider: () => ({ priceRange: null }), lineStyle: 2 });
           const lower = chart.addSeries(LineSeries, { color, lineWidth: 1, crosshairMarkerVisible: false, priceLineVisible: false, lastValueVisible: true, autoscaleInfoProvider: () => ({ priceRange: null }), lineStyle: 2 });
           indicatorSeriesRef.current[ind.id] = { type: ind.type, period: ind.period, color, series: [basis, upper, lower] };
        } else {
           const series = chart.addSeries(LineSeries, { color, lineWidth: 2, crosshairMarkerVisible: false, priceLineVisible: false, lastValueVisible: true, autoscaleInfoProvider: () => ({ priceRange: null }) });
           indicatorSeriesRef.current[ind.id] = { type: ind.type, period: ind.period, color, series };
        }
      } else {
         // Update period if changed
         indicatorSeriesRef.current[ind.id].period = ind.period;
      }
    });
  }, [indicators]);

  // Update Data
  useEffect(() => {
    if (!seriesRef.current || !data || data.length === 0) return;

    const chartData = data
      .map((r) => ({
        time: (new Date(r.ts).getTime() / 1000) + 19800,
        open: r.open, high: r.high, low: r.low, close: r.close,
        volume: Math.max(0, r.volume || 0),
      }))
      .sort((a, b) => a.time - b.time);

    const uniqueData = [];
    let lastTime = -1;
    for (const d of chartData) {
      if (d.time > lastTime) { uniqueData.push(d); lastTime = d.time; } 
      else { d.time = lastTime + 0.001; uniqueData.push(d); lastTime = d.time; }
    }

    if (!loadedRef.current) {
      seriesRef.current.setData(uniqueData);
      volumeSeriesRef.current.setData(uniqueData.map(d => ({
        time: d.time, value: d.volume, color: d.close >= d.open ? 'rgba(38, 166, 154, 0.4)' : 'rgba(239, 83, 80, 0.4)'
      })));
      chartRef.current.timeScale().fitContent();
      loadedRef.current = true;
    } else {
      for (const candle of uniqueData) {
        if (candle.time >= lastTimeRef.current) {
          seriesRef.current.update(candle);
          volumeSeriesRef.current.update({
            time: candle.time, value: candle.volume, color: candle.close >= candle.open ? 'rgba(38, 166, 154, 0.4)' : 'rgba(239, 83, 80, 0.4)'
          });
        }
      }
    }
    if (uniqueData.length > 0) lastTimeRef.current = uniqueData[uniqueData.length - 1].time;

    // Calculate and update indicator data
    Object.values(indicatorSeriesRef.current).forEach(obj => {
      let indData = [];
      if (obj.type === 'EMA') indData = calculateEMA(uniqueData, obj.period || 20);
      else if (obj.type === 'SMA') indData = calculateSMA(uniqueData, obj.period || 20);
      else if (obj.type === 'VWAP') indData = calculateVWAP(uniqueData);
      else if (obj.type === 'BOLL') indData = calculateBollingerBands(uniqueData, obj.period || 20, 2);

      if (obj.type === 'BOLL') {
         obj.series[0].setData(indData.map(d => ({ time: d.time, value: d.basis })));
         obj.series[1].setData(indData.map(d => ({ time: d.time, value: d.upper })));
         obj.series[2].setData(indData.map(d => ({ time: d.time, value: d.lower })));
      } else {
         obj.series.setData(indData);
      }
    });

  }, [data, indicators]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div 
        ref={legendRef} 
        style={{ 
          position: "absolute", top: 12, left: 12, zIndex: 10, 
          fontSize: "12px", fontFamily: "sans-serif", pointerEvents: "none", 
          backgroundColor: "transparent", color: "#333",
        }} 
      />
      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}
