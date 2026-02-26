import { BookOpen, ExternalLink, Zap } from 'lucide-react'

export default function Header({ apiStatus, onGuide }) {
  return (
    <header className="flex-shrink-0 h-14 flex items-center justify-between px-5 border-b border-zinc-800 bg-[#0c0c0f] relative">
      {/* accent line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-indigo-500/40 to-transparent" />

      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center text-sm font-bold shadow-lg shadow-indigo-500/20">
          S
        </div>
        <div>
          <div className="text-sm font-bold leading-none">
            Silo <span className="gradient-text">Smasher</span>
          </div>
          <div className="text-[10px] text-zinc-600 mt-0.5 font-medium tracking-wide">
            Autonomous Root-Cause Investigator
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onGuide}
          className="flex items-center gap-1.5 h-7 px-3 rounded-md border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-medium hover:bg-indigo-500/20 transition-colors"
        >
          <BookOpen size={11} />
          How it Works
        </button>

        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 h-7 px-3 rounded-md border border-zinc-800 text-zinc-400 text-xs font-medium hover:border-zinc-700 hover:text-zinc-300 transition-colors"
        >
          API Docs
          <ExternalLink size={10} />
        </a>

        <div className={`flex items-center gap-2 h-7 px-3 rounded-full border text-xs font-medium transition-all duration-500
          ${apiStatus === 'live'
            ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-400'
            : apiStatus === 'error'
              ? 'border-rose-500/25 bg-rose-500/10 text-rose-400'
              : 'border-zinc-800 text-zinc-500'
          }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${
            apiStatus === 'live'
              ? 'bg-emerald-400 shadow-sm shadow-emerald-400'
              : apiStatus === 'error'
                ? 'bg-rose-400'
                : 'bg-zinc-600'
          }`} />
          {apiStatus === 'live' ? 'API Live' : apiStatus === 'error' ? 'Offline' : 'Connecting…'}
        </div>
      </div>
    </header>
  )
}
