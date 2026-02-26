import { motion, AnimatePresence } from 'framer-motion'
import { X, Database, Share2, Globe, ShieldCheck, Activity } from 'lucide-react'

const STEPS = [
  {
    icon: Activity,
    title: 'Describe the anomaly',
    body: 'Start with plain language: revenue dip, churn spike, or conversion miss. The system turns this into a structured diagnostic objective.',
  },
  {
    icon: Database,
    title: 'Generate hypotheses',
    body: 'The orchestrator drafts likely explanations and prioritizes them by causal plausibility before any heavy querying starts.',
  },
  {
    icon: Share2,
    title: 'Traverse relationships',
    body: 'Graph traversal links customers, orders, tickets, and regions to expose which entities are truly connected to the metric movement.',
  },
  {
    icon: Globe,
    title: 'Cross-check outside signals',
    body: 'External context is pulled in for weather, macroeconomics, market news, and competitive movement that may explain local variance.',
  },
  {
    icon: ShieldCheck,
    title: 'Score and summarize',
    body: 'Guardrails filter weak claims. You get a concise confidence-scored brief and recommended next actions.',
  },
]

export default function GuideModal({ open, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 bg-[#02060d]/78 backdrop-blur-sm z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          <motion.div
            className="fixed inset-y-0 right-0 w-full max-w-[420px] bg-[#07111d]/96 border-l border-slate-300/20 z-50 flex flex-col shadow-[0_30px_80px_rgba(2,6,14,0.8)]"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
          >
            <div className="h-0.5 w-full bg-gradient-to-r from-sky-300/70 via-cyan-300/40 to-transparent flex-shrink-0" />

            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-300/20 flex-shrink-0">
              <div>
                <h2 className="text-sm font-extrabold text-white">How The Diagnostic Loop Works</h2>
                <p className="text-[11px] text-slate-400 mt-0.5">Five automated stages from signal to explanation</p>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-200/10 transition-colors"
              >
                <X size={14} />
              </button>
            </div>

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
                    <div className="flex flex-col items-center">
                      <div className="w-8 h-8 rounded-xl bg-sky-400/14 border border-sky-300/25 flex items-center justify-center shrink-0">
                        <Icon size={14} className="text-sky-300" />
                      </div>
                      {i < STEPS.length - 1 && (
                        <div className="w-px flex-1 bg-slate-300/20 my-1.5" />
                      )}
                    </div>

                    <div className={`flex-1 ${i < STEPS.length - 1 ? 'pb-4' : ''}`}>
                      <div className="flex items-center gap-2 mb-1 mt-1.5">
                        <span className="text-[9px] font-bold text-slate-300 bg-slate-300/10 border border-slate-300/20 rounded px-1.5 py-0.5 tabular-nums">
                          {i + 1}
                        </span>
                        <span className="text-xs font-bold text-slate-100">{step.title}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-relaxed">{step.body}</p>
                    </div>
                  </motion.div>
                )
              })}
            </div>

            <div className="px-5 py-4 border-t border-slate-300/20 flex-shrink-0 space-y-2.5">
              <div className="rounded-xl bg-sky-400/10 border border-sky-300/20 p-3">
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  <span className="font-bold text-sky-200">Tip:</span>{' '}
                  Use the chart filters first, then open chat to investigate the exact interval where the anomaly starts.
                </p>
              </div>
              <button
                onClick={onClose}
                className="w-full h-9 rounded-xl bg-gradient-to-r from-sky-400 to-cyan-300 text-slate-950 text-xs font-extrabold transition-opacity hover:opacity-95"
              >
                Start Investigation
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
