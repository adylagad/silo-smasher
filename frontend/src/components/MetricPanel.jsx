import { motion } from 'framer-motion'
import { TrendingDown, AlertTriangle } from 'lucide-react'
import MRRChart from './MRRChart'
import { STATS } from '../lib/data'

export default function MetricPanel() {
  return (
    <div className="flex flex-col gap-3 min-h-0">
      {/* Hero metric */}
      <motion.div
        className="card p-4 flex-shrink-0"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-1">
              Current MRR
            </div>
            <div className="text-3xl font-bold text-white tracking-tight">$84,500</div>
            <div className="flex items-center gap-1.5 mt-1.5">
              <div className="flex items-center gap-1 text-rose-400 text-xs font-semibold">
                <TrendingDown size={12} />
                −15.2% WoW
              </div>
              <span className="text-zinc-600 text-xs">vs $99.7K avg</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
            <TrendingDown size={18} className="text-rose-400" />
          </div>
        </div>
      </motion.div>

      {/* MRR Chart */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <MRRChart />
      </motion.div>

      {/* Stats grid */}
      <motion.div
        className="grid grid-cols-3 gap-2 flex-shrink-0"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        {STATS.map(({ label, value, color }) => (
          <div key={label} className="card p-3">
            <div className="text-[9px] text-zinc-500 uppercase tracking-wider font-semibold mb-1 truncate">
              {label}
            </div>
            <div className={`text-sm font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </motion.div>

      {/* Incident banner */}
      <motion.div
        className="card border-l-2 border-l-amber-500 p-3 flex-shrink-0"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
      >
        <div className="flex gap-2.5">
          <AlertTriangle size={14} className="text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <div className="text-xs font-semibold text-amber-400 mb-0.5">Anomaly Detected</div>
            <div className="text-[11px] text-zinc-400 leading-relaxed">
              MRR has dropped{' '}
              <span className="text-white font-medium">$18.7K below baseline</span> over the last
              2 weeks. UK / EU region showing elevated churn and conversion pressure.
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
