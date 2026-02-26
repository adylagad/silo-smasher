import { useState, useEffect } from 'react'
import Header from './components/Header'
import MetricPanel from './components/MetricPanel'
import InvestigatePanel from './components/InvestigatePanel'
import GuideModal from './components/GuideModal'

export default function App() {
  const [apiStatus, setApiStatus] = useState('checking')
  const [guideOpen, setGuideOpen] = useState(false)

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

  return (
    <div
      className="flex flex-col h-full"
      style={{
        background: 'radial-gradient(ellipse 90% 50% at 50% -8%, rgba(20,184,166,0.13) 0%, #070a09 58%)',
      }}
    >
      <Header apiStatus={apiStatus} onGuide={() => setGuideOpen(true)} />

      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* Context sidebar */}
        <aside className="w-[268px] flex-shrink-0 overflow-y-auto border-r border-white/[0.05]">
          <MetricPanel />
        </aside>

        {/* Investigation canvas */}
        <div className="flex-1 min-w-0 relative overflow-hidden dot-bg">
          <InvestigatePanel />
        </div>
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
