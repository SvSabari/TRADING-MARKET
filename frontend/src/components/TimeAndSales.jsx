import { useState, useEffect, useRef } from "react";
import { usePolling } from "@/lib/use-polling";

export default function TimeAndSales({ symbol }) {
  // Poll market history every 1 second
  const { data } = usePolling(`/market/history/${encodeURIComponent(symbol)}?limit=300`, { intervalMs: 1000 });
  const [ticks, setTicks] = useState([]);
  const listRef = useRef(null);

  useEffect(() => {
    if (data && data.candles) {
      // 1. Get raw chronological data
      const raw = [...data.candles];
      
      // 2. Filter out 0-volume ticks FIRST so our math matches what the user sees
      const filtered = raw.filter(t => t.volume && t.volume > 0);
      
      // 3. Calculate direction chronologically
      let lastDirection = 'up';
      const processed = filtered.map((tick, i) => {
        let direction = 'neutral';
        
        if (i > 0) {
          const prevTick = filtered[i - 1];
          if (tick.ltp > prevTick.ltp) direction = 'up';
          else if (tick.ltp < prevTick.ltp) direction = 'down';
        }
        
        if (direction !== 'neutral') {
          lastDirection = direction;
        } else {
          direction = lastDirection;
        }
        
        // Format time
        const d = new Date(tick.ts);
        const timeStr = isNaN(d.getTime()) ? tick.ts : d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        return {
          id: tick.ts + tick.ltp + i,
          time: timeStr,
          price: tick.ltp.toFixed(2),
          volume: tick.volume,
          direction,
          type: direction === 'up' ? 'BUY' : 'SELL'
        };
      });
      
      // 4. Reverse for the tape display (newest first) and limit to 100
      setTicks(processed.reverse().slice(0, 100));
    }
  }, [data]);

  return (
    <div className="w-[260px] h-full flex flex-col" style={{ background: 'var(--surface)', borderLeft: '1px solid var(--border)' }}>
      {/* Header */}
      <div className="px-3 py-2 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)', background: 'var(--background)' }}>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <span className="text-xs font-bold uppercase tracking-wider text-[var(--text)]">Live Tape</span>
        </div>
        <span className="text-[10px] text-[var(--text-secondary)] font-bold uppercase">{symbol}</span>
      </div>
      
      {/* Table Header */}
      <div className="flex text-[10px] font-bold uppercase text-[var(--text-secondary)] px-3 py-1.5 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="w-[50px]">Time</div>
        <div className="flex-1 text-center">Type</div>
        <div className="flex-1 text-right">Price</div>
        <div className="flex-1 text-right">Qty</div>
      </div>
      
      {/* Tick List */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-1 custom-scrollbar" ref={listRef}>
        {!ticks.length && (
          <div className="text-xs text-center p-4 text-[var(--text-secondary)]">
            Waiting for trades...
          </div>
        )}
        
        {ticks.map((tick) => {
          // Colors
          let color = 'var(--text)';
          let bgColor = 'transparent';
          
          if (tick.direction === 'up') {
            color = '#26a69a';
            bgColor = 'rgba(38, 166, 154, 0.05)';
          } else if (tick.direction === 'down') {
            color = '#ef5350';
            bgColor = 'rgba(239, 83, 80, 0.05)';
          }
          
          return (
            <div 
              key={tick.id}
              className="flex items-center text-[11px] font-mono px-2 py-1 mb-[1px] rounded transition-colors duration-300"
              style={{ backgroundColor: bgColor, color: 'var(--text)' }}
            >
              <div className="w-[50px] text-[var(--text-secondary)] tracking-tighter">{tick.time}</div>
              <div className="flex-1 text-center font-bold text-[9px] uppercase tracking-wider" style={{ color }}>
                {tick.type}
              </div>
              <div className="flex-1 text-right font-semibold" style={{ color }}>
                {tick.price}
              </div>
              <div className="flex-1 text-right opacity-80 text-[var(--text)]">
                {tick.volume}
              </div>
            </div>
          );
        })}
      </div>
      
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: var(--border);
          border-radius: 4px;
        }
      `}} />
    </div>
  );
}
