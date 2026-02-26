import { motion } from 'framer-motion'
import { TrendingDown, AlertTriangle } from 'lucide-react'
import MRRChart from './MRRChart'
import { STATS } from '../lib/data'

const fade = (delay = 0) => ({
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, delay },
})

export default function MetricPanel() {
  return (
    <>
      {/* Section label */}
      <div className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-1 px-0.5">
        Live Context
      </div>

      {/* Hero MRR */}
      <motion.div {...fade(0)}>
        <div className="text-[10px] text-zinc-600 font-medium mb-1 uppercase tracking-wide">
          Current MRR
        </div>
        <div className="text-[2.6rem] font-black text-white tracking-tight leading-none">
          $84.5K
        </div>
        <div className="flex items-center gap-1.5 mt-2">
          <TrendingDown size={11} className="text-rose-400" />
          <span className="text-rose-400 text-xs font-bold">−15.2%</span>
          <span className="text-zinc-600 text-[11px]">vs $99.7K avg</span>
        </div>
      </motion.div>

      {/* Divider */}
      <div className="h-px bg-white/[0.05]" />

      {/* MRR Chart */}
      <motion.div {...fade(0.1)}>
        <MRRChart />
      </motion.div>

      {/* Divider */}
      <div className="h-px bg-white/[0.05]" />

      {/* Stats grid */}
      <motion.div className="grid grid-cols-2 gap-1.5" {...fade(0.2)}>
        {STATS.map(({ label, value, color }) => (
          <div key={label} className="card p-2.5 hover:border-white/[0.12] transition-colors">
            <div className="text-[9px] text-zinc-600 uppercase tracking-wider font-semibold truncate mb-1">
              {label}
            </div>
            <div className={`text-sm font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </motion.div>

      {/* Incident banner */}
      <motion.div
        className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3"
        {...fade(0.3)}
      >
        <div className="flex gap-2">
          <AlertTriangle size={12} className="text-amber-400 shrink-0 mt-0.5" />
          <div>
            <div className="text-[10px] font-semibold text-amber-400 mb-1">Anomaly Detected</div>
            <div className="text-[10px] text-zinc-500 leading-relaxed">
              MRR dropped{' '}
              <span className="text-zinc-300 font-medium">$18.7K below baseline</span>{' '}
              over 2 weeks. UK/EU showing elevated churn pressure.
            </div>
          </div>
        </div>
      </motion.div>
    </>
  )
}
