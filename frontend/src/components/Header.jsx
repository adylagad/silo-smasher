import { BookOpen, ExternalLink } from 'lucide-react'

export default function Header({ apiStatus, onGuide }) {
  return (
    <header className="flex-shrink-0 h-11 flex items-center justify-between px-5 border-b border-white/[0.05] bg-black/30 backdrop-blur-sm relative z-10">
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-teal-500/25 to-transparent" />

      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-teal-500 to-cyan-400 flex items-center justify-center text-[11px] font-black text-black shadow-md shadow-teal-500/20">
          S
        </div>
        <span className="text-[13px] font-bold tracking-tight">
          Silo <span className="gradient-text">Smasher</span>
        </span>
        <div className="h-3.5 w-px bg-white/10 mx-1" />
        <span className="text-[11px] text-zinc-600 font-medium hidden sm:block">
          Root-Cause Investigator
        </span>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={onGuide}
          className="h-7 px-2.5 rounded-lg border border-white/[0.07] text-zinc-500 text-[11px] font-medium hover:text-zinc-300 hover:border-white/[0.13] transition-all flex items-center gap-1.5"
        >
          <BookOpen size={11} />
          How it Works
        </button>

        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="h-7 px-2.5 rounded-lg border border-white/[0.07] text-zinc-500 text-[11px] font-medium hover:text-zinc-300 hover:border-white/[0.13] transition-all flex items-center gap-1"
        >
          API Docs
          <ExternalLink size={9} />
        </a>

        {/* Status */}
        <div className={`h-7 px-2.5 rounded-lg border text-[11px] font-medium flex items-center gap-1.5 transition-all duration-500
          ${apiStatus === 'live'
            ? 'border-emerald-500/20 text-emerald-400'
            : apiStatus === 'error'
              ? 'border-rose-500/20 text-rose-400'
              : 'border-white/[0.06] text-zinc-600'
          }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${
            apiStatus === 'live'   ? 'bg-emerald-400 shadow-sm shadow-emerald-400/60' :
            apiStatus === 'error'  ? 'bg-rose-400' :
                                     'bg-zinc-700'
          }`} />
          {apiStatus === 'live' ? 'Live' : apiStatus === 'error' ? 'Offline' : 'Connecting'}
        </div>
      </div>
    </header>
  )
}
