import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { Activity, BarChart3, PieChart as PieChartIcon } from 'lucide-react'
import { METRIC_SERIES } from '../lib/data'

const RANGE_OPTIONS = [
  { label: '8W', value: 8 },
  { label: '12W', value: 12 },
  { label: '16W', value: 16 },
]

const TRACK_OPTIONS = [
  { key: 'mrr', label: 'MRR', color: '#2dd4bf' },
  { key: 'conversion', label: 'Conversion', color: '#22d3ee' },
  { key: 'churn', label: 'Churn', color: '#fb7185' },
  { key: 'tickets', label: 'Tickets', color: '#f59e0b' },
]

const REGION_COLORS = ['#f43f5e', '#60a5fa', '#22c55e']

const fmtCurrency = (value) => `$${(value / 1000).toFixed(0)}K`

const MetricTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-white/[0.1] bg-[#090c0b] px-3 py-2 shadow-2xl">
      <div className="text-[10px] text-zinc-500 mb-1">{label}</div>
      {payload.map((entry) => (
        <div
          key={entry.name}
          className="text-[11px] font-medium flex items-center justify-between gap-5"
          style={{ color: entry.color }}
        >
          <span>{entry.name}</span>
          <span className="tabular-nums">
            {entry.name === 'MRR' ? fmtCurrency(entry.value) : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

const CardTitle = ({ icon: Icon, title, subtitle }) => (
  <div className="flex items-center justify-between mb-3">
    <div className="flex items-center gap-2">
      <span className="w-6 h-6 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center">
        <Icon size={13} className="text-zinc-300" />
      </span>
      <div>
        <div className="text-[11px] font-semibold text-zinc-200 uppercase tracking-widest">{title}</div>
        <div className="text-[10px] text-zinc-600">{subtitle}</div>
      </div>
    </div>
  </div>
)

export default function ChartsFocusPanel() {
  const [weeks, setWeeks] = useState(12)
  const [track, setTrack] = useState('mrr')

  const series = useMemo(() => METRIC_SERIES.slice(-weeks), [weeks])
  const latest = series[series.length - 1]
  const previous = series[series.length - 2] ?? latest
  const selectedTrack = TRACK_OPTIONS.find((option) => option.key === track) ?? TRACK_OPTIONS[0]
  const delta = latest[track] - previous[track]

  const regionShare = useMemo(() => {
    const total = latest.eu + latest.us + latest.apac
    if (!total) return []
    return [
      { name: 'EU', value: Number(((latest.eu / total) * 100).toFixed(1)) },
      { name: 'US', value: Number(((latest.us / total) * 100).toFixed(1)) },
      { name: 'APAC', value: Number(((latest.apac / total) * 100).toFixed(1)) },
    ]
  }, [latest])

  return (
    <div className="h-full p-5 md:p-6 overflow-y-auto">
      <div className="max-w-[1200px] mx-auto flex flex-col gap-4">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="flex flex-col md:flex-row md:items-end md:justify-between gap-3"
        >
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500 font-semibold">Live Metrics</div>
            <h2 className="text-[2rem] md:text-[2.2rem] leading-none tracking-tight text-white font-black mt-1">
              Chart-Centric Diagnostic View
            </h2>
            <p className="text-[12px] text-zinc-500 mt-2">
              Monitor revenue behavior first. Expand chat only when you want agent-driven investigation.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setWeeks(option.value)}
                className={`h-7 px-3 rounded-lg border text-[11px] font-semibold transition ${
                  weeks === option.value
                    ? 'bg-teal-500/20 text-teal-300 border-teal-500/50'
                    : 'bg-white/[0.03] text-zinc-500 border-white/[0.08] hover:text-zinc-200'
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
          transition={{ duration: 0.35, delay: 0.06 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-2"
        >
          {TRACK_OPTIONS.map((option) => (
            <button
              key={option.key}
              onClick={() => setTrack(option.key)}
              className={`text-left rounded-xl border p-3 transition ${
                track === option.key
                  ? 'bg-white/[0.08] border-white/[0.16]'
                  : 'bg-white/[0.03] border-white/[0.08] hover:bg-white/[0.05]'
              }`}
            >
              <div className="text-[10px] uppercase tracking-widest text-zinc-500">{option.label}</div>
              <div className="text-[18px] text-zinc-100 font-bold tabular-nums mt-1">
                {option.key === 'mrr'
                  ? `$${latest[option.key].toLocaleString()}`
                  : option.key === 'tickets'
                  ? latest[option.key]
                  : `${latest[option.key].toFixed(1)}%`}
              </div>
              {track === option.key && (
                <div className={`text-[10px] mt-1 font-semibold ${delta < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {delta < 0 ? '−' : '+'}
                  {option.key === 'mrr'
                    ? `$${(Math.abs(delta) / 1000).toFixed(1)}K`
                    : option.key === 'tickets'
                    ? Math.abs(delta)
                    : `${Math.abs(delta).toFixed(1)} pts`}{' '}
                  vs previous week
                </div>
              )}
            </button>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="card p-4"
        >
          <CardTitle
            icon={Activity}
            title={`${selectedTrack.label} Trend`}
            subtitle={`${weeks}-week interactive timeline`}
          />
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={series} margin={{ top: 8, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="trackFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={selectedTrack.color} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={selectedTrack.color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="week" tick={{ fill: '#52525b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis
                tick={{ fill: '#52525b', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={track === 'mrr' ? fmtCurrency : undefined}
              />
              <Tooltip content={<MetricTip />} />
              <Area
                type="monotone"
                dataKey={track}
                name={selectedTrack.label}
                stroke={selectedTrack.color}
                strokeWidth={2.5}
                fill="url(#trackFill)"
                activeDot={{ r: 4, fill: selectedTrack.color, stroke: '#0b0f0e', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.14 }}
            className="card p-4 xl:col-span-2"
          >
            <CardTitle icon={BarChart3} title="Operational Pressure" subtitle="Conversion, churn, and ticket load" />
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={series} margin={{ top: 6, right: 6, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="week" tick={{ fill: '#52525b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="left" tick={{ fill: '#52525b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: '#52525b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip content={<MetricTip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: '#71717a' }} />
                <Line yAxisId="left" dataKey="conversion" name="Conversion %" stroke="#22d3ee" strokeWidth={2} dot={false} />
                <Line yAxisId="left" dataKey="churn" name="Churn %" stroke="#fb7185" strokeWidth={2} dot={false} />
                <Line yAxisId="right" dataKey="tickets" name="Tickets" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.16 }}
            className="card p-4"
          >
            <CardTitle icon={PieChartIcon} title="Regional Mix" subtitle={`${latest.week} contribution`} />
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={regionShare}
                  cx="50%"
                  cy="50%"
                  dataKey="value"
                  innerRadius={48}
                  outerRadius={76}
                  paddingAngle={3}
                >
                  {regionShare.map((entry, index) => (
                    <Cell key={entry.name} fill={REGION_COLORS[index % REGION_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => `${value}%`} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: '#71717a' }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-3 gap-2 mt-2">
              {regionShare.map((entry, index) => (
                <div key={entry.name} className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-2 py-1.5 text-center">
                  <div className="text-[9px] text-zinc-500 uppercase tracking-widest">{entry.name}</div>
                  <div className="text-[12px] font-semibold mt-0.5" style={{ color: REGION_COLORS[index % REGION_COLORS.length] }}>
                    {entry.value}%
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.2 }}
          className="card p-4"
        >
          <CardTitle icon={BarChart3} title="Revenue by Region" subtitle="Absolute contribution trend" />
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={series} margin={{ top: 8, right: 4, left: -14, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="week" tick={{ fill: '#52525b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#52525b', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={fmtCurrency} />
              <Tooltip content={<MetricTip />} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: '#71717a' }} />
              <Bar dataKey="eu" name="EU" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              <Bar dataKey="us" name="US" fill="#60a5fa" radius={[4, 4, 0, 0]} />
              <Bar dataKey="apac" name="APAC" fill="#22c55e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>
      </div>
    </div>
  )
}
