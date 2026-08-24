import { useEffect, useState, useMemo } from 'react';
import { Search, TrendingUp, ChevronLeft, ChevronRight } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { fetchTopK, fetchPatternHistory } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';

const GRADIENT_COLORS = ['#6366f1', '#818cf8', '#a5b4fc', '#6ee7b7', '#34d399', '#10b981', '#fbbf24', '#f59e0b', '#fb923c', '#ef4444'];

const CustomTooltip = ({ active, payload }) => {
  if (active && payload?.[0]) {
    return (
      <div className="glass rounded-lg px-3 py-2 text-xs shadow-xl border border-border-subtle">
        <p className="font-semibold text-text-primary font-mono">{payload[0].payload.pattern_key}</p>
        <p className="text-text-secondary">Avg Utility: {payload[0].value.toFixed(4)}</p>
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
      topK.slice(0, 10).map((p, i) => ({
        ...p,
        short: p.pattern_key.length > 12 ? p.pattern_key.slice(0, 12) + '…' : p.pattern_key,
        fill: GRADIENT_COLORS[i % GRADIENT_COLORS.length],
      })),
    [topK],
  );

  const totalPages = Math.ceil(total / LIMIT);

  if (loading) return <LoadingSpinner message="Loading results…" />;

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary">Results</h1>
        <p className="text-sm text-text-secondary mt-1">Explore mined high-utility itemset patterns</p>
      </div>

      {/* Top-K controls + chart */}
      <div className="glass rounded-xl border border-border-subtle p-5 mb-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-5">
          <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-primary-400" />
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
              className="w-32 accent-primary-500"
            />
            <span className="text-sm font-bold text-primary-400 min-w-[2rem] text-right">{k}</span>
          </div>
        </div>

        {chartData.length === 0 ? (
          <EmptyState title="No patterns" message="Run the pipeline to discover patterns." />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} barCategoryGap="15%">
              <XAxis
                dataKey="short"
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                interval={0}
                angle={-30}
                textAnchor="end"
                height={60}
              />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Bar dataKey="avg_util" radius={[6, 6, 0, 0]}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={d.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Top-K table */}
      <div className="glass rounded-xl border border-border-subtle overflow-hidden mb-8">
        <div className="px-5 py-4 border-b border-border-subtle">
          <h2 className="text-sm font-semibold text-text-primary">Top-{k} Patterns</h2>
        </div>
        {topK.length === 0 ? (
          <EmptyState title="Empty" message="No patterns available." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted text-xs uppercase tracking-wider">
                  <th className="px-5 py-3 font-medium">Rank</th>
                  <th className="px-5 py-3 font-medium">Pattern</th>
                  <th className="px-5 py-3 font-medium text-right">Avg Utility</th>
                  <th className="px-5 py-3 font-medium text-right">Total Utility</th>
                  <th className="px-5 py-3 font-medium text-right">Count</th>
                  <th className="px-5 py-3 font-medium text-right">Last Seen Batch</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {topK.map((p) => (
                  <tr key={p.rank} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-3">
                      <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-primary-500/10 text-primary-400 text-xs font-bold">
                        {p.rank}
                      </span>
                    </td>
                    <td className="px-5 py-3 font-mono text-xs text-text-primary">{p.pattern_key}</td>
                    <td className="px-5 py-3 text-right font-semibold text-success-400">{p.avg_util.toFixed(4)}</td>
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
      <div className="glass rounded-xl border border-border-subtle overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
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
              className="pl-8 pr-3 py-1.5 bg-bg-deep/60 border border-border-subtle rounded-lg text-xs text-text-primary placeholder-text-muted focus:outline-none focus:border-primary-500/40 transition-all w-48"
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
                  <tr className="text-left text-text-muted text-xs uppercase tracking-wider">
                    <th className="px-5 py-3 font-medium">Pattern</th>
                    <th className="px-5 py-3 font-medium text-right">Avg Utility</th>
                    <th className="px-5 py-3 font-medium text-right">Total Utility</th>
                    <th className="px-5 py-3 font-medium text-right">Count</th>
                    <th className="px-5 py-3 font-medium text-right">Last Seen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {filteredPatterns.map((p) => (
                    <tr key={p.pattern_key} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-5 py-3 font-mono text-xs text-text-primary">{p.pattern_key}</td>
                      <td className="px-5 py-3 text-right font-semibold text-success-400">{p.avg_util.toFixed(4)}</td>
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
              <div className="flex items-center justify-between px-5 py-3 border-t border-border-subtle">
                <p className="text-xs text-text-muted">
                  Page {page + 1} of {totalPages}
                </p>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="p-1.5 rounded-md hover:bg-white/5 disabled:opacity-30 transition-colors cursor-pointer"
                  >
                    <ChevronLeft className="w-4 h-4 text-text-secondary" />
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="p-1.5 rounded-md hover:bg-white/5 disabled:opacity-30 transition-colors cursor-pointer"
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
