import { useEffect, useRef } from "react";
import { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } from "lightweight-charts";
import { calculateEMA, calculateVWAP } from "./indicators";

export default function CandleChart({ data, symbol, interval }) {
  const chartContainerRef = useRef(null);
  const legendRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  
  const ema20Ref = useRef(null);
  const ema50Ref = useRef(null);
  const vwapRef = useRef(null);

  const loadedRef = useRef(false);
  const lastTimeRef = useRef(0);

  // 1. Initialize Chart
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
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        scaleMargins: {
          top: 0.15,    // Leave 15% space at the top so candles don't hide under legend
          bottom: 0.25, // Leave 25% space at the bottom for the volume
        },
      },
      autoSize: true, // Let lightweight-charts handle resizing natively!
    });
    chartRef.current = chart;

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: true,
      borderUpColor: "#26a69a",
      borderDownColor: "#ef5350",
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });
    seriesRef.current = candlestickSeries;

    const ema20Series = chart.addSeries(LineSeries, {
      color: '#2196F3',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: true,
      autoscaleInfoProvider: () => ({ priceRange: null }),
    });
    ema20Ref.current = ema20Series;

    const ema50Series = chart.addSeries(LineSeries, {
      color: '#FF9800',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: true,
      autoscaleInfoProvider: () => ({ priceRange: null }),
    });
    ema50Ref.current = ema50Series;

    const vwapSeries = chart.addSeries(LineSeries, {
      color: '#9C27B0',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: true,
      autoscaleInfoProvider: () => ({ priceRange: null }),
    });
    vwapRef.current = vwapSeries;

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: '', // set as an overlay by setting a blank priceScaleId
    });
    
    // Scale volume to be at the bottom 15% of the chart so it doesn't overlap candles
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.85, 
        bottom: 0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    chart.subscribeCrosshairMove((param) => {
      if (!legendRef.current) return;
      if (param.point === undefined || !param.time || param.point.x < 0 || param.point.x > chartContainerRef.current.clientWidth || param.point.y < 0 || param.point.y > chartContainerRef.current.clientHeight) {
        // Crosshair is out of bounds, you could reset to latest candle, but keeping last hovered is fine
      } else {
        const currentData = param.seriesData.get(candlestickSeries);
        const volumeData = param.seriesData.get(volumeSeries);
        const ema20Data = param.seriesData.get(ema20Series);
        const ema50Data = param.seriesData.get(ema50Series);
        const vwapData = param.seriesData.get(vwapSeries);

        if (currentData) {
          const { open, high, low, close } = currentData;
          const color = close >= open ? '#26a69a' : '#ef5350';
          
          const change = close - open;
          const changePct = (change / open) * 100;
          const sign = change >= 0 ? '+' : '';
          
          const intervalLabel = 
            interval === '1' ? '1 min' :
            interval === '3' ? '3 min' :
            interval === '5' ? '5 min' :
            interval === '10' ? '10min' :
            interval === '15' ? '15 min' :
            interval === '60' ? '1 hrs' :
            interval === 'D' ? '1 days' : interval;
            
          const ema20Str = ema20Data ? ema20Data.value.toFixed(2) : 'N/A';
          const ema50Str = ema50Data ? ema50Data.value.toFixed(2) : 'N/A';
          const vwapStr = vwapData ? vwapData.value.toFixed(2) : 'N/A';
          
          let volFmt = '0';
          if (volumeData) {
            const v = volumeData.value;
            if (v >= 1000000) volFmt = (v / 1000000).toFixed(2) + 'M';
            else if (v >= 1000) volFmt = (v / 1000).toFixed(2) + 'k';
            else volFmt = v.toString();
          }

          legendRef.current.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; line-height: 1;">
                <div style="font-weight: 600; font-size: 13px; display: flex; align-items: center; gap: 4px; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff;">
                  ${symbol || 'SYMBOL'} <span style="color: #888">•</span> ${intervalLabel} <span style="color: #888">•</span> NSE
                  <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background-color:${color}; margin-left: 2px;"></span>
                </div>
                <div style="font-size: 12px; font-family: monospace; display: flex; gap: 8px; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff;">
                  <span>O <span style="color: ${color}">${open.toFixed(2)}</span></span>
                  <span>H <span style="color: ${color}">${high.toFixed(2)}</span></span>
                  <span>L <span style="color: ${color}">${low.toFixed(2)}</span></span>
                  <span>C <span style="color: ${color}">${close.toFixed(2)} <span style="margin-left: 4px;">${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)</span></span></span>
                </div>
              </div>
              <div style="font-size: 11px; font-family: monospace; display: flex; gap: 8px; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff;">
                <span style="color: #333">Vol <span style="color: #26a69a">${volFmt}</span></span>
                <span style="color: #2196F3">EMA20 <strong>${ema20Str}</strong></span>
                <span style="color: #FF9800">EMA50 <strong>${ema50Str}</strong></span>
                <span style="color: #9C27B0">VWAP <strong>${vwapStr}</strong></span>
              </div>
            </div>
          `;
        }
      }
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      volumeSeriesRef.current = null;
      ema20Ref.current = null;
      ema50Ref.current = null;
      vwapRef.current = null;
      loadedRef.current = false;
      lastTimeRef.current = 0;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2. Update Data
  useEffect(() => {
    if (!seriesRef.current || !data || data.length === 0) return;

    const chartData = data
      .map((r) => ({
        // lightweight-charts defaults to UTC display. We add 19800s (5.5 hrs) to hard-shift it to IST.
        time: (new Date(r.ts).getTime() / 1000) + 19800,
        open: r.open,
        high: r.high,
        low: r.low,
        close: r.close,
        volume: Math.max(0, r.volume || 0),
      }))
      .filter(r => r.open > 0 && r.high > 0 && r.low > 0 && r.close > 0)
      .sort((a, b) => a.time - b.time)
      .filter((r, idx, arr) => idx === 0 || r.time !== arr[idx - 1].time);

    const ema20Data = calculateEMA(chartData, 20);
    const ema50Data = calculateEMA(chartData, 50);
    const vwapData = calculateVWAP(chartData);

    if (!loadedRef.current) {
      // First load: set all data and fit content
      seriesRef.current.setData(chartData);
      
      const volumeData = chartData.map(c => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
      }));
      volumeSeriesRef.current.setData(volumeData);
      
      if (ema20Ref.current) ema20Ref.current.setData(ema20Data);
      if (ema50Ref.current) ema50Ref.current.setData(ema50Data);
      if (vwapRef.current) vwapRef.current.setData(vwapData);
      
      chartRef.current.timeScale().fitContent();
      loadedRef.current = true;
      if (chartData.length > 0) {
        lastTimeRef.current = chartData[chartData.length - 1].time;
      }
    } else {
      // Subsequent updates: only update/append the latest candles
      // lightweight-charts requires new updates to have time >= the last existing time.
      chartData.forEach((candle, idx) => {
        if (candle.time >= lastTimeRef.current) {
          seriesRef.current.update(candle);
          volumeSeriesRef.current.update({
            time: candle.time,
            value: candle.volume,
            color: candle.close >= candle.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
          });
          
          if (ema20Ref.current && ema20Data[idx]) ema20Ref.current.update(ema20Data[idx]);
          if (ema50Ref.current && ema50Data[idx]) ema50Ref.current.update(ema50Data[idx]);
          if (vwapRef.current && vwapData[idx]) vwapRef.current.update(vwapData[idx]);
          
          lastTimeRef.current = candle.time;
        }
      });
    }
  }, [data]);

  return (
    <div className="w-full h-full flex flex-col relative bg-transparent">
      <style>
        {`
          #my-tv-chart a, 
          #tv-attr-logo {
            display: none !important;
            opacity: 0 !important;
            pointer-events: none !important;
          }
        `}
      </style>
      <div className="flex-1 relative min-h-0 w-full">
        <div id="my-tv-chart" ref={chartContainerRef} className="absolute inset-0" />
        <div 
          ref={legendRef} 
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            padding: '4px 8px',
            color: '#333',
            background: 'transparent',
            minHeight: '24px',
            display: 'flex',
            alignItems: 'center',
            zIndex: 10,
            pointerEvents: 'none'
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <div style={{ fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', textShadow: '-1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff' }}>
              {symbol || 'SYMBOL'} <span style={{color: '#888'}}>•</span> {
                interval === '1' ? '1 min' :
                interval === '3' ? '3 min' :
                interval === '5' ? '5 min' :
                interval === '10' ? '10min' :
                interval === '15' ? '15 min' :
                interval === '60' ? '1 hrs' :
                interval === 'D' ? '1 days' : interval
              } <span style={{color: '#888'}}>•</span> NSE
            </div>
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: '#888', textShadow: '-1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 4px #fff' }}>
              Hover over chart for OHLC and Indicators
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
