export const METRIC_SERIES = [
  { week: '08:30', error_rate: 0.3, p95_latency_ms: 210, five_xx: 9, oncall_pages: 0, api_errors: 6, db_errors: 2, dependency_errors: 1 },
  { week: '08:35', error_rate: 0.4, p95_latency_ms: 230, five_xx: 12, oncall_pages: 0, api_errors: 8, db_errors: 2, dependency_errors: 2 },
  { week: '08:40', error_rate: 0.5, p95_latency_ms: 240, five_xx: 15, oncall_pages: 0, api_errors: 10, db_errors: 3, dependency_errors: 2 },
  { week: '08:45', error_rate: 0.6, p95_latency_ms: 255, five_xx: 18, oncall_pages: 1, api_errors: 12, db_errors: 3, dependency_errors: 3 },
  { week: '08:50', error_rate: 0.5, p95_latency_ms: 245, five_xx: 16, oncall_pages: 0, api_errors: 11, db_errors: 3, dependency_errors: 2 },
  { week: '08:55', error_rate: 0.7, p95_latency_ms: 260, five_xx: 20, oncall_pages: 1, api_errors: 14, db_errors: 3, dependency_errors: 3 },
  { week: '09:00', error_rate: 0.8, p95_latency_ms: 285, five_xx: 24, oncall_pages: 1, api_errors: 17, db_errors: 4, dependency_errors: 3 },
  { week: '09:05', error_rate: 1.2, p95_latency_ms: 340, five_xx: 34, oncall_pages: 2, api_errors: 25, db_errors: 5, dependency_errors: 4 },
  { week: '09:10', error_rate: 3.8, p95_latency_ms: 610, five_xx: 109, oncall_pages: 3, api_errors: 84, db_errors: 14, dependency_errors: 11 },
  { week: '09:15', error_rate: 11.6, p95_latency_ms: 1120, five_xx: 332, oncall_pages: 6, api_errors: 276, db_errors: 33, dependency_errors: 23 },
  { week: '09:20', error_rate: 18.7, p95_latency_ms: 1380, five_xx: 538, oncall_pages: 8, api_errors: 468, db_errors: 41, dependency_errors: 29 },
  { week: '09:25', error_rate: 14.9, p95_latency_ms: 1260, five_xx: 427, oncall_pages: 7, api_errors: 361, db_errors: 39, dependency_errors: 27 },
  { week: '09:30', error_rate: 8.4, p95_latency_ms: 820, five_xx: 241, oncall_pages: 5, api_errors: 197, db_errors: 27, dependency_errors: 17 },
  { week: '09:35', error_rate: 4.2, p95_latency_ms: 520, five_xx: 121, oncall_pages: 3, api_errors: 92, db_errors: 18, dependency_errors: 11 },
  { week: '09:40', error_rate: 2.1, p95_latency_ms: 380, five_xx: 61, oncall_pages: 2, api_errors: 44, db_errors: 11, dependency_errors: 6 },
  { week: '09:45', error_rate: 1.0, p95_latency_ms: 290, five_xx: 30, oncall_pages: 1, api_errors: 20, db_errors: 6, dependency_errors: 4 },
]

const BASELINE_WINDOW = METRIC_SERIES.slice(0, 8)
const latest = METRIC_SERIES[METRIC_SERIES.length - 1]
const previous = METRIC_SERIES[METRIC_SERIES.length - 2]

const baselineErrorRate =
  BASELINE_WINDOW.reduce((sum, row) => sum + row.error_rate, 0) / BASELINE_WINDOW.length
const baselineLatency =
  BASELINE_WINDOW.reduce((sum, row) => sum + row.p95_latency_ms, 0) / BASELINE_WINDOW.length
const peakErrors = Math.max(...METRIC_SERIES.map((row) => row.five_xx))
const apiShare =
  ((latest.api_errors / (latest.api_errors + latest.db_errors + latest.dependency_errors)) * 100) || 0

const trendClass = (value, inverse = false) => {
  if (value === 0) return 'text-zinc-300'
  if (inverse) return value < 0 ? 'text-emerald-400' : 'text-rose-400'
  return value < 0 ? 'text-rose-400' : 'text-emerald-400'
}

export const STATS = [
  {
    label: 'Error Rate',
    value: `${latest.error_rate.toFixed(1)}%`,
    color: trendClass(latest.error_rate - previous.error_rate, true),
  },
  {
    label: 'p95 Latency',
    value: `${Math.round(latest.p95_latency_ms)} ms`,
    color: trendClass(latest.p95_latency_ms - previous.p95_latency_ms, true),
  },
  {
    label: '500/min',
    value: `${latest.five_xx}`,
    color: trendClass(latest.five_xx - previous.five_xx, true),
  },
  {
    label: 'On-call Pages',
    value: `${latest.oncall_pages}`,
    color: trendClass(latest.oncall_pages - previous.oncall_pages, true),
  },
  {
    label: 'Peak 500/min',
    value: `${peakErrors}`,
    color: 'text-rose-300',
  },
  {
    label: 'API Error Share',
    value: `${apiShare.toFixed(1)}%`,
    color: trendClass(apiShare),
  },
]

export const AVG_MRR = Math.round(baselineErrorRate * 100) / 100
export const MRR_DATA = METRIC_SERIES.map(({ week, error_rate }) => ({ week, mrr: error_rate }))

export const STEPS = [
  { label: 'Forming hypotheses', short: 'Hypothesis', tool: 'OpenAI' },
  { label: 'Loading incident snapshot', short: 'Logs', tool: 'Context' },
  { label: 'Checking internal chatter', short: 'War Room', tool: 'Signals' },
  { label: 'Checking provider status', short: 'External', tool: 'Tavily' },
  { label: 'Drafting mitigation', short: 'Mitigate', tool: 'Fastino' },
]

export const STEP_DURATIONS = [850, 900, 1000, 900, 700]

export const PRESETS = [
  'Checkout API started returning HTTP 500 after deploy. Find the root cause and mitigation.',
  'Error budget burn is accelerating. Is this deploy regression, cloud outage, or dependency failure?',
]

export const STATUS_META = {
  supported:    { label: 'Supported',    cls: 'text-emerald-400', bar: 'from-emerald-500 to-emerald-400', border: 'border-emerald-500/25', bg: 'bg-emerald-500/5'  },
  rejected:     { label: 'Ruled Out',    cls: 'text-rose-400',    bar: 'from-rose-500 to-rose-400',      border: 'border-rose-500/25',    bg: 'bg-rose-500/5'     },
  inconclusive: { label: 'Inconclusive', cls: 'text-amber-400',   bar: 'from-amber-500 to-amber-400',    border: 'border-amber-500/25',   bg: 'bg-amber-500/5'    },
}

export const BASELINES = {
  baselineErrorRate: Number(baselineErrorRate.toFixed(2)),
  baselineLatency: Number(baselineLatency.toFixed(0)),
}
