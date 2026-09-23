import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend
} from 'recharts';
import type { SpeedPoint, NetworkInterface } from '../types';

interface SpeedChartProps {
  data: SpeedPoint[];
  interfaces: NetworkInterface[];
}

const INTERFACE_COLORS: Record<string, string> = {
  combined: '#06b6d4',      // Cyan
  ethernet: '#10b981',      // Emerald
  wifi: '#3b82f6',          // Blue
  usb_tether: '#f59e0b',    // Amber
  sim_ethernet: '#10b981',
  sim_wifi: '#3b82f6',
  sim_usb: '#f59e0b',
  virtual: '#8b5cf6',
  vpn: '#ec4899'
};

export const SpeedChart: React.FC<SpeedChartProps> = ({ data, interfaces }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-sm">
        <p>Awaiting network telemetry...</p>
      </div>
    );
  }

  return (
    <div className="w-full h-64 sm:h-72">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorCombined" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0}/>
            </linearGradient>
            <linearGradient id="colorEth" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#10b981" stopOpacity={0.0}/>
            </linearGradient>
            <linearGradient id="colorWifi" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0}/>
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.6} />
          
          <XAxis 
            dataKey="timeLabel" 
            stroke="#64748b" 
            fontSize={11}
            tickLine={false}
          />
          
          <YAxis 
            stroke="#64748b" 
            fontSize={11} 
            tickFormatter={(val) => `${val.toFixed(1)}M`}
            tickLine={false}
          />

          <Tooltip
            contentStyle={{
              backgroundColor: '#0f172a',
              borderColor: '#334155',
              borderRadius: '0.5rem',
              fontSize: '12px',
              color: '#f8fafc',
              boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)'
            }}
            formatter={(value: any, name: any) => [`${Number(value).toFixed(2)} Mbps`, name]}
          />

          <Legend 
            wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
          />

          {/* Combined Throughput Area */}
          <Area
            type="monotone"
            dataKey="combined_mbps"
            name="Combined Speed"
            stroke="#06b6d4"
            strokeWidth={2.5}
            fillOpacity={1}
            fill="url(#colorCombined)"
            isAnimationActive={false}
          />

          {/* Dynamic Lines for Active Interfaces */}
          {interfaces.map((iface) => {
            const color = INTERFACE_COLORS[iface.type] || INTERFACE_COLORS[iface.id] || '#94a3b8';
            return (
              <Area
                key={iface.id}
                type="monotone"
                dataKey={iface.id}
                name={iface.name}
                stroke={color}
                strokeWidth={1.5}
                fillOpacity={0.1}
                fill={color}
                isAnimationActive={false}
              />
            );
          })}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
