import { motion, AnimatePresence } from 'framer-motion'
import { X, Database, Share2, Globe, ShieldCheck, Lightbulb } from 'lucide-react'

const STEPS = [
  {
    icon: Lightbulb,
    color: 'indigo',
    title: 'Describe the anomaly',
    body: 'Type a plain-English question about any metric drop, revenue miss, or churn spike. Use a preset to see a live example.',
  },
  {
    icon: Database,
    color: 'violet',
    title: 'Hypothesis generation',
    body: 'GPT-4o reads the query and generates ranked hypotheses — possible causes ranked by plausibility based on domain knowledge.',
  },
  {
    icon: Share2,
    color: 'blue',
    title: 'Knowledge graph traversal',
    body: 'Neo4j GraphRAG traverses your entity graph to find which regions, SKUs, or campaigns are connected to the affected metric.',
  },
  {
    icon: Globe,
    color: 'cyan',
    title: 'External economic signals',
    body: 'Tavily Search fetches live news and macro signals — currency moves, competitor pricing, or regional events that may explain the drop.',
  },
  {
    icon: ShieldCheck,
    color: 'emerald',
    title: 'Safety scoring & brief',
    body: 'Fastino Safety scores each hypothesis for factual grounding and removes speculative claims before composing the final brief.',
  },
]

const colorMap = {
  indigo:  { bg: 'bg-indigo-500/10',  border: 'border-indigo-500/20',  icon: 'text-indigo-400'  },
  violet:  { bg: 'bg-violet-500/10',  border: 'border-violet-500/20',  icon: 'text-violet-400'  },
  blue:    { bg: 'bg-blue-500/10',    border: 'border-blue-500/20',    icon: 'text-blue-400'    },
  cyan:    { bg: 'bg-cyan-500/10',    border: 'border-cyan-500/20',    icon: 'text-cyan-400'    },
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', icon: 'text-emerald-400' },
}

export default function GuideModal({ open, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            className="fixed inset-y-0 right-0 w-full max-w-md bg-[#0f0f12] border-l border-zinc-800 z-50 flex flex-col shadow-2xl"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 280 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 flex-shrink-0">
              <div>
                <h2 className="text-sm font-bold text-white">How Silo Smasher Works</h2>
                <p className="text-[11px] text-zinc-500 mt-0.5">Autonomous 5-step investigation pipeline</p>
              </div>
              <button
                onClick={onClose}
                className="w-7 h-7 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            {/* Steps */}
            <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-3">
              {STEPS.map((step, i) => {
                const Icon  = step.icon
                const c     = colorMap[step.color]
                return (
                  <motion.div
                    key={step.title}
                    className="flex gap-3"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, delay: i * 0.07 }}
                  >
                    {/* Step number + connector */}
                    <div className="flex flex-col items-center">
                      <div className={`w-8 h-8 rounded-xl ${c.bg} border ${c.border} flex items-center justify-center flex-shrink-0`}>
                        <Icon size={15} className={c.icon} />
                      </div>
                      {i < STEPS.length - 1 && (
                        <div className="w-px flex-1 bg-zinc-800 my-1.5" />
                      )}
                    </div>

                    {/* Content */}
                    <div className="pb-3 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[9px] font-bold text-zinc-600 bg-zinc-800 rounded px-1.5 py-0.5">
                          STEP {i + 1}
                        </span>
                        <span className="text-xs font-semibold text-zinc-200">{step.title}</span>
                      </div>
                      <p className="text-[11px] text-zinc-400 leading-relaxed">{step.body}</p>
                    </div>
                  </motion.div>
                )
              })}
            </div>

            {/* Footer */}
            <div className="px-5 py-4 border-t border-zinc-800 flex-shrink-0">
              <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-3">
                <p className="text-[11px] text-indigo-300 leading-relaxed">
                  <span className="font-semibold text-indigo-200">Tip:</span> Try the preset questions to see a complete investigation with live API calls, graph traversal, and hypothesis scoring.
                </p>
              </div>
              <button
                onClick={onClose}
                className="mt-3 w-full h-9 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors"
              >
                Start Investigating
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
