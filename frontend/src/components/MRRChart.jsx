import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer, Dot,
} from 'recharts'
import { MRR_DATA, AVG_MRR } from '../lib/data'

const fmt = v => '$' + (v / 1000).toFixed(0) + 'K'

const CustomDot = (props) => {
  const { cx, cy, index } = props
  if (index < 6) return null
  return (
    <g>
      <circle cx={cx} cy={cy} r={10} fill="rgba(244,63,94,0.15)" />
      <circle cx={cx} cy={cy} r={6}  fill="rgba(244,63,94,0.25)" />
      <circle cx={cx} cy={cy} r={3.5} fill="#f43f5e" />
    </g>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const val = payload[0].value
  const isAnomaly = MRR_DATA.findIndex(d => d.week === label) >= 6
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 shadow-xl">
      <div className="text-xs text-zinc-400 mb-1">{label}</div>
      <div className={`text-sm font-bold ${isAnomaly ? 'text-rose-400' : 'text-white'}`}>
        ${val.toLocaleString()}
      </div>
      {isAnomaly && (
        <div className="text-[10px] text-rose-400/70 mt-0.5">⚠ Drop zone</div>
      )}
    </div>
  )
}

export default function MRRChart() {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
          MRR — 8 Week Trend
        </span>
        <div className="flex items-center gap-3 text-[10px] text-zinc-600">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-indigo-500 rounded" />MRR
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-px border-t border-dashed border-zinc-600" />Avg
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500/80" />Anomaly
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={148}>
        <AreaChart data={MRR_DATA} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id="mrrFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#6366f1" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0}    />
            </linearGradient>
            <linearGradient id="mrrStroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%"   stopColor="#6366f1" />
              <stop offset="70%"  stopColor="#818cf8" />
              <stop offset="100%" stopColor="#f43f5e" />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="week" tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'Inter' }}
            axisLine={false} tickLine={false}
          />
          <YAxis
            tickFormatter={fmt} tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'Inter' }}
            axisLine={false} tickLine={false} domain={[70000, 115000]}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#3f3f46', strokeWidth: 1 }} />
          <ReferenceLine
            y={AVG_MRR} stroke="#3f3f46" strokeDasharray="5 4" strokeWidth={1.5}
            label={{ value: 'avg', fill: '#52525b', fontSize: 9, position: 'insideTopLeft' }}
          />
          <Area
            type="monotone" dataKey="mrr"
            stroke="url(#mrrStroke)" strokeWidth={2.5}
            fill="url(#mrrFill)"
            dot={<CustomDot />} activeDot={{ r: 4, fill: '#818cf8', stroke: '#4f46e5', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
