export const METRIC_SERIES = [
  { week: 'Nov 18', mrr: 106800, conversion: 67.4, churn: 5.6, tickets: 42, returns: 5.0, eu: 41700, us: 39600, apac: 25500 },
  { week: 'Nov 25', mrr: 108200, conversion: 68.1, churn: 5.2, tickets: 41, returns: 4.8, eu: 42100, us: 40100, apac: 26000 },
  { week: 'Dec 2', mrr: 109100, conversion: 68.3, churn: 5.0, tickets: 39, returns: 4.9, eu: 42600, us: 40400, apac: 26100 },
  { week: 'Dec 9', mrr: 110200, conversion: 68.6, churn: 4.9, tickets: 37, returns: 4.7, eu: 43100, us: 40600, apac: 26500 },
  { week: 'Dec 16', mrr: 107900, conversion: 67.8, churn: 5.4, tickets: 45, returns: 5.3, eu: 41600, us: 40300, apac: 26000 },
  { week: 'Dec 23', mrr: 105700, conversion: 66.9, churn: 5.8, tickets: 48, returns: 5.7, eu: 40500, us: 39900, apac: 25300 },
  { week: 'Dec 30', mrr: 103400, conversion: 66.2, churn: 6.0, tickets: 50, returns: 6.0, eu: 39700, us: 39100, apac: 24600 },
  { week: 'Jan 6', mrr: 99200, conversion: 65.4, churn: 6.3, tickets: 56, returns: 6.4, eu: 38000, us: 37200, apac: 24000 },
  { week: 'Jan 13', mrr: 101800, conversion: 65.9, churn: 6.1, tickets: 53, returns: 6.1, eu: 38800, us: 37700, apac: 25300 },
  { week: 'Jan 20', mrr: 98700, conversion: 64.7, churn: 6.6, tickets: 61, returns: 6.9, eu: 37100, us: 37000, apac: 24600 },
  { week: 'Jan 27', mrr: 102400, conversion: 65.8, churn: 6.2, tickets: 55, returns: 6.3, eu: 38900, us: 37700, apac: 25800 },
  { week: 'Feb 3', mrr: 104100, conversion: 66.2, churn: 6.1, tickets: 54, returns: 6.2, eu: 39500, us: 38300, apac: 26300 },
  { week: 'Feb 10', mrr: 100300, conversion: 64.5, churn: 6.8, tickets: 62, returns: 7.0, eu: 36400, us: 37800, apac: 26100 },
  { week: 'Feb 17', mrr: 87600, conversion: 62.0, churn: 7.8, tickets: 72, returns: 8.1, eu: 27400, us: 34000, apac: 26200 },
  { week: 'Feb 24', mrr: 84500, conversion: 61.4, churn: 8.0, tickets: 75, returns: 8.2, eu: 25100, us: 33200, apac: 26200 },
  { week: 'Mar 3', mrr: 86200, conversion: 61.9, churn: 7.9, tickets: 73, returns: 8.0, eu: 25800, us: 33800, apac: 26600 },
]

export const MRR_DATA = METRIC_SERIES.map(({ week, mrr }) => ({ week, mrr }))

const BASELINE_WINDOW = METRIC_SERIES.slice(0, 12)
export const AVG_MRR = Math.round(
  BASELINE_WINDOW.reduce((sum, row) => sum + row.mrr, 0) / BASELINE_WINDOW.length
)

const latest = METRIC_SERIES[METRIC_SERIES.length - 1]
const previous = METRIC_SERIES[METRIC_SERIES.length - 2]
const baselineMrr = BASELINE_WINDOW.reduce((sum, row) => sum + row.mrr, 0) / BASELINE_WINDOW.length
const wowDelta = ((latest.mrr - previous.mrr) / previous.mrr) * 100
const baselineDelta = latest.mrr - baselineMrr
const euShare = (latest.eu / latest.mrr) * 100

const trendClass = (value, inverse = false) => {
  if (value === 0) return 'text-zinc-300'
  if (inverse) return value < 0 ? 'text-emerald-400' : 'text-rose-400'
  return value < 0 ? 'text-rose-400' : 'text-emerald-400'
}

export const STATS = [
  {
    label: 'WoW Change',
    value: `${wowDelta < 0 ? '−' : '+'}${Math.abs(wowDelta).toFixed(1)}%`,
    color: trendClass(wowDelta),
  },
  {
    label: 'Baseline Delta',
    value: `${baselineDelta < 0 ? '−' : '+'}$${(Math.abs(baselineDelta) / 1000).toFixed(1)}K`,
    color: trendClass(baselineDelta),
  },
  {
    label: 'Conversion',
    value: `${latest.conversion.toFixed(1)}%`,
    color: trendClass(latest.conversion - previous.conversion),
  },
  {
    label: 'Churn',
    value: `${latest.churn.toFixed(1)}%`,
    color: trendClass(latest.churn - previous.churn, true),
  },
  {
    label: 'Support Tickets',
    value: `${latest.tickets}`,
    color: trendClass(latest.tickets - previous.tickets, true),
  },
  {
    label: 'EU Share',
    value: `${euShare.toFixed(1)}%`,
    color: trendClass(latest.eu - previous.eu),
  },
]

export const STEPS = [
  { label: 'Testing hypotheses', short: 'Hypothesis', tool: 'OpenAI' },
  { label: 'Checking graph links', short: 'Graph', tool: 'Neo4j' },
  { label: 'Checking finance signal', short: 'Finance', tool: 'Numeric' },
  { label: 'Checking external events', short: 'External', tool: 'Tavily' },
  { label: 'Scoring and summary', short: 'Summary', tool: 'Fastino' },
]

export const STEP_DURATIONS = [900, 1100, 1000, 900, 750]

export const PRESETS = [
  'MRR down 15% this week. Why?',
  'UK sales down 20%. Root cause?',
  'Q3 revenue missed by 12%. Why?',
  'Churn jumped to 8%. What changed?',
]

export const STATUS_META = {
  supported:    { label: 'Supported',    cls: 'text-emerald-400', bar: 'from-emerald-500 to-emerald-400', border: 'border-emerald-500/25', bg: 'bg-emerald-500/5'  },
  rejected:     { label: 'Ruled Out',    cls: 'text-rose-400',    bar: 'from-rose-500 to-rose-400',      border: 'border-rose-500/25',    bg: 'bg-rose-500/5'     },
  inconclusive: { label: 'Inconclusive', cls: 'text-amber-400',   bar: 'from-amber-500 to-amber-400',    border: 'border-amber-500/25',   bg: 'bg-amber-500/5'    },
}
