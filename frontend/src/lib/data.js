export const MRR_DATA = [
  { week: 'Jan 6',  mrr: 99200  },
  { week: 'Jan 13', mrr: 101800 },
  { week: 'Jan 20', mrr: 98700  },
  { week: 'Jan 27', mrr: 102400 },
  { week: 'Feb 3',  mrr: 104100 },
  { week: 'Feb 10', mrr: 100300 },
  { week: 'Feb 17', mrr: 87600  },
  { week: 'Feb 24', mrr: 84500  },
]

export const AVG_MRR = Math.round(
  MRR_DATA.slice(0, 6).reduce((s, d) => s + d.mrr, 0) / 6
)

export const STATS = [
  { label: 'Gross Revenue', value: '$84.5K',  color: 'text-white'       },
  { label: 'WoW Change',    value: '−15.2%',  color: 'text-rose-400'    },
  { label: 'Region',        value: 'UK / EU', color: 'text-amber-400'   },
  { label: 'Conversion',    value: '61.4%',   color: 'text-rose-400'    },
  { label: 'Return Rate',   value: '8.2%',    color: 'text-zinc-300'    },
  { label: 'Open Tickets',  value: '+34%',    color: 'text-amber-400'   },
]

export const STEPS = [
  { label: 'Generating hypotheses',       tool: 'OpenAI GPT-4o'  },
  { label: 'Querying knowledge graph',    tool: 'Neo4j GraphRAG' },
  { label: 'Finance variance analysis',   tool: 'Numeric'        },
  { label: 'External economic signals',   tool: 'Tavily Search'  },
  { label: 'Scoring & composing brief',   tool: 'Fastino Safety' },
]

export const STEP_DURATIONS = [900, 1100, 1000, 900, 750]

export const PRESETS = [
  'MRR is down 15% this week. Why?',
  'Sales dropped 20% in the UK. What is the root cause?',
  'Why did our Q3 revenue miss forecast by 12%?',
  'Customer churn spiked to 8% last month. What caused it?',
]

export const STATUS_META = {
  supported:    { label: '✓ Supported',    cls: 'text-emerald-400', bar: 'from-emerald-500 to-emerald-400', border: 'border-l-emerald-500', bg: 'bg-emerald-500/10' },
  rejected:     { label: '✗ Ruled Out',    cls: 'text-rose-400',    bar: 'from-rose-500 to-rose-400',      border: 'border-l-rose-500',    bg: 'bg-rose-500/10'    },
  inconclusive: { label: '? Inconclusive', cls: 'text-amber-400',   bar: 'from-amber-500 to-amber-400',    border: 'border-l-amber-500',   bg: 'bg-amber-500/10'   },
}
