import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';
import Panel from './Panel';

export default function StrategyBuilderPanel({ legs = [], onRemoveLeg, onClear }) {
  if (!legs || legs.length === 0) {
    return (
      <div className="mb-4">
        <Panel title="Strategy Builder" kicker="Expiry Payoff">
          <div className="flex flex-col items-center justify-center p-8 text-center text-[var(--text-secondary)] border-2 border-dashed border-[var(--border)] rounded-md bg-[var(--background)]">
            <h3 className="font-bold text-lg mb-2 text-[var(--text-primary)]">Strategy Builder is Active</h3>
            <p className="max-w-md">Hover over the LTP (Last Traded Price) column in the Option Chain below and click the <span className="bg-green-500 text-white px-1.5 py-0.5 rounded text-[10px] font-bold mx-1">B</span> or <span className="bg-red-500 text-white px-1.5 py-0.5 rounded text-[10px] font-bold mx-1">S</span> buttons to add legs to your strategy.</p>
          </div>
        </Panel>
      </div>
    );
  }

  // Calculate Payoff Data
  const calculatePayoff = () => {
    // Find min and max strike to determine range
    if (legs.length === 0) return [];
    
    const strikes = legs.map(l => l.strike);
    const minStrike = Math.min(...strikes);
    const maxStrike = Math.max(...strikes);
    
    // Generate spot prices from minStrike - 500 to maxStrike + 500
    const start = minStrike - 500;
    const end = maxStrike + 500;
    const step = 20;
    
    const data = [];
    
    for (let spot = start; spot <= end; spot += step) {
      let totalPnl = 0;
      
      legs.forEach(leg => {
        const { type, side, strike, premium, qty = 50 } = leg;
        let intrinsic = 0;
        
        if (type === 'CE') {
          intrinsic = Math.max(0, spot - strike);
        } else {
          intrinsic = Math.max(0, strike - spot);
        }
        
        let pnl = 0;
        if (side === 'Buy') {
          pnl = (intrinsic - premium) * qty;
        } else {
          pnl = (premium - intrinsic) * qty;
        }
        
        totalPnl += pnl;
      });
      
      data.push({ spot, pnl: totalPnl });
    }
    
    return data;
  };

  const data = calculatePayoff();
  
  const maxProfit = Math.max(...data.map(d => d.pnl));
  const maxLoss = Math.min(...data.map(d => d.pnl));
  
  // Calculate Net Premium
  let netPremium = 0;
  legs.forEach(l => {
    if (l.side === 'Buy') netPremium -= l.premium * (l.qty || 50);
    if (l.side === 'Sell') netPremium += l.premium * (l.qty || 50);
  });

  // Calculate Breakevens
  const breakevens = [];
  for (let i = 1; i < data.length; i++) {
    if ((data[i-1].pnl > 0 && data[i].pnl < 0) || (data[i-1].pnl < 0 && data[i].pnl > 0)) {
      const fraction = Math.abs(data[i-1].pnl) / (Math.abs(data[i-1].pnl) + Math.abs(data[i].pnl));
      const be = data[i-1].spot + fraction * (data[i].spot - data[i-1].spot);
      breakevens.push(be.toFixed(0));
    }
  }

  // Calculate Risk/Reward
  let riskReward = 'N/A';
  if (maxProfit > 0 && maxLoss < 0 && maxProfit < 50000 && maxLoss > -50000) {
    const risk = Math.abs(maxLoss);
    const reward = maxProfit;
    riskReward = `1 : ${(reward / risk).toFixed(2)}`;
  } else if (maxLoss >= 0 && maxProfit > 0) {
    riskReward = 'Zero Risk';
  } else if (maxProfit <= 0 && maxLoss < 0) {
    riskReward = 'Zero Reward';
  }

  // Calculate correct gradient offset for the AreaChart so 0 is exactly the split point
  const gradientOffset = () => {
    if (maxProfit <= 0) return 0;
    if (maxLoss >= 0) return 1;
    return maxProfit / (maxProfit - maxLoss);
  };
  const off = gradientOffset();

  return (
    <div className="mb-4">
      <Panel title="Strategy Builder" kicker="Expiry Day Payoff">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-4">
          {/* Left: Legs list */}
          <div className="lg:col-span-1 flex flex-col">
            <div className="flex justify-between items-center mb-2 pb-2 border-b border-[var(--border)]">
              <h3 className="text-xs font-bold uppercase tracking-widest dim">Selected Legs</h3>
              <button onClick={onClear} className="text-[10px] uppercase tracking-wider font-bold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Clear All</button>
            </div>
            
            <div className="space-y-0 mb-4 flex-1">
              {legs.map((leg, idx) => (
                <div key={idx} className="flex justify-between items-center py-2 border-b border-[var(--border)] group">
                  <div className="flex items-center gap-3">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider text-white ${leg.side === 'Buy' ? 'bg-green-500' : 'bg-red-500'}`}>
                      {leg.side}
                    </span>
                    <span className="text-xs font-bold font-mono">{leg.strike} <span className="dim font-sans">{leg.type}</span></span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono dim">₹{leg.premium.toFixed(2)}</span>
                    <button onClick={() => onRemoveLeg(idx)} className="text-[var(--text-muted)] hover:text-red-500 transition-colors opacity-50 group-hover:opacity-100">×</button>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="grid grid-cols-2 gap-y-4 gap-x-2 py-4 border-t border-[var(--border)] bg-[var(--surface)] px-3 rounded">
              <div>
                <div className="text-[10px] dim uppercase tracking-widest mb-1">Net Premium</div>
                <div className={`text-sm font-bold font-mono ${netPremium > 0 ? 'text-green-500' : netPremium < 0 ? 'text-red-500' : 'text-[var(--text-primary)]'}`}>
                  {netPremium > 0 ? '+' : ''}{netPremium.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-[10px] dim uppercase tracking-widest mb-1">Risk : Reward</div>
                <div className="text-sm font-bold font-mono text-[var(--text-primary)]">
                  {riskReward}
                </div>
              </div>
              <div>
                <div className="text-[10px] dim uppercase tracking-widest mb-1">Max Profit</div>
                <div className="text-sm font-bold font-mono text-green-500">
                  {maxProfit > 50000 ? 'Unlimited' : '+' + maxProfit.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-[10px] dim uppercase tracking-widest mb-1">Max Loss</div>
                <div className="text-sm font-bold font-mono text-red-500">
                  {maxLoss < -50000 ? 'Unlimited' : maxLoss.toFixed(2)}
                </div>
              </div>
              <div className="col-span-2">
                <div className="text-[10px] dim uppercase tracking-widest mb-1">Breakeven Points</div>
                <div className="text-sm font-bold font-mono text-[var(--text-primary)]">
                  {breakevens.length > 0 ? breakevens.join(', ') : 'None / N/A'}
                </div>
              </div>
            </div>
            
            <button className="w-full mt-4 bg-[var(--brand)] text-white font-bold py-2.5 rounded text-xs uppercase tracking-widest hover:brightness-110 transition-all">
              Deploy Strategy
            </button>
          </div>
          
          {/* Right: Chart */}
          <div className="lg:col-span-2 h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="splitColor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset={off} stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset={off} stopColor="#ef4444" stopOpacity={0.4} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} vertical={false} />
                <XAxis 
                  dataKey="spot" 
                  stroke="var(--text-muted)" 
                  fontSize={10} 
                  tickFormatter={(val) => val.toString()} 
                  tickMargin={10}
                />
                <YAxis 
                  stroke="var(--text-muted)" 
                  fontSize={10} 
                  tickFormatter={(val) => val > 1000 || val < -1000 ? (val/1000).toFixed(1) + 'k' : val}
                  tickMargin={10}
                />
                <Tooltip 
                  formatter={(value) => [`₹${value.toFixed(2)}`, 'P&L']}
                  labelFormatter={(label) => `Spot: ${label}`}
                  contentStyle={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '12px' }}
                  itemStyle={{ fontWeight: 'bold' }}
                />
                <ReferenceLine y={0} stroke="var(--text-secondary)" strokeDasharray="3 3" />
                {legs.length > 0 && (
                  <ReferenceLine 
                    x={legs[0].strike} 
                    stroke="var(--brand)" 
                    strokeDasharray="3 3" 
                    label={{ position: 'top', value: 'ATM', fill: 'var(--brand)', fontSize: 10, fontWeight: 'bold' }} 
                  />
                )}
                <Area 
                  type="monotone" 
                  dataKey="pnl" 
                  stroke="var(--text-primary)" 
                  strokeWidth={2}
                  fill="url(#splitColor)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Panel>
    </div>
  );
}
