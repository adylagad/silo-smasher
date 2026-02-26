import { useState, useEffect } from 'react'
import { MessageSquare, Expand } from 'lucide-react'
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
    <div
      className="flex flex-col h-full"
      style={{
        background: 'radial-gradient(ellipse 90% 50% at 50% -8%, rgba(20,184,166,0.13) 0%, #070a09 58%)',
      }}
    >
      <Header apiStatus={apiStatus} onGuide={() => setGuideOpen(true)} />

      <div className="flex-1 min-h-0 relative overflow-hidden dot-bg">
        <ChartsFocusPanel />

        <div className="absolute inset-x-3 bottom-3 md:inset-x-auto md:right-4 md:bottom-4 md:w-[460px] z-20">
          {!chatOpen && (
            <form
              onSubmit={submitQuickQuery}
              className="rounded-2xl border border-white/[0.1] bg-[#090c0b]/95 backdrop-blur px-3 py-3 shadow-2xl"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-zinc-400 uppercase tracking-widest">
                  <MessageSquare size={12} className="text-teal-400" />
                  Analyst Chat
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSeedQuery('')
                    setChatOpen(true)
                  }}
                  className="h-6 px-2 rounded-md border border-white/[0.1] bg-white/[0.03] text-[10px] text-zinc-400 hover:text-zinc-200"
                >
                  Open
                </button>
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask why revenue changed this week..."
                  className="flex-1 h-10 rounded-xl border border-white/[0.09] bg-white/[0.03] px-3 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-teal-500/50"
                />
                <button
                  type="submit"
                  disabled={!chatInput.trim()}
                  className="h-10 px-3 rounded-xl bg-teal-500 text-black text-xs font-bold disabled:opacity-25 disabled:cursor-not-allowed"
                >
                  Zoom
                </button>
              </div>
            </form>
          )}
        </div>

        {chatOpen && (
          <div className="absolute inset-3 md:inset-auto md:right-4 md:bottom-4 md:w-[min(860px,86vw)] md:h-[82vh] z-30 rounded-2xl border border-white/[0.1] bg-[#070a09] shadow-2xl overflow-hidden">
            <div className="h-11 px-3 border-b border-white/[0.08] bg-white/[0.02] flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-zinc-400 uppercase tracking-widest">
                <Expand size={12} className="text-teal-400" />
                Expanded Diagnostic Chat
              </span>
              <button
                onClick={() => {
                  setSeedQuery('')
                  setChatOpen(false)
                }}
                className="h-7 px-3 rounded-lg border border-white/[0.1] bg-white/[0.03] text-[11px] text-zinc-300 hover:text-white"
              >
                Close
              </button>
            </div>
            <div className="relative h-[calc(100%-44px)]">
              <InvestigatePanel initialQuery={seedQuery} autoRunSignal={autoRunSignal} />
            </div>
          </div>
        )}

        {chatOpen && (
          <div className="hidden md:block absolute right-4 bottom-4 translate-y-[calc(100%+10px)] z-20">
            <button
              onClick={() => {
                setSeedQuery('')
                setChatOpen(false)
              }}
              className="rounded-lg border border-white/[0.1] bg-black/50 px-3 py-1 text-[10px] text-zinc-500 hover:text-zinc-300"
            >
              Return to chart-only view
            </button>
          </div>
        )}
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
