import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingDown, TrendingUp, Minus, BarChart3, Activity, LifeBuoy } from 'lucide-react'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  ComposedChart,
} from 'recharts'
import { AVG_MRR, METRIC_SERIES, STATS } from '../lib/data'

const RANGE_OPTIONS = [
  { label: '8W', value: 8 },
  { label: '12W', value: 12 },
  { label: '16W', value: 16 },
]

const fmtCurrency = (value) => `$${(value / 1000).toFixed(0)}K`

const trendMeta = (delta) => {
  if (delta > 0) return { icon: TrendingUp, cls: 'text-emerald-400' }
  if (delta < 0) return { icon: TrendingDown, cls: 'text-rose-400' }
  return { icon: Minus, cls: 'text-zinc-500' }
}

const DataTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-white/[0.1] bg-[#0a0d0c] px-3 py-2 shadow-2xl">
      <div className="text-[10px] text-zinc-500 mb-1">{label}</div>
      <div className="flex flex-col gap-0.5">
        {payload.map((entry) => (
          <div
            key={entry.name}
            className="text-[11px] font-medium flex items-center justify-between gap-5"
            style={{ color: entry.color }}
          >
            <span>{entry.name}</span>
            <span className="tabular-nums">
              {typeof entry.value === 'number' && entry.name.toLowerCase().includes('mrr')
                ? fmtCurrency(entry.value)
                : entry.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

const SectionTitle = ({ icon: Icon, title, subtitle }) => (
  <div className="flex items-start justify-between mb-2.5">
    <div className="flex items-center gap-2">
      <span className="w-5 h-5 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center">
        <Icon size={11} className="text-zinc-400" />
      </span>
      <div>
        <div className="text-[10px] font-semibold text-zinc-300 uppercase tracking-widest">{title}</div>
        {subtitle ? <div className="text-[10px] text-zinc-600">{subtitle}</div> : null}
      </div>
    </div>
  </div>
)

export default function MetricPanel() {
  const [weeks, setWeeks] = useState(12)
  const [focusWeek, setFocusWeek] = useState(METRIC_SERIES[METRIC_SERIES.length - 1].week)

  const series = useMemo(() => METRIC_SERIES.slice(-weeks), [weeks])
  const current = series[series.length - 1]
  const previous = series[series.length - 2] ?? current
  const wowDelta = ((current.mrr - previous.mrr) / previous.mrr) * 100
  const baselineDelta = current.mrr - AVG_MRR
  const mrrTrend = trendMeta(baselineDelta)
  const wowTrend = trendMeta(wowDelta)

  return (
    <div className="flex flex-col h-full">
      <div className="h-0.5 w-full bg-gradient-to-r from-teal-500/70 via-teal-400/30 to-transparent flex-shrink-0" />
      <div className="flex-1 flex flex-col px-4 py-4 gap-4 overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="flex items-center justify-between"
        >
          <div>
            <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">Context</div>
            <div className="text-[11px] text-zinc-600 mt-1">Interactive metric explorer</div>
          </div>
          <div className="flex items-center gap-1">
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setWeeks(option.value)}
                className={`h-6 px-2 rounded-md border text-[10px] font-semibold transition-all ${
                  weeks === option.value
                    ? 'bg-teal-500/20 text-teal-300 border-teal-400/40'
                    : 'bg-white/[0.03] text-zinc-500 border-white/[0.08] hover:text-zinc-300'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.05 }}
          className="card p-3"
        >
          <div className="flex items-end justify-between">
            <div>
              <div className="text-[9px] text-zinc-600 uppercase tracking-widest font-semibold">Current MRR</div>
              <div className="text-[2.2rem] font-black text-white tracking-tighter leading-none tabular-nums">
                ${current.mrr.toLocaleString()}
              </div>
            </div>
            <div className="flex flex-col gap-1 items-end mb-1">
              <span className={`flex items-center gap-1 text-[10px] font-semibold ${mrrTrend.cls}`}>
                <mrrTrend.icon size={10} />
                {baselineDelta < 0 ? '−' : '+'}${(Math.abs(baselineDelta) / 1000).toFixed(1)}K vs baseline
              </span>
              <span className={`flex items-center gap-1 text-[10px] font-semibold ${wowTrend.cls}`}>
                <wowTrend.icon size={10} />
                {wowDelta < 0 ? '−' : '+'}{Math.abs(wowDelta).toFixed(1)}% WoW
              </span>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.08 }}
          className="grid grid-cols-2 gap-2"
        >
          {STATS.slice(0, 4).map((stat) => (
            <div key={stat.label} className="card px-2.5 py-2">
              <div className="text-[9px] uppercase tracking-widest text-zinc-600">{stat.label}</div>
              <div className={`text-[15px] font-bold tabular-nums mt-1 ${stat.color}`}>{stat.value}</div>
            </div>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.12 }}
          className="card p-3"
        >
          <SectionTitle icon={Activity} title="Revenue Signal" subtitle={`Focus: ${focusWeek}`} />
          <ResponsiveContainer width="100%" height={150}>
            <AreaChart data={series} margin={{ top: 4, right: 2, left: -14, bottom: 0 }}>
              <defs>
                <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.26} />
                  <stop offset="100%" stopColor="#14b8a6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis
                dataKey="week"
                tick={{ fill: '#52525b', fontSize: 9 }}
                axisLine={false}
                tickLine={false}
                onClick={(event) => {
                  if (event?.value) setFocusWeek(event.value)
                }}
              />
              <YAxis
                tickFormatter={fmtCurrency}
                tick={{ fill: '#52525b', fontSize: 9 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<DataTip />} />
              <Area
                dataKey="mrr"
                name="MRR"
                type="monotone"
                stroke="#2dd4bf"
                strokeWidth={2}
                fill="url(#revenueFill)"
                activeDot={{ r: 4, stroke: '#0f766e', strokeWidth: 2, fill: '#5eead4' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.16 }}
          className="card p-3"
        >
          <SectionTitle icon={BarChart3} title="Conversion vs Churn" subtitle="Quality tension over time" />
          <ResponsiveContainer width="100%" height={130}>
            <ComposedChart data={series} margin={{ top: 4, right: 2, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="week" tick={{ fill: '#52525b', fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="left" tick={{ fill: '#52525b', fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: '#52525b', fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip content={<DataTip />} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 10, color: '#71717a' }} />
              <Line yAxisId="left" type="monotone" dataKey="conversion" name="Conversion %" stroke="#22d3ee" strokeWidth={2} dot={false} />
              <Line yAxisId="right" type="monotone" dataKey="churn" name="Churn %" stroke="#fb7185" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.2 }}
          className="card p-3"
        >
          <SectionTitle icon={LifeBuoy} title="Support Pressure" subtitle="Tickets + regional revenue mix" />
          <div className="grid grid-cols-1 gap-3">
            <ResponsiveContainer width="100%" height={110}>
              <BarChart data={series} margin={{ top: 4, right: 2, left: -14, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="week" tick={{ fill: '#52525b', fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#52525b', fontSize: 9 }} axisLine={false} tickLine={false} />
                <Tooltip content={<DataTip />} />
                <Bar dataKey="tickets" name="Tickets" fill="#f59e0b" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>

            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={series} margin={{ top: 2, right: 2, left: -14, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="week" tick={{ fill: '#52525b', fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={fmtCurrency} tick={{ fill: '#52525b', fontSize: 9 }} axisLine={false} tickLine={false} />
                <Tooltip content={<DataTip />} />
                <Legend iconType="line" wrapperStyle={{ fontSize: 10, color: '#71717a' }} />
                <Line dataKey="eu" name="EU" stroke="#f43f5e" strokeWidth={2} dot={false} />
                <Line dataKey="us" name="US" stroke="#60a5fa" strokeWidth={2} dot={false} />
                <Line dataKey="apac" name="APAC" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        <div className="pt-1 pb-1 text-[9px] text-zinc-700 text-center">
          Silo Smasher · Metric Intelligence
        </div>
      </div>
    </div>
  )
}
