import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles, Loader2, Search, RotateCcw,
  CheckCircle2, AlertCircle, HelpCircle, ArrowRight,
  Activity,
} from 'lucide-react'
import { STEPS, STEP_DURATIONS, PRESETS, STATUS_META } from '../lib/data'

// ── Tool badge ────────────────────────────────────────────────────────────────
const ToolBadge = ({ name }) => (
  <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[9px] font-medium bg-white/[0.04] text-zinc-500 border border-white/[0.07]">
    {name}
  </span>
)

// ── Horizontal step pipeline ──────────────────────────────────────────────────
const StepPipeline = ({ activeStep }) => (
  <div className="flex items-start px-8 py-4 border-b border-white/[0.05]">
    {STEPS.map((step, i) => {
      const state = activeStep > i ? 'done' : activeStep === i ? 'active' : 'pending'
      return (
        <div key={step.label} className="flex items-center flex-1 last:flex-none">
          <div className="flex flex-col items-center gap-1.5">
            <motion.div
              className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors duration-500
                ${state === 'done'
                  ? 'bg-sky-400 border-sky-300 shadow-lg shadow-sky-400/25'
                  : state === 'active'
                  ? 'bg-sky-400/12 border-sky-400/70'
                  : 'bg-white/[0.02] border-white/[0.07]'}`}
              animate={state === 'active'
                ? { boxShadow: ['0 0 0 0px rgba(56,189,248,0.4)', '0 0 0 7px rgba(56,189,248,0)', '0 0 0 0px rgba(56,189,248,0)'] }
                : {}}
              transition={{ duration: 1.6, repeat: Infinity }}
            >
              {state === 'done'
                ? <CheckCircle2 size={14} className="text-black" />
                : state === 'active'
                ? <Loader2 size={12} className="text-sky-300 animate-spin" />
                : <span className="text-[9px] font-bold text-zinc-700">{i + 1}</span>
              }
            </motion.div>
            <span className={`text-[9px] font-medium text-center leading-tight w-16
              ${state === 'pending' ? 'text-zinc-700'
                : state === 'active' ? 'text-sky-200 font-semibold'
                : 'text-zinc-500'}`}>
              {step.short}
            </span>
            {state !== 'pending' && (
              <span className="text-[8px] text-zinc-700 text-center w-16 leading-tight truncate">{step.tool}</span>
            )}
          </div>
          {i < STEPS.length - 1 && (
            <motion.div
              className="flex-1 h-px mx-1.5 mb-[26px]"
              style={{ background: activeStep > i ? 'rgba(56,189,248,0.4)' : 'rgba(255,255,255,0.05)' }}
            />
          )}
        </div>
      )
    })}
  </div>
)

// ── Hypothesis card ───────────────────────────────────────────────────────────
const HypothesisCard = ({ hyp, index }) => {
  const meta = STATUS_META[hyp.status] ?? STATUS_META.inconclusive
  const Icon = hyp.status === 'supported' ? CheckCircle2 : hyp.status === 'rejected' ? AlertCircle : HelpCircle

  return (
    <motion.div
      className={`relative rounded-2xl border ${meta.border} overflow-hidden`}
      style={{ background: 'rgba(255,255,255,0.018)' }}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.09, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      <div className={`absolute inset-0 ${meta.bg} pointer-events-none`} />
      <div className="relative flex gap-4 p-4 items-start">
        {/* Confidence */}
        <div className="shrink-0 text-center w-12 pt-0.5">
          <div className={`text-[2rem] font-black leading-none ${meta.cls} tabular-nums`}>
            {hyp.confidence}
          </div>
          <div className={`text-[9px] font-bold ${meta.cls} opacity-50`}>%</div>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-zinc-200 leading-relaxed mb-2.5">{hyp.title}</p>
          <div className="h-1 bg-white/[0.05] rounded-full overflow-hidden mb-2.5">
            <motion.div
              className={`h-full rounded-full bg-gradient-to-r ${meta.bar}`}
              initial={{ width: 0 }}
              animate={{ width: `${hyp.confidence}%` }}
              transition={{ duration: 0.85, delay: index * 0.09 + 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
            />
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 flex-wrap">
              {hyp.sources?.map(s => <ToolBadge key={s} name={s} />)}
            </div>
            <span className={`flex items-center gap-1 text-[10px] font-semibold ${meta.cls} shrink-0`}>
              <Icon size={10} />
              {meta.label}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ── Thinking orb ──────────────────────────────────────────────────────────────
const ThinkingOrb = ({ currentStep }) => (
  <div className="flex flex-col items-center gap-5">
    <div className="relative w-16 h-16">
      {[0, 0.55, 1.1].map((delay, i) => (
        <motion.div
          key={i}
          className="absolute inset-0 rounded-full border border-sky-400/20"
          animate={{ scale: [1, 2.8], opacity: [0.5, 0] }}
          transition={{ duration: 2.2, delay, repeat: Infinity, ease: 'easeOut' }}
        />
      ))}
      <div className="absolute inset-0 rounded-full bg-sky-400/12 border border-sky-400/35 flex items-center justify-center">
        <Activity size={20} className="text-sky-300" />
      </div>
    </div>
    <div className="text-sm text-zinc-500 text-center">
      <span className="text-zinc-400 font-medium">
        {STEPS[Math.min(currentStep, STEPS.length - 1)]?.label ?? 'Analyzing'}
      </span>
      <motion.span
        animate={{ opacity: [1, 0.2, 1] }}
        transition={{ duration: 1.4, repeat: Infinity }}
      >…</motion.span>
    </div>
    <p className="text-xs text-zinc-600 text-center max-w-xs leading-relaxed">
      Checking SQL, graph, and market signals.
    </p>
  </div>
)

const normalizeDiagnosticResult = (payload) => {
  const providerFailure =
    payload &&
    payload.error === 'all_providers_failed' &&
    payload.fallback_response &&
    typeof payload.fallback_response === 'object'

  const base = providerFailure ? payload.fallback_response : payload
  if (!base || typeof base !== 'object') return payload

  const rawHypotheses = Array.isArray(base.hypotheses) ? base.hypotheses : []
  const hypotheses = rawHypotheses.map((item) => {
    const source = item && typeof item === 'object' ? item : {}
    const rawConfidence = source.confidence
    const confidencePct = typeof rawConfidence === 'number'
      ? (rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence)
      : 0
    const normalizedStatus = ['supported', 'rejected', 'inconclusive'].includes(source.status)
      ? source.status
      : 'inconclusive'
    const evidence = Array.isArray(source.evidence)
      ? source.evidence.filter((v) => typeof v === 'string')
      : []
    return {
      title: source.title || source.name || 'Hypothesis',
      status: normalizedStatus,
      confidence: Math.max(0, Math.min(100, Math.round(confidencePct))),
      sources: evidence.slice(0, 3),
    }
  })

  const actions = Array.isArray(base.actions)
    ? base.actions.filter((value) => typeof value === 'string')
    : Array.isArray(base.recommended_next_queries)
      ? base.recommended_next_queries.filter((value) => typeof value === 'string')
      : []

  const briefCandidates = [
    base.brief,
    base.metric_summary,
    base.most_likely_root_cause,
  ]
  const brief = briefCandidates.find((value) => typeof value === 'string' && value.trim()) ||
    'Investigation completed in fallback mode with available local context.'

  return {
    ...base,
    brief,
    hypotheses,
    actions,
    degraded_mode: providerFailure || Boolean(base.degraded_mode),
    provider_attempts: providerFailure ? payload.attempts : base.provider_attempts,
  }
}

const EvidencePanel = ({ toolOutputs }) => {
  if (!toolOutputs || typeof toolOutputs !== 'object') return null

  const sqlStatusRows = Array.isArray(toolOutputs?.sql_status?.rows)
    ? toolOutputs.sql_status.rows
    : []
  const sqlRevenueRows = Array.isArray(toolOutputs?.sql_revenue?.rows)
    ? toolOutputs.sql_revenue.rows
    : []
  const internalRows = Array.isArray(toolOutputs?.internal_signals?.results)
    ? toolOutputs.internal_signals.results
    : []

  if (!sqlStatusRows.length && !sqlRevenueRows.length && !internalRows.length) return null

  const statusMap = {}
  for (const row of sqlStatusRows) {
    if (!row || typeof row !== 'object') continue
    const key = String(row.status || '').toLowerCase()
    if (!key) continue
    statusMap[key] = row.event_count ?? row.count ?? 0
  }
  const topRegion = sqlRevenueRows[0] && typeof sqlRevenueRows[0] === 'object' ? sqlRevenueRows[0] : null

  return (
    <motion.div
      className="rounded-2xl border border-white/[0.07] bg-white/[0.018] p-5"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.12 }}
    >
      <div className="flex items-center gap-2 mb-3">
        <div className="w-1 h-4 rounded-full bg-sky-300" />
        <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
          Evidence
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-3">
          <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">SQL</div>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {['purchased', 'returned', 'carted'].map((key) => (
              <span key={key} className="text-[10px] px-2 py-1 rounded-md border border-white/[0.08] bg-white/[0.03] text-zinc-300">
                {key}: {statusMap[key] ?? 0}
              </span>
            ))}
          </div>
          {topRegion && (
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Top region: <span className="text-zinc-200">{String(topRegion.country_code || 'n/a')}</span>{' '}
              ({topRegion.purchased_revenue ?? 0} revenue)
            </p>
          )}
        </div>

        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-3">
          <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">Internal Signals</div>
          <div className="flex flex-col gap-2">
            {internalRows.slice(0, 2).map((item) => (
              <div key={item.message_id || item.timestamp} className="text-[11px] text-zinc-300 leading-relaxed">
                <div className="text-zinc-500 text-[10px]">
                  {item.channel || 'channel'} · {item.timestamp || 'time'}
                </div>
                <div className="line-clamp-2">{item.text || 'No message text'}</div>
              </div>
            ))}
            {!internalRows.length && (
              <div className="text-[11px] text-zinc-500">No internal matches found.</div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function InvestigatePanel({ initialQuery = '', autoRunSignal = 0 }) {
  const [query, setQuery]           = useState('')
  const [status, setStatus]         = useState('idle')
  const [activeStep, setActiveStep] = useState(-1)
  const [result, setResult]         = useState(null)
  const feedRef                     = useRef(null)
  const inputRef                    = useRef(null)
  const lastAutoRunSignalRef        = useRef(autoRunSignal)

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight
  }, [activeStep, result])

  const runQuery = useCallback(async (q) => {
    const text = (q ?? query).trim()
    if (!text || status === 'running') return

    setQuery(text)
    setStatus('running')
    setActiveStep(0)
    setResult(null)

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
      const normalized = normalizeDiagnosticResult(data)
      setResult(normalized)
      setActiveStep(STEPS.length)
      setStatus(normalized?.error ? 'error' : 'done')
    } catch {
      setResult({ error: 'Could not reach the API. Is the backend running?' })
      setActiveStep(STEPS.length)
      setStatus('error')
    }
  }, [query, status])

  useEffect(() => {
    if (!initialQuery?.trim()) return
    setQuery(initialQuery)
  }, [initialQuery])

  useEffect(() => {
    if (!autoRunSignal || autoRunSignal === lastAutoRunSignalRef.current) return
    lastAutoRunSignalRef.current = autoRunSignal
    if (initialQuery?.trim()) runQuery(initialQuery)
  }, [autoRunSignal, initialQuery, runQuery])

  const reset = () => {
    setStatus('idle')
    setQuery('')
    setResult(null)
    setActiveStep(-1)
    setTimeout(() => inputRef.current?.focus(), 150)
  }

  return (
    <div className="absolute inset-0 flex flex-col">
      <AnimatePresence mode="wait">

        {/* ══ IDLE — centered command interface ══ */}
        {status === 'idle' && (
          <motion.div
            key="idle"
            className="flex-1 flex flex-col items-center justify-center px-10 py-16"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -14 }}
            transition={{ duration: 0.28 }}
          >
            {/* Eyebrow */}
            <motion.div
              className="flex items-center gap-2 mb-6"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 }}
            >
              <div className="w-7 h-7 rounded-xl bg-sky-400/12 border border-sky-400/22 flex items-center justify-center">
                <Activity size={13} className="text-sky-300" />
              </div>
              <span className="text-[10px] font-semibold text-sky-300/70 tracking-widest uppercase">
                Diagnostic Agent
              </span>
            </motion.div>

            {/* Headline */}
            <motion.h1
              className="text-[2.1rem] font-black text-white text-center tracking-tight leading-tight mb-3"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12 }}
            >
              What changed?
            </motion.h1>
            <motion.p
              className="text-[13px] text-zinc-500 text-center mb-9 max-w-[420px] leading-relaxed"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.16 }}
            >
              Type your question. Get a short answer with evidence.
            </motion.p>

            {/* Command input */}
            <motion.div
              className="w-full max-w-2xl"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <div className="input-glow relative rounded-2xl border border-white/[0.08] bg-white/[0.035] transition-all duration-300">
                <div className="flex items-start gap-3 p-4 pb-2">
                  <Search size={14} className="text-zinc-600 mt-0.5 shrink-0" />
                  <textarea
                    ref={inputRef}
                    rows={2}
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        runQuery()
                      }
                    }}
                    placeholder="MRR is down 15% this week. Why?"
                    className="flex-1 bg-transparent resize-none text-sm text-zinc-200 placeholder:text-zinc-600/60 focus:outline-none leading-relaxed"
                    autoFocus
                  />
                </div>
                <div className="flex items-center justify-between px-4 pb-3 mt-0.5">
                  <div className="flex items-center gap-2 text-[10px] text-zinc-700">
                    <kbd className="px-1.5 py-0.5 rounded border border-white/[0.08] bg-white/[0.04] font-mono">↵</kbd>
                    <span>run</span>
                    <span className="text-zinc-800">·</span>
                    <kbd className="px-1.5 py-0.5 rounded border border-white/[0.08] bg-white/[0.04] font-mono text-[9px]">⇧↵</kbd>
                    <span>newline</span>
                  </div>
                  <button
                    onClick={() => runQuery()}
                    disabled={!query.trim()}
                    className="flex items-center gap-1.5 h-7 px-3.5 rounded-xl bg-sky-400 hover:bg-sky-400 disabled:opacity-25 disabled:cursor-not-allowed text-black text-xs font-bold transition-all duration-200 shadow-lg shadow-sky-400/20"
                  >
                    Analyze
                    <ArrowRight size={11} />
                  </button>
                </div>
              </div>
            </motion.div>

            {/* Presets */}
            <motion.div
              className="flex flex-wrap justify-center gap-2 mt-5 max-w-2xl"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
            >
              <span className="text-[11px] text-zinc-700 self-center mr-1">Try:</span>
              {PRESETS.map(p => (
                <button
                  key={p}
                  onClick={() => { setQuery(p); runQuery(p) }}
                  className="flex items-center gap-1.5 text-[11px] text-zinc-500 hover:text-zinc-200 bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] hover:border-white/[0.13] rounded-full px-3 py-1.5 transition-all duration-200"
                >
                  <Sparkles size={9} className="text-sky-300/50" />
                  {p.length > 50 ? p.slice(0, 50) + '…' : p}
                </button>
              ))}
            </motion.div>
          </motion.div>
        )}

        {/* ══ RUNNING / DONE ══ */}
        {(status === 'running' || status === 'done' || status === 'error') && (
          <motion.div
            key="active"
            className="flex-1 flex flex-col min-h-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.28 }}
          >
            {/* Query bar */}
            <div className="flex-shrink-0 px-6 pt-4">
              <div className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.025] px-4 py-2.5">
                <Search size={13} className="text-zinc-600 shrink-0" />
                <p className="flex-1 text-sm text-zinc-400 leading-snug line-clamp-1">{query}</p>
                {(status === 'done' || status === 'error') && (
                  <button
                    onClick={reset}
                    className="flex items-center gap-1.5 text-[11px] text-zinc-500 hover:text-zinc-300 bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.07] rounded-lg px-2.5 py-1 transition-all shrink-0"
                  >
                    <RotateCcw size={10} />
                    New
                  </button>
                )}
              </div>
            </div>

            {/* Step pipeline */}
            <StepPipeline activeStep={activeStep} />

            {/* Feed */}
            <div className="flex-1 min-h-0 overflow-y-auto px-6 pb-6 pt-4" ref={feedRef}>

              {/* Thinking */}
              {status === 'running' && (
                <div className="flex items-center justify-center h-full">
                  <ThinkingOrb currentStep={activeStep} />
                </div>
              )}

              {/* Results */}
              {(status === 'done' || status === 'error') && (
                <div className="flex flex-col gap-4">

                  {result?.degraded_mode && (
                    <motion.div
                      className="rounded-xl border border-amber-400/25 bg-amber-500/8 px-4 py-3"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <p className="text-xs text-amber-200/85">
                        Provider unavailable. Showing fallback results.
                      </p>
                    </motion.div>
                  )}

                  {/* Error */}
                  {result?.error && (
                    <motion.div
                      className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <div className="flex items-center gap-2 text-rose-400 font-semibold text-sm mb-2">
                        <AlertCircle size={14} />
                        Investigation failed
                      </div>
                      <p className="text-sm text-zinc-400">{result.error}</p>
                    </motion.div>
                  )}

                  {/* Brief */}
                  {result?.brief && (
                    <motion.div
                      className="rounded-2xl border border-sky-400/18 overflow-hidden"
                      style={{ background: 'linear-gradient(135deg, rgba(56,189,248,0.07) 0%, rgba(6,182,212,0.04) 100%)' }}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4 }}
                    >
                      <div className="flex items-center gap-2 px-5 pt-4 pb-3 border-b border-sky-400/10">
                        <div className="w-1 h-4 rounded-full bg-gradient-to-b from-sky-300 to-cyan-500" />
                        <span className="text-[10px] font-semibold text-sky-200/70 uppercase tracking-widest">
                          Summary
                        </span>
                      </div>
                      <p className="px-5 py-4 text-sm text-zinc-200 leading-relaxed">{result.brief}</p>
                    </motion.div>
                  )}

                  {/* Hypotheses */}
                  {result?.hypotheses?.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
                          Findings
                        </span>
                        <span className="text-[10px] text-zinc-700 bg-white/[0.04] border border-white/[0.07] rounded-full px-2 py-0.5">
                          {result.hypotheses.length}
                        </span>
                        <div className="flex-1 h-px bg-white/[0.05]" />
                      </div>
                      <div className="flex flex-col gap-2.5">
                        {result.hypotheses.map((h, i) => (
                          <HypothesisCard key={i} hyp={h} index={i} />
                        ))}
                      </div>
                    </div>
                  )}

                  <EvidencePanel toolOutputs={result?.tool_outputs} />

                  {/* Actions */}
                  {result?.actions?.length > 0 && (
                    <motion.div
                      className="rounded-2xl border border-white/[0.07] bg-white/[0.018] p-5"
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.4, delay: 0.18 }}
                    >
                      <div className="flex items-center gap-2 mb-4">
                        <div className="w-1 h-4 rounded-full bg-emerald-400" />
                        <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
                          Next Steps
                        </span>
                      </div>
                      <ol className="flex flex-col gap-3">
                        {result.actions.map((a, i) => (
                          <motion.li
                            key={i}
                            className="flex items-start gap-3 text-sm text-zinc-300"
                            initial={{ opacity: 0, x: 6 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.28, delay: i * 0.06 + 0.28 }}
                          >
                            <span className="w-5 h-5 rounded-full bg-white/[0.04] border border-white/[0.08] text-[9px] font-bold text-zinc-600 flex items-center justify-center shrink-0 mt-0.5 tabular-nums">
                              {i + 1}
                            </span>
                            {a}
                          </motion.li>
                        ))}
                      </ol>
                    </motion.div>
                  )}

                </div>
              )}
            </div>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  )
}
