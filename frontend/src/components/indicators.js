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

export function calculateSMA(data, period) {
  if (!data || data.length === 0) return [];
  const smaData = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      // Not enough data yet, we can either skip or calculate partial average. Let's do partial.
      let sum = 0;
      for (let j = 0; j <= i; j++) sum += data[j].close;
      smaData.push({ time: data[i].time, value: sum / (i + 1) });
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += data[i - j].close;
      smaData.push({ time: data[i].time, value: sum / period });
    }
  }
  return smaData;
}

export function calculateBollingerBands(data, period, stdDev = 2) {
  if (!data || data.length === 0) return [];
  const sma = calculateSMA(data, period);
  const bbData = [];
  
  for (let i = 0; i < data.length; i++) {
    let variance = 0;
    const mean = sma[i].value;
    const windowStart = Math.max(0, i - period + 1);
    const windowSize = i - windowStart + 1;
    
    for (let j = windowStart; j <= i; j++) {
      variance += Math.pow(data[j].close - mean, 2);
    }
    variance /= windowSize;
    
    const std = Math.sqrt(variance);
    bbData.push({
      time: data[i].time,
      upper: mean + stdDev * std,
      lower: mean - stdDev * std,
      basis: mean
    });
  }
  return bbData;
}
