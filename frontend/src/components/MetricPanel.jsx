import { motion } from 'framer-motion'
import { TrendingDown, TrendingUp, Minus } from 'lucide-react'
import MRRChart from './MRRChart'

const STATS = [
  { label: 'WoW Change',     value: '−15.2%', trend: 'down',    color: 'text-rose-400'   },
  { label: 'Region',         value: 'UK / EU', trend: 'neutral', color: 'text-zinc-300'   },
  { label: 'Conversion',     value: '61.4%',  trend: 'down',    color: 'text-rose-400'   },
  { label: 'Churn Rate',     value: '8.0%',   trend: 'up',      color: 'text-amber-400'  },
  { label: 'Return Rate',    value: '8.2%',   trend: 'neutral', color: 'text-zinc-400'   },
  { label: 'Open Tickets',   value: '+34%',   trend: 'up',      color: 'text-amber-400'  },
]

const TrendIcon = ({ trend }) => {
  if (trend === 'down')    return <TrendingDown size={10} className="text-rose-500/60"  />
  if (trend === 'up')      return <TrendingUp   size={10} className="text-amber-500/60" />
  return <Minus size={10} className="text-zinc-700" />
}

const fade = (delay = 0) => ({
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, delay },
})

export default function MetricPanel() {
  return (
    <div className="flex flex-col h-full">
      {/* ── Teal accent bar at top ── */}
      <div className="h-0.5 w-full bg-gradient-to-r from-teal-500/60 via-teal-400/30 to-transparent flex-shrink-0" />

      <div className="flex-1 flex flex-col px-4 py-4 gap-5 overflow-y-auto">

        {/* ── Panel label + live badge ── */}
        <motion.div className="flex items-center justify-between" {...fade(0)}>
          <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
            Context
          </span>
          <span className="flex items-center gap-1.5 text-[10px] text-teal-400/70 font-medium">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-50" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-teal-400" />
            </span>
            Live
          </span>
        </motion.div>

        {/* ── Hero MRR ── */}
        <motion.div {...fade(0.05)}>
          <div className="text-[9px] text-zinc-600 uppercase tracking-widest font-semibold mb-2">
            Monthly Recurring Revenue
          </div>
          <div
            className="text-[2.75rem] font-black text-white tracking-tighter leading-none"
            style={{ fontVariantNumeric: 'tabular-nums' }}
          >
            $84,500
          </div>
          <div className="flex items-center gap-2 mt-2.5">
            <div className="flex items-center gap-1 bg-rose-500/10 border border-rose-500/20 rounded-full px-2 py-0.5">
              <TrendingDown size={10} className="text-rose-400" />
              <span className="text-[10px] font-bold text-rose-400">−15.2% WoW</span>
            </div>
            <span className="text-[10px] text-zinc-600">−$18.7K vs avg</span>
          </div>
        </motion.div>

        {/* ── Period ── */}
        <motion.div
          className="flex items-center gap-2 text-[10px] text-zinc-600"
          {...fade(0.08)}
        >
          <span className="inline-block w-1 h-1 rounded-full bg-teal-500/50" />
          Period: Feb 10 – Feb 24, 2025
        </motion.div>

        {/* ── Separator ── */}
        <div className="h-px bg-white/[0.05]" />

        {/* ── MRR Chart ── */}
        <motion.div {...fade(0.12)}>
          <MRRChart />
        </motion.div>

        {/* ── Separator ── */}
        <div className="h-px bg-white/[0.05]" />

        {/* ── Stats list ── */}
        <motion.div {...fade(0.18)}>
          <div className="text-[9px] font-semibold text-zinc-600 uppercase tracking-widest mb-1">
            Key Metrics
          </div>
          <div>
            {STATS.map(({ label, value, trend, color }) => (
              <div key={label} className="stat-row">
                <span className="text-[11px] text-zinc-500">{label}</span>
                <div className="flex items-center gap-1.5">
                  <TrendIcon trend={trend} />
                  <span className={`text-[11px] font-semibold tabular-nums ${color}`}>
                    {value}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* ── Separator ── */}
        <div className="h-px bg-white/[0.05]" />

        {/* ── Anomaly alert ── */}
        <motion.div {...fade(0.24)}>
          <div className="rounded-xl border border-rose-500/15 bg-rose-500/[0.04] p-3.5">
            <div className="flex items-start gap-2.5">
              {/* Pulsing dot */}
              <span className="relative flex h-2 w-2 mt-0.5 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-40" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500" />
              </span>
              <div>
                <div className="text-[10px] font-bold text-rose-400 uppercase tracking-wide mb-1">
                  Anomaly Active
                </div>
                <p className="text-[10px] text-zinc-500 leading-relaxed">
                  Sustained decline{' '}
                  <span className="text-zinc-300 font-medium">$18.7K below the 6-week baseline</span>.
                  {' '}UK / EU churn elevated.
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* ── Bottom spacer ── */}
        <div className="flex-1" />

        {/* ── Footer watermark ── */}
        <div className="text-[9px] text-zinc-700 text-center pb-1">
          Silo Smasher · Autonomous BI
        </div>

      </div>
    </div>
  )
}
