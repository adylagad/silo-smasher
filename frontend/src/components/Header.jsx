import { BookOpen, ExternalLink } from 'lucide-react'

export default function Header({ apiStatus, onGuide }) {
  return (
    <header className="flex-shrink-0 h-12 flex items-center justify-between px-5 border-b border-white/[0.05] relative bg-black/20 backdrop-blur-sm">
      {/* bottom accent */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-indigo-500/30 to-transparent" />

      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-xs font-black shadow-lg shadow-indigo-500/25">
          S
        </div>
        <div className="leading-none">
          <span className="text-sm font-bold">Silo </span>
          <span className="text-sm font-bold gradient-text">Smasher</span>
        </div>
        <div className="hidden sm:block h-4 w-px bg-white/10 ml-1" />
        <span className="hidden sm:block text-[11px] text-zinc-600 font-medium">
          Autonomous Root-Cause Investigator
        </span>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={onGuide}
          className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg border border-white/[0.08] text-zinc-500 text-[11px] font-medium hover:text-zinc-300 hover:border-white/[0.14] transition-all"
        >
          <BookOpen size={11} />
          How it Works
        </button>

        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 h-7 px-2.5 rounded-lg border border-white/[0.08] text-zinc-500 text-[11px] font-medium hover:text-zinc-300 hover:border-white/[0.14] transition-all"
        >
          API Docs
          <ExternalLink size={9} />
        </a>

        {/* Status pill */}
        <div className={`flex items-center gap-1.5 h-7 px-2.5 rounded-lg border text-[11px] font-medium transition-all duration-500
          ${apiStatus === 'live'
            ? 'border-emerald-500/20 bg-emerald-500/8 text-emerald-400'
            : apiStatus === 'error'
              ? 'border-rose-500/20 bg-rose-500/8 text-rose-400'
              : 'border-white/[0.07] text-zinc-600'
          }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${
            apiStatus === 'live'
              ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50'
              : apiStatus === 'error'
                ? 'bg-rose-400'
                : 'bg-zinc-700'
          }`} />
          {apiStatus === 'live' ? 'Live' : apiStatus === 'error' ? 'Offline' : 'Connecting…'}
        </div>
      </div>
    </header>
  )
}
