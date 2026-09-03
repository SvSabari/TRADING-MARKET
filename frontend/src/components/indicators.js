export function calculateEMA(data, period) {
  if (!data || data.length === 0) return [];
  const k = 2 / (period + 1);
  const emaData = [];
  let ema = data[0].close;
  emaData.push({ time: data[0].time, value: ema });
  for (let i = 1; i < data.length; i++) {
    ema = (data[i].close - ema) * k + ema;
    emaData.push({ time: data[i].time, value: ema });
  }
  return emaData;
}

export function calculateVWAP(data) {
  if (!data || data.length === 0) return [];
  const vwapData = [];
  let cumulativePV = 0;
  let cumulativeV = 0;
  let currentDay = -1;
  
  for (let i = 0; i < data.length; i++) {
    const d = data[i];
    const dateObj = new Date(d.time * 1000);
    const day = dateObj.getUTCDate();
    
    if (day !== currentDay) {
      cumulativePV = 0;
      cumulativeV = 0;
      currentDay = day;
    }
    
    const typicalPrice = (d.high + d.low + d.close) / 3;
    const volume = Number(d.volume) || 0;
    
    cumulativePV += typicalPrice * volume;
    cumulativeV += volume;
    
    const vwap = cumulativeV === 0 ? typicalPrice : cumulativePV / cumulativeV;
    vwapData.push({ time: d.time, value: vwap });
  }
  return vwapData;
}
