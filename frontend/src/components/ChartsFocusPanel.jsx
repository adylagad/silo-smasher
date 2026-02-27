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
import { Activity, BarChart3, PieChart as PieChartIcon, Radar } from 'lucide-react'
import { METRIC_SERIES } from '../lib/data'

const RANGE_OPTIONS = [
  { label: '8W', value: 8 },
  { label: '12W', value: 12 },
  { label: '16W', value: 16 },
]

const TRACK_OPTIONS = [
  { key: 'five_xx', label: '500/min', color: '#38bdf8', type: 'count' },
  { key: 'error_rate', label: 'Error Rate', color: '#fb7185', type: 'percent' },
  { key: 'p95_latency_ms', label: 'p95 Latency', color: '#22d3ee', type: 'ms' },
  { key: 'oncall_pages', label: 'Pages', color: '#f59e0b', type: 'count' },
]

const SOURCE_COLORS = ['#38bdf8', '#22c55e', '#f97316']

const formatValue = (value, type) => {
  if (type === 'percent') return `${Number(value).toFixed(1)}%`
  if (type === 'ms') return `${Math.round(Number(value))} ms`
  return `${Number(value).toLocaleString()}`
}

const tooltipValue = (name, value) => {
  if (String(name).toLowerCase().includes('error rate')) return `${Number(value).toFixed(1)}%`
  if (String(name).toLowerCase().includes('latency')) return `${Math.round(Number(value))} ms`
  return `${Number(value).toLocaleString()}`
}

const MetricTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-slate-300/25 bg-[#07111d] px-3 py-2 shadow-2xl">
      <div className="text-[10px] text-slate-400 mb-1">{label}</div>
      {payload.map((entry) => (
        <div
          key={entry.name}
          className="text-[11px] font-semibold flex items-center justify-between gap-5"
          style={{ color: entry.color }}
        >
          <span>{entry.name}</span>
          <span className="tabular-nums">{tooltipValue(entry.name, entry.value)}</span>
        </div>
      ))}
    </div>
  )
}

const CardTitle = ({ icon: Icon, title, subtitle, right }) => (
  <div className="flex items-start justify-between mb-3">
    <div className="flex items-start gap-2.5">
      <span className="w-7 h-7 rounded-xl bg-sky-400/14 border border-sky-400/25 flex items-center justify-center mt-0.5">
        <Icon size={13} className="text-sky-300" />
      </span>
      <div>
        <div className="text-[11px] font-bold text-slate-100 uppercase tracking-widest">{title}</div>
        {subtitle ? <div className="text-[11px] text-slate-400 mt-0.5">{subtitle}</div> : null}
      </div>
    </div>
    {right}
  </div>
)

export default function ChartsFocusPanel() {
  const [weeks, setWeeks] = useState(12)
  const [track, setTrack] = useState('five_xx')

  const series = useMemo(() => METRIC_SERIES.slice(-weeks), [weeks])
  const latest = series[series.length - 1]
  const previous = series[series.length - 2] ?? latest
  const selectedTrack = TRACK_OPTIONS.find((option) => option.key === track) ?? TRACK_OPTIONS[0]
  const delta = latest[track] - previous[track]

  const sourceShare = useMemo(() => {
    const total = latest.api_errors + latest.db_errors + latest.dependency_errors
    if (!total) return []
    return [
      { name: 'API', value: Number(((latest.api_errors / total) * 100).toFixed(1)) },
      { name: 'Database', value: Number(((latest.db_errors / total) * 100).toFixed(1)) },
      { name: 'Dependency', value: Number(((latest.dependency_errors / total) * 100).toFixed(1)) },
    ]
  }, [latest])

  return (
    <div className="h-full p-4 md:p-6 overflow-y-auto">
      <div className="max-w-[1320px] mx-auto flex flex-col gap-4 md:gap-5 pb-24">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4"
        >
          <div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-400 font-bold">Incident Telemetry</div>
            <h2 className="text-[2rem] md:text-[2.35rem] leading-[1.05] tracking-tight text-white font-extrabold mt-1">
              Signals first. <span className="gradient-text">Then investigate.</span>
            </h2>
          </div>

          <div className="flex items-center gap-2 self-start lg:self-auto">
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setWeeks(option.value)}
                className={`h-8 px-3 rounded-xl border text-[11px] font-bold transition ${
                  weeks === option.value
                    ? 'bg-sky-400/20 text-sky-200 border-sky-300/50'
                    : 'bg-slate-900/50 text-slate-300 border-slate-300/25 hover:text-white hover:border-slate-300/45'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.06 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-2"
        >
          {TRACK_OPTIONS.map((option) => {
            const isActive = track === option.key
            const directionClass = delta <= 0 ? 'text-emerald-300' : 'text-rose-300'
            return (
              <button
                key={option.key}
                onClick={() => setTrack(option.key)}
                className={`text-left rounded-2xl border px-3 py-3 transition-all ${
                  isActive
                    ? 'bg-[#0a1929] border-sky-300/35 shadow-[0_12px_30px_rgba(8,47,73,0.4)]'
                    : 'bg-[#07111d]/85 border-slate-300/20 hover:border-slate-200/35 hover:bg-[#0a1625]'
                }`}
              >
                <div className="text-[10px] uppercase tracking-[0.15em] text-slate-400 font-bold">{option.label}</div>
                <div className="text-[19px] text-slate-50 font-extrabold tabular-nums mt-1">
                  {formatValue(latest[option.key], option.type)}
                </div>
                {isActive && (
                  <div className={`text-[10px] mt-1 font-bold ${directionClass}`}>
                    {delta <= 0 ? '−' : '+'}
                    {option.type === 'percent'
                      ? `${Math.abs(delta).toFixed(1)} pts`
                      : option.type === 'ms'
                      ? `${Math.abs(delta).toFixed(0)} ms`
                      : Math.abs(delta)}
                  </div>
                )}
              </button>
            )
          })}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="card panel-hover p-4 md:p-5"
        >
          <CardTitle
            icon={Activity}
            title={`${selectedTrack.label} Trend`}
            right={<span className="soft-pill px-2.5 py-1 text-[10px] text-slate-300 font-semibold">Latest: {latest.week}</span>}
          />
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={series} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="trackFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={selectedTrack.color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={selectedTrack.color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.18)" vertical={false} />
              <XAxis dataKey="week" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<MetricTip />} />
              <Area
                type="monotone"
                dataKey={track}
                name={selectedTrack.label}
                stroke={selectedTrack.color}
                strokeWidth={2.6}
                fill="url(#trackFill)"
                activeDot={{ r: 4.5, fill: selectedTrack.color, stroke: '#05101c', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.14 }}
            className="card panel-hover p-4 md:p-5 xl:col-span-2"
          >
            <CardTitle icon={BarChart3} title="Runtime Health Signals" />
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={series} margin={{ top: 6, right: 6, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.16)" vertical={false} />
                <XAxis dataKey="week" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="left" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip content={<MetricTip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
                <Line yAxisId="left" dataKey="error_rate" name="Error Rate %" stroke="#fb7185" strokeWidth={2.2} dot={false} />
                <Line yAxisId="right" dataKey="p95_latency_ms" name="p95 Latency (ms)" stroke="#22d3ee" strokeWidth={2.2} dot={false} />
                <Line yAxisId="left" dataKey="oncall_pages" name="On-call Pages" stroke="#f59e0b" strokeWidth={2.2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.16 }}
            className="card panel-hover p-4 md:p-5"
          >
            <CardTitle icon={PieChartIcon} title="Error Source Mix" subtitle={latest.week} />
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={sourceShare} cx="50%" cy="50%" dataKey="value" innerRadius={48} outerRadius={76} paddingAngle={3}>
                  {sourceShare.map((entry, index) => (
                    <Cell key={entry.name} fill={SOURCE_COLORS[index % SOURCE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => `${value}%`} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-3 gap-2 mt-2.5">
              {sourceShare.map((entry, index) => (
                <div key={entry.name} className="rounded-xl border border-slate-300/20 bg-[#0a1726] px-2 py-1.5 text-center">
                  <div className="text-[9px] text-slate-400 uppercase tracking-widest font-bold">{entry.name}</div>
                  <div className="text-[12px] font-bold mt-0.5" style={{ color: SOURCE_COLORS[index % SOURCE_COLORS.length] }}>
                    {entry.value}%
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.2 }}
          className="grid grid-cols-1 lg:grid-cols-3 gap-4"
        >
          <div className="card panel-hover p-4 md:p-5 lg:col-span-2">
            <CardTitle icon={Radar} title="Error Volume by Subsystem" />
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={series} margin={{ top: 8, right: 4, left: -14, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.16)" vertical={false} />
                <XAxis dataKey="week" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip content={<MetricTip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
                <Bar dataKey="api_errors" name="API" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="db_errors" name="Database" fill="#22c55e" radius={[4, 4, 0, 0]} />
                <Bar dataKey="dependency_errors" name="Dependency" fill="#f97316" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card panel-hover p-4 md:p-5 flex flex-col justify-between">
            <CardTitle icon={Activity} title="Incident Note" />
            <div className="rounded-xl border border-rose-300/20 bg-rose-400/10 px-3 py-3">
              <div className="text-[11px] uppercase tracking-wider text-rose-200/80 font-bold">Signal</div>
              <div className="text-[12px] leading-relaxed text-slate-100 mt-1">HTTP 500 up sharply after deploy. p95 latency and pages increased.</div>
            </div>
            <div className="rounded-xl border border-sky-300/20 bg-sky-400/10 px-3 py-3 mt-3">
              <div className="text-[11px] uppercase tracking-wider text-sky-200/90 font-bold">Action</div>
              <div className="text-[12px] leading-relaxed text-slate-100 mt-1">Open chat to generate root cause + mitigation + PR draft.</div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
