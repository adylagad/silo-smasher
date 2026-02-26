import { motion, AnimatePresence } from 'framer-motion'
import { X, Database, Share2, Globe, ShieldCheck, Activity } from 'lucide-react'

const STEPS = [
  {
    icon: Activity,
    title: 'Describe the anomaly',
    body: 'Type a plain-English question about any metric drop, revenue miss, or churn spike. Use a preset to see a live example.',
  },
  {
    icon: Database,
    title: 'Hypothesis generation',
    body: 'GPT-4o reads the query and generates ranked hypotheses — possible causes sorted by plausibility based on domain knowledge.',
  },
  {
    icon: Share2,
    title: 'Knowledge graph traversal',
    body: 'Neo4j GraphRAG traverses your entity graph to find which regions, SKUs, or campaigns are connected to the affected metric.',
  },
  {
    icon: Globe,
    title: 'External economic signals',
    body: 'Tavily Search fetches live news and macro signals — currency moves, competitor pricing, or regional events that may explain the drop.',
  },
  {
    icon: ShieldCheck,
    title: 'Safety scoring & brief',
    body: 'Fastino Safety scores each hypothesis for factual grounding and removes speculative claims before composing the final brief.',
  },
]

export default function GuideModal({ open, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 bg-black/75 backdrop-blur-sm z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          <motion.div
            className="fixed inset-y-0 right-0 w-full max-w-[400px] bg-[#090d0c] border-l border-white/[0.06] z-50 flex flex-col shadow-2xl"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
          >
            {/* Teal accent top bar */}
            <div className="h-0.5 w-full bg-gradient-to-r from-teal-500/70 via-teal-400/30 to-transparent flex-shrink-0" />

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.05] flex-shrink-0">
              <div>
                <h2 className="text-sm font-bold text-white">How Silo Smasher Works</h2>
                <p className="text-[11px] text-zinc-600 mt-0.5">5-step autonomous investigation pipeline</p>
              </div>
              <button
                onClick={onClose}
                className="w-7 h-7 rounded-lg flex items-center justify-center text-zinc-600 hover:text-zinc-300 hover:bg-white/[0.06] transition-colors"
              >
                <X size={13} />
              </button>
            </div>

            {/* Steps */}
            <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-0">
              {STEPS.map((step, i) => {
                const Icon = step.icon
                return (
                  <motion.div
                    key={step.title}
                    className="flex gap-3"
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.07 }}
                  >
                    {/* Icon + connector */}
                    <div className="flex flex-col items-center">
                      <div className="w-8 h-8 rounded-xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center shrink-0">
                        <Icon size={14} className="text-teal-400" />
                      </div>
                      {i < STEPS.length - 1 && (
                        <div className="w-px flex-1 bg-white/[0.05] my-1.5" />
                      )}
                    </div>

                    {/* Text */}
                    <div className={`flex-1 ${i < STEPS.length - 1 ? 'pb-4' : ''}`}>
                      <div className="flex items-center gap-2 mb-1 mt-1.5">
                        <span className="text-[9px] font-bold text-zinc-700 bg-white/[0.04] border border-white/[0.06] rounded px-1.5 py-0.5 tabular-nums">
                          {i + 1}
                        </span>
                        <span className="text-xs font-semibold text-zinc-200">{step.title}</span>
                      </div>
                      <p className="text-[11px] text-zinc-500 leading-relaxed">{step.body}</p>
                    </div>
                  </motion.div>
                )
              })}
            </div>

            {/* Footer */}
            <div className="px-5 py-4 border-t border-white/[0.05] flex-shrink-0 space-y-2.5">
              <div className="rounded-xl bg-teal-500/[0.07] border border-teal-500/15 p-3">
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  <span className="font-semibold text-teal-300">Tip:</span>{' '}
                  Use the preset questions on the investigation screen to see a complete end-to-end run.
                </p>
              </div>
              <button
                onClick={onClose}
                className="w-full h-9 rounded-xl bg-teal-600 hover:bg-teal-500 text-black text-xs font-bold transition-colors shadow-lg shadow-teal-600/20"
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
