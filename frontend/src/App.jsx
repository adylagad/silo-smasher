import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { MessageSquare, Expand, ArrowUpRight } from 'lucide-react'
import Header from './components/Header'
import ChartsFocusPanel from './components/ChartsFocusPanel'
import InvestigatePanel from './components/InvestigatePanel'
import GuideModal from './components/GuideModal'

export default function App() {
  const [apiStatus, setApiStatus] = useState('checking')
  const [guideOpen, setGuideOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [seedQuery, setSeedQuery] = useState('')
  const [autoRunSignal, setAutoRunSignal] = useState(0)

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('/health', { signal: AbortSignal.timeout(4000) })
        setApiStatus(res.ok ? 'live' : 'error')
      } catch {
        setApiStatus('error')
      }
    }
    check()
    const id = setInterval(check, 30_000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!localStorage.getItem('silo_guide_seen')) {
      const t = setTimeout(() => setGuideOpen(true), 800)
      return () => clearTimeout(t)
    }
  }, [])

  const submitQuickQuery = (event) => {
    event.preventDefault()
    const text = chatInput.trim()
    if (!text) return
    setSeedQuery(text)
    setAutoRunSignal((n) => n + 1)
    setChatInput('')
    setChatOpen(true)
  }

  return (
    <div className="flex flex-col h-full relative overflow-hidden">
      <div className="floating-blob absolute -top-20 right-[12%] w-72 h-72 rounded-full bg-cyan-400/12 pointer-events-none" style={{ animationDelay: '1.7s' }} />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.05),transparent_46%)] pointer-events-none" />

      <Header apiStatus={apiStatus} onGuide={() => setGuideOpen(true)} />

      <div className="flex-1 min-h-0 relative overflow-hidden dot-bg">
        <ChartsFocusPanel />

        <div className="absolute inset-x-3 bottom-3 md:inset-x-auto md:right-5 md:bottom-5 md:w-[470px] z-20">
          <AnimatePresence mode="wait">
            {!chatOpen && (
              <motion.form
                key="chat-dock"
                onSubmit={submitQuickQuery}
                className="card panel-hover rounded-2xl px-3 py-3"
                initial={{ opacity: 0, y: 18, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 14, scale: 0.98 }}
                transition={{ duration: 0.24, ease: [0.2, 0.8, 0.2, 1] }}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-300 uppercase tracking-widest">
                    <MessageSquare size={12} className="text-cyan-300" />
                    Chat
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setSeedQuery('')
                      setChatOpen(true)
                    }}
                    className="h-7 px-2.5 rounded-lg border border-slate-400/25 bg-slate-900/40 text-[10px] font-semibold text-slate-200 hover:text-white"
                  >
                    Open
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask: why did revenue drop?"
                    className="flex-1 h-10 rounded-xl border border-slate-400/25 bg-[#0a1625]/85 px-3 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-sky-300/50"
                  />
                  <button
                    type="submit"
                    disabled={!chatInput.trim()}
                    className="h-10 px-3.5 rounded-xl bg-gradient-to-r from-sky-400 to-cyan-300 text-slate-950 text-xs font-extrabold disabled:opacity-30 disabled:cursor-not-allowed inline-flex items-center gap-1"
                  >
                    Zoom
                    <ArrowUpRight size={12} />
                  </button>
                </div>
              </motion.form>
            )}
          </AnimatePresence>
        </div>

        <AnimatePresence>
          {chatOpen && (
            <motion.div
              className="absolute inset-3 md:inset-auto md:right-5 md:bottom-5 md:w-[min(900px,88vw)] md:h-[84vh] z-30 rounded-2xl border border-slate-300/20 bg-[#050b14]/94 backdrop-blur-xl shadow-[0_35px_90px_rgba(3,7,18,0.7)] overflow-hidden"
              initial={{ opacity: 0, y: 22, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 18, scale: 0.98 }}
              transition={{ duration: 0.26, ease: [0.2, 0.8, 0.2, 1] }}
            >
              <div className="h-12 px-4 border-b border-slate-400/20 bg-slate-900/40 flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-300 uppercase tracking-widest">
                  <Expand size={12} className="text-sky-300" />
                  Diagnostic Chat
                </span>
                <button
                  onClick={() => {
                    setSeedQuery('')
                    setChatOpen(false)
                  }}
                  className="h-7 px-3 rounded-lg border border-slate-400/25 bg-slate-900/50 text-[11px] text-slate-200 hover:text-white"
                >
                  Close
                </button>
              </div>
              <div className="relative h-[calc(100%-48px)]">
                <InvestigatePanel initialQuery={seedQuery} autoRunSignal={autoRunSignal} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <GuideModal
        open={guideOpen}
        onClose={() => {
          localStorage.setItem('silo_guide_seen', '1')
          setGuideOpen(false)
        }}
      />
    </div>
  )
}
