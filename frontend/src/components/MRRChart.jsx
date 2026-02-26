import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import { MRR_DATA, AVG_MRR } from '../lib/data'

const fmt = v => '$' + (v / 1000).toFixed(0) + 'K'

const CustomDot = (props) => {
  const { cx, cy, index } = props
  if (index < 6) return null
  return (
    <g>
      <circle cx={cx} cy={cy} r={8}   fill="rgba(244,63,94,0.1)"  />
      <circle cx={cx} cy={cy} r={4.5} fill="rgba(244,63,94,0.2)"  />
      <circle cx={cx} cy={cy} r={2.5} fill="#f43f5e" />
    </g>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const val      = payload[0].value
  const isAnomaly = MRR_DATA.findIndex(d => d.week === label) >= 6
  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0b0e0d] px-3 py-2 shadow-2xl">
      <div className="text-[10px] text-zinc-500 mb-0.5">{label}</div>
      <div className={`text-sm font-bold ${isAnomaly ? 'text-rose-400' : 'text-white'}`}>
        ${val.toLocaleString()}
      </div>
      {isAnomaly && <div className="text-[9px] text-rose-500/60 mt-0.5">⚠ Drop zone</div>}
    </div>
  )
}

export default function MRRChart() {
  return (
    <div>
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-[9px] font-semibold text-zinc-700 uppercase tracking-wider">
          8-Week Trend
        </span>
        <div className="flex items-center gap-2.5 text-[9px] text-zinc-700">
          <span className="flex items-center gap-1">
            <span className="w-3 h-px bg-teal-500 inline-block rounded" />MRR
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-px border-t border-dashed border-zinc-700 inline-block" />Avg
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500/60 inline-block" />Drop
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={MRR_DATA} margin={{ top: 4, right: 2, left: -14, bottom: 0 }}>
          <defs>
            <linearGradient id="mrrFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#14b8a6" stopOpacity={0.18} />
              <stop offset="100%" stopColor="#14b8a6" stopOpacity={0}    />
            </linearGradient>
            <linearGradient id="mrrStroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%"   stopColor="#14b8a6" />
              <stop offset="68%"  stopColor="#2dd4bf" />
              <stop offset="100%" stopColor="#f43f5e" />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="week"
            tick={{ fill: '#3f3f46', fontSize: 8, fontFamily: 'Inter' }}
            axisLine={false} tickLine={false}
          />
          <YAxis
            tickFormatter={fmt}
            tick={{ fill: '#3f3f46', fontSize: 8, fontFamily: 'Inter' }}
            axisLine={false} tickLine={false} domain={[70000, 115000]}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#1f2421', strokeWidth: 1 }} />
          <ReferenceLine
            y={AVG_MRR} stroke="#1f2421" strokeDasharray="5 4" strokeWidth={1.5}
            label={{ value: 'avg', fill: '#3f3f46', fontSize: 8, position: 'insideTopLeft' }}
          />
          <Area
            type="monotone" dataKey="mrr"
            stroke="url(#mrrStroke)" strokeWidth={2}
            fill="url(#mrrFill)"
            dot={<CustomDot />}
            activeDot={{ r: 3.5, fill: '#2dd4bf', stroke: '#0d9488', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
