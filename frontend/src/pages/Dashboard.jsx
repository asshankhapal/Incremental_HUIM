import { useEffect, useState } from 'react';
import {
  Database,
  Layers,
  Activity,
  TrendingUp,
  Play,
  ArrowRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { fetchStats, fetchTopK, fetchPipelineHistory, runPipeline } from '../api/client';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';



export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [topK, setTopK] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [toast, setToast] = useState(null);

  const loadData = async () => {
    try {
      const [s, t, r] = await Promise.all([
        fetchStats(),
        fetchTopK(10),
        fetchPipelineHistory(5),
      ]);
      setStats(s);
      setTopK(t.top_k || []);
      setRuns(r.runs || []);
    } catch {
      /* API might not be ready yet */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };



  const handleRunPipeline = async () => {
    setActionLoading('pipeline');
    try {
      const res = await runPipeline();
      showToast(
        res.status === 'no_data'
          ? 'No queued batches to process.'
          : `Pipeline run #${res.run_id} completed — ${res.patterns_discovered ?? 0} patterns found`,
        res.status === 'no_data' ? 'warning' : 'success',
      );
      loadData();
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <LoadingSpinner message="Loading dashboard…" />;

  const totalBatches = stats ? Object.values(stats.batches || {}).reduce((a, b) => a + b, 0) : 0;

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary">Dashboard</h1>
        <p className="text-sm text-text-secondary mt-1">
          Real-time overview of the Incremental HUIM mining pipeline
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Database} label="Transactions" value={stats?.total_transactions ?? 0} />
        <StatCard icon={Layers} label="Batches" value={totalBatches} subtitle={stats?.batches?.queued ? `${stats.batches.queued} queued` : undefined} />
        <StatCard icon={Activity} label="Pipeline Runs" value={stats?.total_pipeline_runs ?? 0} />
        <StatCard icon={TrendingUp} label="Patterns Tracked" value={stats?.total_patterns_tracked ?? 0} />
      </div>

      {/* Quick Actions */}
      <div className="mb-8 max-w-md">
        <button
          onClick={handleRunPipeline}
          disabled={actionLoading === 'pipeline'}
          className="w-full rounded-lg border border-border-default bg-bg-surface p-5 flex items-center gap-4 text-left hover:bg-bg-card-hover transition-colors cursor-pointer disabled:opacity-50"
        >
          <div className="flex items-center justify-center w-11 h-11 rounded-lg bg-bg-muted">
            <Play className="w-5 h-5 text-text-secondary" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-text-primary">
              {actionLoading === 'pipeline' ? 'Running…' : 'Run Pipeline'}
            </p>
            <p className="text-xs text-text-muted mt-0.5">Execute the full 5-phase mining pipeline</p>
          </div>
          <ArrowRight className="w-4 h-4 text-text-muted" />
        </button>
      </div>

      {/* Two-column: Top-K + Recent Runs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top-K Patterns */}
        <div className="lg:col-span-2 rounded-lg border border-border-default bg-bg-surface overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
            <h2 className="text-sm font-semibold text-text-primary">Top-K High-Utility Patterns</h2>
            <Link to="/results" className="text-xs font-medium text-text-secondary hover:text-text-primary transition-colors">
              View all →
            </Link>
          </div>
          {topK.length === 0 ? (
            <EmptyState title="No patterns mined" message="Ingest data and run the pipeline to discover patterns." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted text-xs uppercase tracking-wider bg-bg-card">
                    <th className="px-5 py-3 font-medium">Rank</th>
                    <th className="px-5 py-3 font-medium">Pattern</th>
                    <th className="px-5 py-3 font-medium text-right">Avg Utility</th>
                    <th className="px-5 py-3 font-medium text-right">Count</th>
                    <th className="px-5 py-3 font-medium text-right">Total Utility</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-muted">
                  {topK.map((p) => (
                    <tr key={p.rank} className="hover:bg-bg-card transition-colors">
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-bg-muted text-text-primary text-xs font-bold">
                          {p.rank}
                        </span>
                      </td>
                      <td className="px-5 py-3 font-mono text-xs text-text-primary">{p.pattern_key}</td>
                      <td className="px-5 py-3 text-right font-semibold text-text-primary">{p.avg_util.toFixed(4)}</td>
                      <td className="px-5 py-3 text-right text-text-secondary">{p.count}</td>
                      <td className="px-5 py-3 text-right text-text-secondary">{p.total_util.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Recent Runs */}
        <div className="rounded-lg border border-border-default bg-bg-surface overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
            <h2 className="text-sm font-semibold text-text-primary">Recent Runs</h2>
            <Link to="/pipeline" className="text-xs font-medium text-text-secondary hover:text-text-primary transition-colors">
              View all →
            </Link>
          </div>
          {runs.length === 0 ? (
            <EmptyState title="No runs yet" message="Trigger the pipeline to see run history." />
          ) : (
            <div className="divide-y divide-border-muted">
              {runs.map((r) => (
                <div key={r.run_id} className="px-5 py-3.5 hover:bg-bg-card transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-text-primary">Run #{r.run_id}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  <p className="text-[11px] text-text-muted">{r.started_at}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-lg bg-accent text-white px-5 py-3 text-sm font-medium shadow-lg">
          {toast.msg}
        </div>
      )}
    </div>
  );
}
