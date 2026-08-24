import { useEffect, useState } from 'react';
import { Save, RotateCcw, SlidersHorizontal, Hash, Shield, Database } from 'lucide-react';
import { fetchConfig, updateConfig } from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';

const SECTIONS = [
  {
    title: 'Phase 1 — Sliding Window',
    icon: SlidersHorizontal,
    color: '#6366f1',
    fields: [
      { key: 'window_size', label: 'Window Size', desc: 'Max transactions kept in the sliding window', type: 'number', min: 1 },
      { key: 'time_threshold', label: 'Time Threshold (s)', desc: 'Seconds between automatic pipeline triggers', type: 'number', min: 1 },
      { key: 'batch_trigger_size', label: 'Batch Trigger Size', desc: 'Queued-transaction count that triggers auto-processing', type: 'number', min: 1 },
    ],
  },
  {
    title: 'Phase 3 — HDkT',
    icon: Hash,
    color: '#10b981',
    fields: [
      { key: 'stale_limit', label: 'Stale Limit', desc: 'Batches before a pattern is considered stale', type: 'number', min: 1 },
      { key: 'top_k', label: 'Top K', desc: 'Number of top patterns to mine', type: 'number', min: 1 },
    ],
  },
  {
    title: 'Phase 5 — Historical Validation',
    icon: Shield,
    color: '#ef4444',
    fields: [
      { key: 'decay_factor', label: 'Decay Factor', desc: 'Decay multiplier applied per batch (0 < x ≤ 1)', type: 'number', min: 0.01, max: 1, step: 0.01 },
      { key: 'hashmap_capacity', label: 'HashMap Capacity', desc: 'Max patterns stored in the tracker', type: 'number', min: 1 },
      { key: 'top_n_results', label: 'Top N Results', desc: 'Recommendations returned per pipeline run', type: 'number', min: 1 },
    ],
  },
  {
    title: 'Database',
    icon: Database,
    color: '#f59e0b',
    fields: [
      { key: 'db_path', label: 'DB Path', desc: 'Path to the SQLite database file', type: 'text', readonly: true },
    ],
  },
];

export default function ConfigPage() {
  const [config, setConfig] = useState(null);
  const [draft, setDraft] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  const loadConfig = async () => {
    try {
      const c = await fetchConfig();
      setConfig(c);
      setDraft(c);
    } catch { /* noop */ }
    setLoading(false);
  };

  useEffect(() => { loadConfig(); }, []);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const handleChange = (key, value, type) => {
    setDraft((prev) => ({
      ...prev,
      [key]: type === 'number' ? (value === '' ? '' : Number(value)) : value,
    }));
  };

  const handleSave = async () => {
    // Only send changed fields
    const changes = {};
    for (const section of SECTIONS) {
      for (const f of section.fields) {
        if (f.readonly) continue;
        if (draft[f.key] !== config[f.key]) {
          changes[f.key] = draft[f.key];
        }
      }
    }

    if (Object.keys(changes).length === 0) {
      showToast('No changes to save.', 'warning');
      return;
    }

    setSaving(true);
    try {
      const res = await updateConfig(changes);
      setConfig(res.config);
      setDraft(res.config);
      showToast(`Updated ${res.updated_fields.length} setting(s): ${res.updated_fields.join(', ')}`);
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setDraft({ ...config });
  };

  const hasChanges = config && JSON.stringify(draft) !== JSON.stringify(config);

  if (loading) return <LoadingSpinner message="Loading configuration…" />;

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Configuration</h1>
          <p className="text-sm text-text-secondary mt-1">Tune pipeline parameters at runtime</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            disabled={!hasChanges}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border-subtle text-text-secondary text-sm font-medium hover:bg-white/5 transition-all disabled:opacity-30 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold transition-all disabled:opacity-40 shadow-lg shadow-primary-500/20 cursor-pointer"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>

      {/* Sections */}
      <div className="space-y-6 stagger">
        {SECTIONS.map((section) => (
          <div key={section.title} className="glass rounded-xl border border-border-subtle overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-border-subtle">
              <div
                className="flex items-center justify-center w-7 h-7 rounded-md"
                style={{ backgroundColor: `${section.color}20` }}
              >
                <section.icon className="w-3.5 h-3.5" style={{ color: section.color }} />
              </div>
              <h2 className="text-sm font-semibold text-text-primary">{section.title}</h2>
            </div>

            <div className="p-5 space-y-5">
              {section.fields.map((f) => (
                <div key={f.key} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-6">
                  <div className="sm:w-56 shrink-0">
                    <label className="text-sm font-medium text-text-primary">{f.label}</label>
                    <p className="text-xs text-text-muted mt-0.5">{f.desc}</p>
                  </div>
                  <input
                    type={f.type}
                    value={draft[f.key] ?? ''}
                    onChange={(e) => handleChange(f.key, e.target.value, f.type)}
                    readOnly={f.readonly}
                    min={f.min}
                    max={f.max}
                    step={f.step}
                    className={`flex-1 bg-bg-deep/60 border border-border-subtle rounded-lg px-4 py-2.5 text-sm text-text-primary font-mono focus:outline-none focus:border-primary-500/40 focus:ring-1 focus:ring-primary-500/20 transition-all ${
                      f.readonly ? 'opacity-50 cursor-not-allowed' : ''
                    } ${
                      draft[f.key] !== config?.[f.key] ? 'border-primary-400/40 bg-primary-500/5' : ''
                    }`}
                  />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 animate-slide-up glass rounded-lg px-5 py-3 border text-sm font-medium shadow-2xl ${
            toast.type === 'error'
              ? 'border-error-500/30 text-error-400'
              : toast.type === 'warning'
                ? 'border-warning-500/30 text-warning-400'
                : 'border-success-500/30 text-success-400'
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
