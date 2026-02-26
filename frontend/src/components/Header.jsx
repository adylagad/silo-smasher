import { BookOpen, ExternalLink, Sparkles } from 'lucide-react'

export default function Header({ apiStatus, onGuide }) {
  const statusTone =
    apiStatus === 'live'
      ? 'border-emerald-400/35 text-emerald-300 bg-emerald-400/10'
      : apiStatus === 'error'
      ? 'border-rose-400/35 text-rose-300 bg-rose-400/10'
      : 'border-slate-400/30 text-slate-300 bg-slate-400/10'

  return (
    <header className="flex-shrink-0 h-14 px-4 md:px-6 border-b border-slate-500/20 bg-[#06101c]/70 backdrop-blur-xl relative z-20">
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-sky-400/40 to-transparent" />
      <div className="h-full max-w-[1320px] mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-2xl bg-gradient-to-br from-sky-300 to-cyan-400 text-slate-950 flex items-center justify-center font-black text-sm shadow-lg shadow-cyan-500/30">
            S
          </div>
          <div className="min-w-0">
            <div className="text-[15px] leading-none font-extrabold tracking-tight truncate">
              Silo <span className="gradient-text">Smasher</span>
            </div>
            <div className="hidden sm:flex items-center gap-1.5 text-[11px] text-slate-400 mt-1">
              <Sparkles size={11} className="text-cyan-300" />
              Find why metrics changed
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onGuide}
            className="h-8 px-3 rounded-xl border border-slate-400/25 bg-slate-900/45 text-slate-200 text-[11px] font-semibold hover:border-sky-300/40 hover:text-white transition-colors flex items-center gap-1.5"
          >
            <BookOpen size={12} />
            Guide
          </button>

          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="h-8 px-3 rounded-xl border border-slate-400/25 bg-slate-900/45 text-slate-200 text-[11px] font-semibold hover:border-sky-300/40 hover:text-white transition-colors flex items-center gap-1"
          >
            API
            <ExternalLink size={10} />
          </a>

          <div className={`h-8 px-3 rounded-xl border text-[11px] font-semibold inline-flex items-center gap-1.5 ${statusTone}`}>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                apiStatus === 'live' ? 'bg-emerald-300 shadow-[0_0_8px_rgba(110,231,183,0.85)]' :
                apiStatus === 'error' ? 'bg-rose-300' :
                'bg-slate-300'
              }`}
            />
            {apiStatus === 'live' ? 'API Live' : apiStatus === 'error' ? 'API Offline' : 'Checking'}
          </div>
        </div>
      </div>
    </header>
  )
}
