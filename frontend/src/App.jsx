import { useState, useEffect } from 'react'
import Header from './components/Header'
import MetricPanel from './components/MetricPanel'
import InvestigatePanel from './components/InvestigatePanel'
import GuideModal from './components/GuideModal'

export default function App() {
  const [apiStatus, setApiStatus] = useState('checking')
  const [guideOpen, setGuideOpen] = useState(false)

  // Health-check polling
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

  // Auto-open guide on first visit
  useEffect(() => {
    if (!localStorage.getItem('silo_guide_seen')) {
      const t = setTimeout(() => setGuideOpen(true), 600)
      return () => clearTimeout(t)
    }
  }, [])

  const handleCloseGuide = () => {
    localStorage.setItem('silo_guide_seen', '1')
    setGuideOpen(false)
  }

  return (
    <div className="flex flex-col h-full">
      <Header
        apiStatus={apiStatus}
        onGuide={() => setGuideOpen(true)}
      />

      {/* Main layout */}
      <div className="flex-1 min-h-0 grid grid-cols-[340px_1fr] gap-3 p-3">
        {/* Left: metrics */}
        <div className="overflow-y-auto min-h-0">
          <MetricPanel />
        </div>

        {/* Right: investigation */}
        <div className="card p-4 min-h-0 flex flex-col">
          <div className="flex items-center gap-2 mb-3 flex-shrink-0">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Root-Cause Investigation
            </span>
            <div className="flex-1 h-px bg-zinc-800" />
          </div>
          <InvestigatePanel />
        </div>
      </div>

      <GuideModal open={guideOpen} onClose={handleCloseGuide} />
    </div>
  )
}
