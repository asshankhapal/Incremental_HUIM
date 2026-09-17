import { useEffect, useState, useMemo } from 'react';
import { Search, TrendingUp, ChevronLeft, ChevronRight } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { fetchTopK, fetchPatternHistory } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';

const CustomTooltip = ({ active, payload }) => {
  if (active && payload?.[0]) {
    return (
      <div className="rounded-lg bg-accent text-white px-3 py-2 text-xs shadow-lg">
        <p className="font-semibold font-mono">{payload[0].payload.pattern_key}</p>
        <p className="opacity-80">Avg Utility: {payload[0].value.toFixed(4)}</p>
      </div>
    );
  }
  return null;
};

export default function ResultsPage() {
  const [k, setK] = useState(10);
  const [topK, setTopK] = useState([]);
  const [patterns, setPatterns] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const LIMIT = 20;

  const loadData = async () => {
    try {
      const [tk, ph] = await Promise.all([
        fetchTopK(k),
        fetchPatternHistory(LIMIT, page * LIMIT),
      ]);
      setTopK(tk.top_k || []);
      setPatterns(ph.patterns || []);
      setTotal(ph.total || 0);
    } catch { /* noop */ }
    setLoading(false);
  };

  useEffect(() => { loadData(); }, [k, page]);

  const filteredPatterns = useMemo(() => {
    if (!search.trim()) return patterns;
    const q = search.toLowerCase();
    return patterns.filter((p) => p.pattern_key.toLowerCase().includes(q));
  }, [patterns, search]);

  const chartData = useMemo(
    () =>
      topK.slice(0, 10).map((p) => ({
        ...p,
        short: p.pattern_key.length > 12 ? p.pattern_key.slice(0, 12) + '…' : p.pattern_key,
      })),
    [topK],
  );

  const totalPages = Math.ceil(total / LIMIT);

  if (loading) return <LoadingSpinner message="Loading results…" />;

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary">Results</h1>
        <p className="text-sm text-text-secondary mt-1">Explore mined high-utility itemset patterns</p>
      </div>

      {/* Top-K controls + chart */}
      <div className="rounded-lg border border-border-default bg-bg-surface p-5 mb-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-5">
          <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-text-secondary" />
            Top-K Patterns by Avg Utility
          </h2>
          <div className="flex items-center gap-3">
            <label className="text-xs text-text-muted">K =</label>
            <input
              type="range"
              min={5}
              max={100}
              step={5}
              value={k}
              onChange={(e) => setK(Number(e.target.value))}
              className="w-32 accent-[#111827]"
            />
            <span className="text-sm font-bold text-text-primary min-w-[2rem] text-right">{k}</span>
          </div>
        </div>

        {chartData.length === 0 ? (
          <EmptyState title="No patterns" message="Run the pipeline to discover patterns." />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} barCategoryGap="15%">
              <XAxis
                dataKey="short"
                tick={{ fill: '#9ca3af', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                interval={0}
                angle={-30}
                textAnchor="end"
                height={60}
              />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
              <Bar dataKey="avg_util" radius={[4, 4, 0, 0]} fill="#111827" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Top-K table */}
      <div className="rounded-lg border border-border-default bg-bg-surface overflow-hidden mb-8">
        <div className="px-5 py-4 border-b border-border-default">
          <h2 className="text-sm font-semibold text-text-primary">Top-{k} Patterns</h2>
        </div>
        {topK.length === 0 ? (
          <EmptyState title="Empty" message="No patterns available." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted text-xs uppercase tracking-wider bg-bg-card">
                  <th className="px-5 py-3 font-medium">Rank</th>
                  <th className="px-5 py-3 font-medium">Pattern</th>
                  <th className="px-5 py-3 font-medium text-right">Avg Utility</th>
                  <th className="px-5 py-3 font-medium text-right">Total Utility</th>
                  <th className="px-5 py-3 font-medium text-right">Count</th>
                  <th className="px-5 py-3 font-medium text-right">Last Seen Batch</th>
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
                    <td className="px-5 py-3 text-right text-text-secondary">{p.total_util.toFixed(4)}</td>
                    <td className="px-5 py-3 text-right text-text-secondary">{p.count}</td>
                    <td className="px-5 py-3 text-right text-text-secondary">#{p.last_seen_batch}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Full pattern history */}
      <div className="rounded-lg border border-border-default bg-bg-surface overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
          <h2 className="text-sm font-semibold text-text-primary">
            Pattern History
            <span className="text-text-muted font-normal ml-2">({total} total)</span>
          </h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter patterns…"
              className="pl-8 pr-3 py-1.5 bg-bg-card border border-border-default rounded-lg text-xs text-text-primary placeholder-text-muted focus:outline-none focus:border-text-secondary transition-colors w-48"
            />
          </div>
        </div>

        {filteredPatterns.length === 0 ? (
          <EmptyState title="No patterns" message={search ? 'No patterns match your search.' : 'No patterns tracked yet.'} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-muted text-xs uppercase tracking-wider bg-bg-card">
                    <th className="px-5 py-3 font-medium">Pattern</th>
                    <th className="px-5 py-3 font-medium text-right">Avg Utility</th>
                    <th className="px-5 py-3 font-medium text-right">Total Utility</th>
                    <th className="px-5 py-3 font-medium text-right">Count</th>
                    <th className="px-5 py-3 font-medium text-right">Last Seen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-muted">
                  {filteredPatterns.map((p) => (
                    <tr key={p.pattern_key} className="hover:bg-bg-card transition-colors">
                      <td className="px-5 py-3 font-mono text-xs text-text-primary">{p.pattern_key}</td>
                      <td className="px-5 py-3 text-right font-semibold text-text-primary">{p.avg_util.toFixed(4)}</td>
                      <td className="px-5 py-3 text-right text-text-secondary">{p.total_util.toFixed(4)}</td>
                      <td className="px-5 py-3 text-right text-text-secondary">{p.count}</td>
                      <td className="px-5 py-3 text-right text-text-secondary">#{p.last_seen_batch}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-5 py-3 border-t border-border-default">
                <p className="text-xs text-text-muted">
                  Page {page + 1} of {totalPages}
                </p>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="p-1.5 rounded-md hover:bg-bg-card disabled:opacity-30 transition-colors cursor-pointer"
                  >
                    <ChevronLeft className="w-4 h-4 text-text-secondary" />
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="p-1.5 rounded-md hover:bg-bg-card disabled:opacity-30 transition-colors cursor-pointer"
                  >
                    <ChevronRight className="w-4 h-4 text-text-secondary" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
