import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, ChevronRight, Loader2, Sparkles, CheckCircle2, AlertCircle, HelpCircle } from 'lucide-react'
import { STEPS, STEP_DURATIONS, PRESETS, STATUS_META } from '../lib/data'

const ToolBadge = ({ name }) => (
  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
    {name}
  </span>
)

const HypothesisCard = ({ hyp, index }) => {
  const meta = STATUS_META[hyp.status] ?? STATUS_META.inconclusive
  const StatusIcon = hyp.status === 'supported' ? CheckCircle2 : hyp.status === 'rejected' ? AlertCircle : HelpCircle

  return (
    <motion.div
      className={`card border-l-2 ${meta.border} p-3 ${meta.bg}`}
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, delay: index * 0.08 }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-xs text-zinc-200 leading-relaxed flex-1">{hyp.title}</p>
        <span className={`flex items-center gap-1 text-[10px] font-semibold shrink-0 ${meta.cls}`}>
          <StatusIcon size={10} />
          {meta.label}
        </span>
      </div>

      {/* Confidence bar */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[9px] text-zinc-500 w-14 shrink-0">Confidence</span>
        <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
          <motion.div
            className={`h-full rounded-full bg-gradient-to-r ${meta.bar}`}
            initial={{ width: 0 }}
            animate={{ width: `${hyp.confidence}%` }}
            transition={{ duration: 0.6, delay: index * 0.08 + 0.2 }}
          />
        </div>
        <span className={`text-[10px] font-semibold ${meta.cls} w-8 text-right shrink-0`}>
          {hyp.confidence}%
        </span>
      </div>

      {hyp.sources?.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[9px] text-zinc-600">via</span>
          {hyp.sources.map(s => <ToolBadge key={s} name={s} />)}
        </div>
      )}
    </motion.div>
  )
}

const StepRow = ({ step, state }) => {
  // state: 'pending' | 'active' | 'done'
  return (
    <div className="flex items-center gap-2.5 py-1.5">
      <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
        {state === 'done'
          ? <CheckCircle2 size={14} className="text-indigo-400" />
          : state === 'active'
          ? <Loader2 size={12} className="text-indigo-400 animate-spin" />
          : <div className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
        }
      </div>
      <span className={`text-xs flex-1 ${state === 'pending' ? 'text-zinc-600' : state === 'active' ? 'text-zinc-200' : 'text-zinc-400'}`}>
        {step.label}
      </span>
      {state !== 'pending' && <ToolBadge name={step.tool} />}
    </div>
  )
}

export default function InvestigatePanel() {
  const [query, setQuery]           = useState('')
  const [status, setStatus]         = useState('idle')  // idle | running | done | error
  const [activeStep, setActiveStep] = useState(-1)
  const [result, setResult]         = useState(null)
  const feedRef                     = useRef(null)

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [activeStep, result])

  const runQuery = async (q) => {
    const text = (q ?? query).trim()
    if (!text || status === 'running') return

    setQuery(text)
    setStatus('running')
    setActiveStep(0)
    setResult(null)

    // Animate through steps
    let step = 0
    const advance = () => {
      step++
      if (step < STEPS.length) {
        setActiveStep(step)
        setTimeout(advance, STEP_DURATIONS[step])
      }
    }
    setTimeout(advance, STEP_DURATIONS[0])

    try {
      const res = await fetch('/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text }),
      })
      const data = await res.json()
      setResult(data)
      setActiveStep(STEPS.length)  // all done
      setStatus('done')
    } catch {
      setResult({ error: 'Could not reach the API. Is the backend running?' })
      setActiveStep(STEPS.length)
      setStatus('error')
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      runQuery()
    }
  }

  const isRunning = status === 'running'

  return (
    <div className="flex flex-col h-full gap-3 min-h-0">
      {/* Query input */}
      <div className="card p-3 flex-shrink-0">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <textarea
              rows={2}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Describe the metric anomaly you want to investigate…"
              disabled={isRunning}
              className="w-full bg-transparent resize-none text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none leading-relaxed pr-2 disabled:opacity-50"
            />
          </div>
          <button
            onClick={() => runQuery()}
            disabled={isRunning || !query.trim()}
            className="self-end flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            {isRunning
              ? <Loader2 size={14} className="animate-spin text-white" />
              : <Send size={14} className="text-white" />
            }
          </button>
        </div>

        {/* Presets */}
        {status === 'idle' && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {PRESETS.map(p => (
              <button
                key={p}
                onClick={() => { setQuery(p); runQuery(p) }}
                className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 border border-zinc-800 hover:border-zinc-700 rounded-md px-2 py-1 transition-colors"
              >
                <Sparkles size={8} />
                {p.length > 42 ? p.slice(0, 42) + '…' : p}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Feed */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto min-h-0 flex flex-col gap-2 pr-0.5"
      >
        <AnimatePresence mode="wait">
          {status === 'idle' && (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center h-full text-center py-10"
            >
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-3">
                <Sparkles size={20} className="text-indigo-400" />
              </div>
              <div className="text-sm font-semibold text-zinc-300 mb-1">Ready to investigate</div>
              <div className="text-xs text-zinc-600 max-w-[220px]">
                Ask about any metric drop or anomaly. Pick a preset above to see a live demo.
              </div>
            </motion.div>
          )}

          {(status === 'running' || status === 'done' || status === 'error') && (
            <motion.div
              key="feed"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col gap-2"
            >
              {/* Steps */}
              <div className="card p-3">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">
                  Investigation Pipeline
                </div>
                {STEPS.map((step, i) => (
                  <StepRow
                    key={step.label}
                    step={step}
                    state={
                      activeStep > i ? 'done'
                      : activeStep === i ? 'active'
                      : 'pending'
                    }
                  />
                ))}
              </div>

              {/* Results */}
              {result && !result.error && (
                <>
                  {/* Brief */}
                  {result.brief && (
                    <motion.div
                      className="card p-3"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4 }}
                    >
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">
                        Summary Brief
                      </div>
                      <p className="text-xs text-zinc-300 leading-relaxed">{result.brief}</p>
                    </motion.div>
                  )}

                  {/* Hypotheses */}
                  {result.hypotheses?.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold px-1">
                        Hypotheses ({result.hypotheses.length})
                      </div>
                      {result.hypotheses.map((h, i) => (
                        <HypothesisCard key={i} hyp={h} index={i} />
                      ))}
                    </div>
                  )}

                  {/* Actions */}
                  {result.actions?.length > 0 && (
                    <motion.div
                      className="card p-3"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4, delay: 0.2 }}
                    >
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">
                        Recommended Actions
                      </div>
                      <ul className="flex flex-col gap-1.5">
                        {result.actions.map((a, i) => (
                          <li key={i} className="flex items-start gap-2 text-xs text-zinc-300">
                            <ChevronRight size={12} className="text-indigo-400 flex-shrink-0 mt-0.5" />
                            {a}
                          </li>
                        ))}
                      </ul>
                    </motion.div>
                  )}
                </>
              )}

              {/* Error state */}
              {result?.error && (
                <motion.div
                  className="card border-l-2 border-l-rose-500 p-3 bg-rose-500/5"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <div className="flex items-center gap-2 text-rose-400 text-xs font-semibold mb-1">
                    <AlertCircle size={12} />
                    Investigation failed
                  </div>
                  <p className="text-[11px] text-zinc-400">{result.error}</p>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
