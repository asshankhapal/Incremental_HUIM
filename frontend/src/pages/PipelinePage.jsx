import { useEffect, useState } from 'react';
import {
  Play,
  Clock,
  Zap,
  SlidersHorizontal,
  BarChart3,
  Hash,
  Shield,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { runPipeline, fetchPipelineStatus, fetchPipelineHistory } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';

const PHASES = [
  { key: 'phase1_ms', label: 'Phase 1', title: 'Sliding Window', desc: 'Ingests new batch, evicts oldest if window is full', icon: SlidersHorizontal },
  { key: 'phase2_ms', label: 'Phase 2', title: 'Prefix Utility & MRU', desc: 'Incrementally updates item prefix utilities and MRU values', icon: Hash },
  { key: 'phase3_ms', label: 'Phase 3', title: 'HDkT Threshold', desc: 'Computes the minimum utility threshold for top-k mining', icon: BarChart3 },
  { key: 'phase4_ms', label: 'Phase 4', title: 'Top-K DFS Mining', desc: 'Depth-first search to discover high-utility itemsets', icon: Zap },
  { key: 'phase5_ms', label: 'Phase 5', title: 'Historical Validation', desc: 'Validates and ranks patterns using decay-weighted history', icon: Shield },
];

const CustomTooltip = ({ active, payload }) => {
  if (active && payload?.[0]) {
    return (
      <div className="rounded-lg bg-accent text-white px-3 py-2 text-xs shadow-lg">
        <p className="font-semibold">{payload[0].payload.label}</p>
        <p className="opacity-80">{payload[0].value.toFixed(2)} ms</p>
      </div>
    );
  }
  return null;
};

export default function PipelinePage() {
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [toast, setToast] = useState(null);

  const loadData = async () => {
    try {
      const [s, h] = await Promise.all([
        fetchPipelineStatus(),
        fetchPipelineHistory(20),
      ]);
      setStatus(s);
      setHistory(h.runs || []);
    } catch { /* noop */ }
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const handleRun = async () => {
    setRunning(true);
    try {
      const res = await runPipeline();
      showToast(
        res.status === 'no_data'
          ? 'No queued batches to process'
          : `Run #${res.run_id} completed — ${res.patterns_discovered ?? 0} patterns`,
        res.status === 'no_data' ? 'warning' : 'success',
      );
      loadData();
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <LoadingSpinner message="Loading pipeline data…" />;

  const timings = status?.details?.timings;
  const chartData = timings
    ? PHASES.map((p) => ({ label: p.label, value: timings[p.key] || 0 }))
    : [];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Pipeline</h1>
          <p className="text-sm text-text-secondary mt-1">Trigger, monitor, and analyze the 5-phase mining pipeline</p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-semibold transition-colors disabled:opacity-50 cursor-pointer"
        >
          <Play className="w-4 h-4" />
          {running ? 'Running…' : 'Run Pipeline'}
        </button>
      </div>

      {/* Phase cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-8">
        {PHASES.map((p) => {
          const ms = timings?.[p.key];
          return (
            <div
              key={p.key}
              className="rounded-lg border border-border-default bg-bg-surface p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <div className="flex items-center justify-center w-7 h-7 rounded-md bg-bg-muted">
                  <p.icon className="w-3.5 h-3.5 text-text-secondary" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-text-muted">{p.label}</span>
              </div>
              <p className="text-xs font-semibold text-text-primary mb-0.5">{p.title}</p>
              <p className="text-[11px] text-text-muted leading-snug mb-2">{p.desc}</p>
              {ms !== undefined && (
                <div className="flex items-center gap-1 mt-auto">
                  <Clock className="w-3 h-3 text-text-muted" />
                  <span className="text-xs font-semibold text-text-primary">{ms.toFixed(2)} ms</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Phase timing chart */}
        <div className="rounded-lg border border-border-default bg-bg-surface p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">Phase Timings (ms)</h2>
          {chartData.length === 0 ? (
            <EmptyState title="No timing data" message="Run the pipeline to see phase timings." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} barCategoryGap="20%">
                <XAxis dataKey="label" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} fill="#111827" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Last run summary */}
        <div className="rounded-lg border border-border-default bg-bg-surface p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">Last Run Summary</h2>
          {!status?.details ? (
            <EmptyState title="No run data" message="Trigger the pipeline to see detailed results." />
          ) : (
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-text-muted">Status</span>
                <StatusBadge status={status.details.status || status.status} />
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Run ID</span>
                <span className="text-text-primary font-semibold">#{status.details.run_id ?? status.run_id}</span>
              </div>
              {status.details.batch_new_id && (
                <>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Batch Processed</span>
                    <span className="text-text-primary">#{status.details.batch_new_id} ({status.details.batch_new_size} txns)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Evicted Batch</span>
                    <span className="text-text-primary">{status.details.batch_old_id ? `#${status.details.batch_old_id}` : 'None'}</span>
                  </div>
                </>
              )}
              {status.details.min_util_threshold !== undefined && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Min Utility Threshold</span>
                  <span className="text-text-primary font-semibold">{status.details.min_util_threshold.toFixed(4)}</span>
                </div>
              )}
              {status.details.patterns_discovered !== undefined && (
                <div className="flex justify-between">
                  <span className="text-text-muted">Patterns Discovered</span>
                  <span className="text-text-primary font-semibold">{status.details.patterns_discovered}</span>
                </div>
              )}
              {status.details.top_results?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border-default">
                  <p className="text-xs text-text-muted mb-2 font-medium uppercase tracking-wider">Top Results</p>
                  <div className="space-y-1.5">
                    {status.details.top_results.slice(0, 5).map((r, i) => (
                      <div key={i} className="flex items-center justify-between bg-bg-card rounded-lg px-3 py-2">
                        <span className="font-mono text-xs text-text-primary">{r.pattern}</span>
                        <span className="text-xs font-semibold text-text-primary">{r.avg_util.toFixed(4)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Run history table */}
      <div className="rounded-lg border border-border-default bg-bg-surface overflow-hidden">
        <div className="px-5 py-4 border-b border-border-default">
          <h2 className="text-sm font-semibold text-text-primary">Run History</h2>
        </div>
        {history.length === 0 ? (
          <EmptyState title="No history" message="Pipeline runs will appear here once triggered." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted text-xs uppercase tracking-wider bg-bg-card">
                  <th className="px-5 py-3 font-medium">Run ID</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Started At</th>
                  <th className="px-5 py-3 font-medium">Finished At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-muted">
                {history.map((r) => (
                  <tr key={r.run_id} className="hover:bg-bg-card transition-colors">
                    <td className="px-5 py-3 font-semibold text-text-primary">#{r.run_id}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-5 py-3 text-text-secondary text-xs">{r.started_at}</td>
                    <td className="px-5 py-3 text-text-secondary text-xs">{r.finished_at || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-lg bg-accent text-white px-5 py-3 text-sm font-medium shadow-lg">
          {toast.msg}
        </div>
      )}
    </div>
  );
}
