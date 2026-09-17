import { useEffect, useState, useRef, useMemo } from 'react';
import {
  Upload, ChevronDown, ChevronRight, FileJson, AlertCircle, FileUp, X,
  FileSpreadsheet, Settings, Play, Cpu, Clock, TrendingUp, BarChart3,
  RotateCcw, CheckCircle2, Database, Info
} from 'lucide-react';
import { ingestBatch, fetchBatches, fetchTransactions, runDataset, runDatasetFile } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import EmptyState from '../components/EmptyState';

const PLACEHOLDER = 'Paste your transaction dataset here (JSON array or SPMF format)...';

/**
 * Parse a text dataset into transactions [{items, utilities}].
 * Supports many common formats:
 *   1. HUIM format:   "A B C:5 3 8"  (colon separates items from utilities, space-delimited)
 *   2. SPMF HUIM format: "item1 item2 ...:TU:util1 util2 ..." (two colons separating items, TU, and utilities)
 *   3. Pipe format:   "A,B,C | 5,3,8"
 *   4. Tab format:    "A,B,C\t5,3,8"
 *   5. Colon-pairs:   "A:5,B:3,C:8"
 *   6. CSV headers:   items,utilities  then  "A,B,C","5,3,8"
 *   7. Semicolon CSV: "A;B;C;5;3;8"  (first half items, second half utilities)
 */
function parseTextData(text) {
  const rawLines = text.trim().split(/\r?\n/).filter((l) => l.trim());
  if (rawLines.length === 0) throw new Error('File is empty');

  const transactions = [];

  // Detect & skip header row
  const firstLower = rawLines[0].toLowerCase();
  const hasHeader =
    firstLower.includes('items') ||
    firstLower.includes('utilities') ||
    firstLower.includes('transaction') ||
    firstLower.includes('item') && firstLower.includes('util');
  const startIdx = hasHeader ? 1 : 0;

  for (let i = startIdx; i < rawLines.length; i++) {
    const line = rawLines[i].trim();
    if (!line || line.startsWith('#') || line.startsWith('//')) continue;

    let items = null;
    let utilities = null;

    const colonParts = line.split(':');

    // ── Format 2: SPMF HUIM standard  "item1 item2 ...:TU:util1 util2 ..." ──
    if (colonParts.length === 3) {
      const left = colonParts[0].trim();
      const right = colonParts[2].trim();
      const leftTokens = left.split(/[\s,]+/).filter(Boolean);
      const rightTokens = right.split(/[\s,]+/).filter(Boolean);
      const rightNums = rightTokens.map(Number);
      if (leftTokens.length > 0 && rightNums.every((n) => !isNaN(n)) && rightNums.length > 0) {
        items = leftTokens;
        utilities = rightNums;
      }
    }

    // ── Format 1: HUIM standard  "A B C:5 3 8" ────────────────
    if (!items && colonParts.length === 2) {
      const left = colonParts[0].trim();
      const right = colonParts[1].trim();

      if (right && /\s/.test(left + right)) {
        const leftTokens = left.split(/[\s,]+/).filter(Boolean);
        const rightTokens = right.split(/[\s,]+/).filter(Boolean);
        const rightNums = rightTokens.map(Number);
        if (leftTokens.length > 0 && rightNums.every((n) => !isNaN(n)) && rightNums.length > 0) {
          items = leftTokens;
          utilities = rightNums;
        }
      }
    }

    // ── Format 3: Pipe-delimited  "A,B,C | 5,3,8" ─────────────
    if (!items && line.includes('|')) {
      const parts = line.split('|').map((s) => s.trim().replace(/^"|"$/g, ''));
      if (parts.length >= 2) {
        const left = parts[0].split(/[\s,]+/).filter(Boolean);
        const right = parts[1].split(/[\s,]+/).map(Number).filter((n) => !isNaN(n));
        if (left.length > 0 && right.length > 0) {
          items = left;
          utilities = right;
        }
      }
    }

    // ── Format 4: Tab-delimited  "A,B,C\t5,3,8" ───────────────
    if (!items && line.includes('\t')) {
      const parts = line.split('\t').map((s) => s.trim().replace(/^"|"$/g, ''));
      if (parts.length >= 2) {
        const left = parts[0].split(/[\s,]+/).filter(Boolean);
        const right = parts[1].split(/[\s,]+/).map(Number).filter((n) => !isNaN(n));
        if (left.length > 0 && right.length > 0) {
          items = left;
          utilities = right;
        }
      }
    }

    // ── Format 5: Colon-pairs  "A:5,B:3,C:8" or "A:5 B:3 C:8" ─
    if (!items && colonParts.length > 3) {
      const pairs = line.split(/[\s,]+/).filter(Boolean);
      const tmpItems = [];
      const tmpUtils = [];
      for (const p of pairs) {
        const idx = p.lastIndexOf(':');
        if (idx > 0) {
          const it = p.slice(0, idx).trim();
          const ut = Number(p.slice(idx + 1).trim());
          if (it && !isNaN(ut)) {
            tmpItems.push(it);
            tmpUtils.push(ut);
          }
        }
      }
      if (tmpItems.length > 0) {
        items = tmpItems;
        utilities = tmpUtils;
      }
    }

    // ── Format 6: Quoted CSV  "A,B,C","5,3,8" ─────────────────
    if (!items) {
      const quoted = [...line.matchAll(/"([^"]*)"/g)].map((m) => m[1]);
      if (quoted.length >= 2) {
        const left = quoted[0].split(/[\s,]+/).filter(Boolean);
        const right = quoted[1].split(/[\s,]+/).map(Number).filter((n) => !isNaN(n));
        if (left.length > 0 && right.length > 0) {
          items = left;
          utilities = right;
        }
      }
    }

    // ── Format 7: Plain comma-separated  "A,B,C,5,3,8" ────────
    if (!items) {
      const tokens = line.split(/[\s,;]+/).filter(Boolean);
      if (tokens.length >= 2) {
        let splitAt = tokens.findIndex((t) => /^-?\d+(\.\d+)?$/.test(t));
        if (splitAt > 0) {
          const left = tokens.slice(0, splitAt);
          const right = tokens.slice(splitAt).map(Number);
          if (left.length > 0 && right.every((n) => !isNaN(n)) && right.length > 0) {
            items = left;
            utilities = right;
          }
        }
      }
    }

    if (items && utilities) {
      transactions.push({ items, utilities });
    }
  }

  return transactions;
}

export default function IngestPage() {
  const [mode, setMode] = useState('paste');
  const [json, setJson] = useState('');
  const [file, setFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  const [parseWarning, setParseWarning] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [batches, setBatches] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [txns, setTxns] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const fileInputRef = useRef(null);

  const [viewState, setViewState] = useState('input');
  const [parsedDataset, setParsedDataset] = useState(null);
  const [topK, setTopK] = useState(10);
  const [batchSize, setBatchSize] = useState(20);
  const [resultsData, setResultsData] = useState(null);

  const loadBatches = async () => {
    try {
      const res = await fetchBatches();
      setBatches(res.batches || []);
    } catch { /* noop */ }
    setLoading(false);
  };

  useEffect(() => { loadBatches(); }, []);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const processFile = async (f) => {
    if (/\.(csv|txt)$/i.test(f.name)) {
      setParseWarning(null);
      setParsedDataset(null);
      setBatchSize(100);
      setTopK(10);
      setFile(f);
      setViewState('settings');
      return;
    }

    const text = await f.text();
    setParseWarning(null);

    let transactions;

    try {
      const parsed = JSON.parse(text);
      transactions = Array.isArray(parsed) ? parsed : parsed.transactions;
      if (Array.isArray(transactions) && transactions.length > 0 && transactions[0].items) {
        setParsedDataset(transactions);
        const recommendedBatch = Math.max(1, Math.round(transactions.length * 0.2));
        setBatchSize(recommendedBatch);
        setTopK(10);
        setFile(f);
        setViewState('settings');
        return;
      }
    } catch {
      // JSON parse failed — fall through to text parsing
    }

    try {
      transactions = parseTextData(text);
    } catch (e) {
      showToast(e.message, 'error');
      return;
    }

    if (!Array.isArray(transactions) || transactions.length === 0) {
      showToast('Could not parse any transactions from the file. Check the format.', 'error');
      return;
    }

    const totalLines = text.trim().split(/\r?\n/).filter((l) => l.trim() && !l.trim().startsWith('#')).length;
    if (transactions.length < totalLines * 0.5) {
      setParseWarning(`Parsed ${transactions.length} of ~${totalLines} lines. Some lines may have been skipped.`);
    }

    setParsedDataset(transactions);
    const recommendedBatch = Math.max(1, Math.round(transactions.length * 0.2));
    setBatchSize(recommendedBatch);
    setTopK(10);
    setFile(f);
    setViewState('settings');
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) processFile(f);
  };

  const handleFileSelect = (e) => {
    const f = e.target.files?.[0];
    if (f) processFile(f);
    e.target.value = '';
  };

  const clearFile = () => {
    setFile(null);
    setFilePreview(null);
    setParseWarning(null);
  };

  const handleAnalyzePaste = () => {
    if (!json.trim()) {
      showToast('Please paste some data first.', 'error');
      return;
    }

    let transactions;
    try {
      let parsed;
      try {
        parsed = JSON.parse(json);
      } catch (e) {
        try {
          parsed = parseTextData(json);
        } catch (textErr) {
          throw new Error(`Failed to parse input as JSON or Dataset: ${e.message}`);
        }
      }
      transactions = Array.isArray(parsed) ? parsed : parsed.transactions;

      if (!Array.isArray(transactions) || transactions.length === 0) {
        throw new Error('Provide an array of {items, utilities} objects.');
      }

      setParsedDataset(transactions);
      const recommendedBatch = Math.max(1, Math.round(transactions.length * 0.2));
      setBatchSize(recommendedBatch);
      setTopK(10);
      setViewState('settings');
    } catch (e) {
      showToast(e.message || 'Invalid input', 'error');
    }
  };

  const handleProcessDataset = async () => {
    if ((!parsedDataset || parsedDataset.length === 0) && !file) return;

    if (isNaN(topK) || topK <= 0) {
      showToast('Top Patterns (K) must be a positive integer.', 'error');
      return;
    }
    if (isNaN(batchSize) || batchSize <= 0) {
      showToast('Batch Size (B) must be a positive integer.', 'error');
      return;
    }

    setViewState('processing');
    try {
      const res = file && !parsedDataset
        ? await runDatasetFile(file, parseInt(batchSize), parseInt(topK))
        : await runDataset(parsedDataset, parseInt(batchSize), parseInt(topK));
      setResultsData(res);
      setViewState('results');
      showToast('Dataset processed successfully!');
      loadBatches();
    } catch (e) {
      setViewState('settings');
      showToast(e.message || 'Processing failed', 'error');
    }
  };

  const datasetStats = useMemo(() => {
    if (file && !parsedDataset) {
      return {
        totalTxns: 'Processed in batches', uniqueItemsCount: 'Calculated server-side',
        avgLen: '—', totalUtility: '—', avgUtil: '—', topItems: []
      };
    }
    if (!parsedDataset || parsedDataset.length === 0) return null;

    const totalTxns = parsedDataset.length;
    let itemCounts = {};
    let totalItemsCount = 0;
    let totalUtility = 0;

    for (const txn of parsedDataset) {
      totalItemsCount += txn.items.length;
      let txnUtil = txn.utilities.reduce((sum, val) => sum + val, 0);
      totalUtility += txnUtil;

      const uniqueTxnItems = new Set(txn.items);
      for (const item of uniqueTxnItems) {
        itemCounts[item] = (itemCounts[item] || 0) + 1;
      }
    }

    const uniqueItems = Object.keys(itemCounts);
    const avgLen = totalTxns > 0 ? (totalItemsCount / totalTxns) : 0;
    const avgUtil = totalTxns > 0 ? (totalUtility / totalTxns) : 0;

    const topItems = Object.entries(itemCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([item, count]) => ({
        item,
        count,
        percent: totalTxns > 0 ? ((count / totalTxns) * 100).toFixed(1) : 0
      }));

    return {
      totalTxns,
      uniqueItemsCount: uniqueItems.length,
      avgLen: avgLen.toFixed(2),
      totalUtility: totalUtility.toFixed(2),
      avgUtil: avgUtil.toFixed(2),
      topItems
    };
  }, [parsedDataset, file]);

  const toggleExpand = async (batchId) => {
    if (expanded === batchId) {
      setExpanded(null);
      return;
    }
    setExpanded(batchId);
    if (!txns[batchId]) {
      try {
        const res = await fetchTransactions(batchId);
        setTxns((prev) => ({ ...prev, [batchId]: res.transactions }));
      } catch {
        setTxns((prev) => ({ ...prev, [batchId]: [] }));
      }
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary">
          {viewState === 'input' && 'Ingest Data'}
          {viewState === 'settings' && 'Configure Run'}
          {viewState === 'processing' && 'Processing Pipeline'}
          {viewState === 'results' && 'Mining Results'}
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          {viewState === 'input' && 'Upload transaction batches or datasets to run the incremental pipeline'}
          {viewState === 'settings' && 'Review dataset characteristics and configure mining thresholds'}
          {viewState === 'processing' && 'Running incremental high-utility itemset mining batch-by-batch...'}
          {viewState === 'results' && 'Review mined top patterns and execution profile statistics'}
        </p>
      </div>

      {/* Input View */}
      {viewState === 'input' && (
        <>
          <div className="rounded-lg border border-border-default bg-bg-surface p-6 mb-8">
            {/* Mode tabs */}
            <div className="flex items-center gap-1 mb-5 bg-bg-muted rounded-lg p-1 w-fit">
              <button
                onClick={() => setMode('paste')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-semibold transition-colors cursor-pointer ${
                  mode === 'paste'
                    ? 'bg-bg-surface text-text-primary shadow-sm'
                    : 'text-text-muted hover:text-text-secondary'
                }`}
              >
                <FileJson className="w-3.5 h-3.5" />
                Paste JSON / Dataset
              </button>
              <button
                onClick={() => setMode('upload')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-semibold transition-colors cursor-pointer ${
                  mode === 'upload'
                    ? 'bg-bg-surface text-text-primary shadow-sm'
                    : 'text-text-muted hover:text-text-secondary'
                }`}
              >
                <FileUp className="w-3.5 h-3.5" />
                Upload Dataset File
              </button>
            </div>

            {/* Paste JSON mode */}
            {mode === 'paste' && (
              <>
                <textarea
                  value={json}
                  onChange={(e) => setJson(e.target.value)}
                  placeholder={PLACEHOLDER}
                  rows={10}
                  className="w-full bg-bg-card border border-border-default rounded-lg px-4 py-3 text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-text-muted transition-colors resize-y"
                />
              </>
            )}

            {/* Upload file mode */}
            {mode === 'upload' && (
              <>
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={handleFileDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`relative flex flex-col items-center justify-center py-14 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${
                    dragging
                      ? 'border-text-primary bg-bg-muted'
                      : 'border-border-default hover:border-text-muted'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".json,.csv,.txt"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-bg-muted mb-4">
                    <FileUp className="w-7 h-7 text-text-muted" />
                  </div>
                  <p className="text-sm font-semibold text-text-primary mb-1">
                    {dragging ? 'Drop file here' : 'Click to browse or drag & drop'}
                  </p>
                  <p className="text-xs text-text-muted">
                    Supports <code className="bg-bg-muted px-1 rounded text-text-secondary">.json</code>,{' '}
                    <code className="bg-bg-muted px-1 rounded text-text-secondary">.csv</code>, and{' '}
                    <code className="bg-bg-muted px-1 rounded text-text-secondary">.txt</code> files
                  </p>
                </div>
              </>
            )}

            {/* Footer with hints + submit */}
            <div className="flex items-center justify-between mt-4">
              <p className="text-xs text-text-muted flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                {mode === 'upload'
                  ? 'Selecting a file automatically parses it and enters settings'
                  : <>Provide standard dataset syntax (e.g. SPMF "item1 item2:TU:util1 util2" or JSON arrays)</>
                }
              </p>
              <button
                id="analyzeDatasetPasteBtn"
                onClick={mode === 'paste' ? handleAnalyzePaste : () => {}}
                disabled={mode === 'paste' ? !json.trim() : true}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              >
                <Upload className="w-4 h-4" />
                Analyze Dataset
              </button>
            </div>
          </div>

          {/* Batch history */}
          <div className="rounded-lg border border-border-default bg-bg-surface overflow-hidden">
            <div className="px-5 py-4 border-b border-border-default">
              <h2 className="text-sm font-semibold text-text-primary">Batch History</h2>
            </div>

            {loading ? (
              <LoadingSpinner message="Loading batches…" />
            ) : batches.length === 0 ? (
              <EmptyState title="No batches" message="Upload your first batch of transactions above." />
            ) : (
              <div className="divide-y divide-border-muted">
                {batches.map((b) => (
                  <div key={b.batch_id}>
                    <button
                      onClick={() => toggleExpand(b.batch_id)}
                      className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-bg-card transition-colors text-left cursor-pointer"
                    >
                      {expanded === b.batch_id ? (
                        <ChevronDown className="w-4 h-4 text-text-muted" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-text-muted" />
                      )}
                      <span className="text-sm font-semibold text-text-primary min-w-[70px]">
                        Batch #{b.batch_id}
                      </span>
                      <StatusBadge status={b.status} />
                      <span className="text-xs text-text-muted ml-auto">
                        {b.txn_count} txn{b.txn_count !== 1 ? 's' : ''} · {b.created_at}
                      </span>
                    </button>

                    {expanded === b.batch_id && (
                      <div className="px-5 pb-4 pl-14">
                        {!txns[b.batch_id] ? (
                          <LoadingSpinner message="Loading transactions…" />
                        ) : txns[b.batch_id].length === 0 ? (
                          <p className="text-xs text-text-muted py-2">No transactions found.</p>
                        ) : (
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-text-muted uppercase tracking-wider">
                                  <th className="px-3 py-2 text-left font-medium">TID</th>
                                  <th className="px-3 py-2 text-left font-medium">Items</th>
                                  <th className="px-3 py-2 text-left font-medium">Utilities</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-border-muted">
                                {txns[b.batch_id].map((t) => (
                                  <tr key={t.tid} className="hover:bg-bg-card">
                                    <td className="px-3 py-2 text-text-secondary">{t.tid}</td>
                                    <td className="px-3 py-2 font-mono text-text-primary">
                                      {t.items.map((it, i) => (
                                        <span key={i} className="inline-block bg-bg-muted text-text-primary px-1.5 py-0.5 rounded mr-1 mb-0.5">
                                          {it}
                                        </span>
                                      ))}
                                    </td>
                                    <td className="px-3 py-2 font-mono text-text-secondary">
                                      [{t.utilities.join(', ')}]
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Settings View */}
      {viewState === 'settings' && datasetStats && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
          {/* Left Panel: Stats */}
          <div className="lg:col-span-2 space-y-6">
            <div className="rounded-lg border border-border-default bg-bg-surface p-6">
              <h2 className="text-base font-bold text-text-primary mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-text-secondary" />
                Dataset Analysis
              </h2>
              
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-bg-card rounded-lg p-4 border border-border-muted">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Total Transactions</span>
                  <p className="text-xl font-extrabold text-text-primary mt-1">{datasetStats.totalTxns}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-4 border border-border-muted">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Unique Items</span>
                  <p className="text-xl font-extrabold text-text-primary mt-1">{datasetStats.uniqueItemsCount}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-4 border border-border-muted">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Avg Transaction Length</span>
                  <p className="text-xl font-extrabold text-text-primary mt-1">{datasetStats.avgLen}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-4 border border-border-muted">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Total Utility</span>
                  <p className="text-xl font-extrabold text-text-primary mt-1">{datasetStats.totalUtility}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-4 border border-border-muted col-span-2 md:col-span-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Avg Transaction Utility</span>
                  <p className="text-xl font-extrabold text-text-primary mt-1">{datasetStats.avgUtil}</p>
                </div>
              </div>

              {/* Frequent items list */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-text-secondary mb-3">Top Frequent Items</h3>
                <div className="space-y-2.5">
                  {datasetStats.topItems.map((itemObj, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="font-mono bg-bg-muted text-text-primary px-2 py-0.5 rounded min-w-[36px] text-center">
                        {itemObj.item}
                      </span>
                      <div className="flex-1 mx-4 h-1.5 bg-bg-muted rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-text-primary rounded-full" 
                          style={{ width: `${itemObj.percent}%` }}
                        />
                      </div>
                      <span className="text-text-secondary min-w-[70px] text-right font-medium">
                        {itemObj.count} txns ({itemObj.percent}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel: Settings inputs */}
          <div className="space-y-6">
            <div className="rounded-lg border border-border-default bg-bg-surface p-6 flex flex-col h-full justify-between">
              <div>
                <h2 className="text-base font-bold text-text-primary mb-4 flex items-center gap-2">
                  <Settings className="w-4 h-4 text-text-secondary" />
                  Mining Settings
                </h2>
                
                <div className="space-y-4">
                  <div>
                    <label htmlFor="topKInput" className="block text-xs font-semibold text-text-secondary mb-1">
                      Top Patterns (K)
                    </label>
                    <input
                      id="topKInput"
                      type="number"
                      min="1"
                      value={topK}
                      onChange={(e) => setTopK(parseInt(e.target.value) || '')}
                      className="w-full bg-bg-card border border-border-default rounded-lg px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus:border-text-muted transition-colors"
                    />
                    <p className="text-[10px] text-text-muted mt-1">Number of top high-utility patterns to mine.</p>
                  </div>

                  <div>
                    <label htmlFor="batchSizeInput" className="block text-xs font-semibold text-text-secondary mb-1">
                      Batch Size (B)
                    </label>
                    <input
                      id="batchSizeInput"
                      type="number"
                      min="1"
                      value={batchSize}
                      onChange={(e) => setBatchSize(parseInt(e.target.value) || '')}
                      className="w-full bg-bg-card border border-border-default rounded-lg px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus:border-text-muted transition-colors"
                    />
                    <p className="text-[10px] text-text-muted mt-1">
                      CSV/TXT uploads are parsed and processed in batches. A smaller batch completes mining sooner.
                    </p>
                  </div>
                </div>

                <div className="mt-5 p-3 rounded-lg bg-bg-card border border-border-muted text-xs text-text-secondary space-y-1.5">
                  <p className="font-semibold flex items-center gap-1 text-text-primary">
                    <Info className="w-3.5 h-3.5" /> Incremental Execution
                  </p>
                  <p className="text-[11px] leading-relaxed">
                    The backend will run database truncation, temporarily set the window size to the total transactions, and stream each batch sequentially.
                  </p>
                </div>
              </div>

              <div className="mt-8 space-y-3">
                <button
                  id="processDatasetBtn"
                  onClick={handleProcessDataset}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-bold transition-colors cursor-pointer"
                >
                  <Play className="w-4 h-4" />
                  Process Dataset
                </button>
                <button
                  id="cancelSettingsBtn"
                  onClick={() => { setViewState('input'); setParsedDataset(null); }}
                  className="w-full py-2.5 rounded-lg border border-border-default hover:bg-bg-card text-text-secondary hover:text-text-primary text-xs font-semibold transition-colors cursor-pointer"
                >
                  Cancel & Go Back
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Processing Loader View */}
      {viewState === 'processing' && (
        <div className="rounded-lg border border-border-default bg-bg-surface p-12 flex flex-col items-center justify-center min-h-[350px]">
          <LoadingSpinner message="Ingesting & executing incremental mining steps batch-by-batch..." />
          <p className="text-xs text-text-muted mt-4 text-center max-w-md leading-relaxed">
            Optimized dual-pruning DFS mining is executing on the server. Because of transaction pre-sorting and suffix sum lookup optimizations, execution should complete in seconds.
          </p>
        </div>
      )}

      {/* Results View */}
      {viewState === 'results' && resultsData && (
        <div className="space-y-8 mb-8">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="rounded-lg border border-border-default bg-bg-surface p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-bg-muted flex items-center justify-center">
                <Database className="w-5 h-5 text-text-secondary" />
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Total Batches Run</span>
                <p className="text-xl font-extrabold text-text-primary mt-0.5">{resultsData.total_batches}</p>
              </div>
            </div>

            <div className="rounded-lg border border-border-default bg-bg-surface p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-bg-muted flex items-center justify-center">
                <Cpu className="w-5 h-5 text-text-secondary" />
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Patterns Mined</span>
                <p className="text-xl font-extrabold text-text-primary mt-0.5">{resultsData.top_results?.length || 0}</p>
              </div>
            </div>

            <div className="rounded-lg border border-border-default bg-bg-surface p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-bg-muted flex items-center justify-center">
                <Clock className="w-5 h-5 text-text-secondary" />
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Total Core Time</span>
                <p className="text-xl font-extrabold text-text-primary mt-0.5">
                  {(Object.values(resultsData.timings || {}).reduce((a, b) => a + b, 0) / 1000).toFixed(3)}s
                </p>
              </div>
            </div>
          </div>

          {/* Candidate Generation & Pruning Stats */}
          {resultsData.dfs_stats && (
            <div className="rounded-lg border border-border-default bg-bg-surface p-6">
              <h2 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-text-secondary" />
                Candidate Generation &amp; Pruning
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <div className="bg-bg-card rounded-lg p-3 border border-border-muted text-center">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Candidates Generated</span>
                  <p className="text-lg font-extrabold text-text-primary mt-1">{(resultsData.dfs_stats.nodes || 0).toLocaleString()}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-3 border border-border-muted text-center">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">HUIs Found</span>
                  <p className="text-lg font-extrabold text-text-primary mt-1">{(resultsData.dfs_stats.hui_found || 0).toLocaleString()}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-3 border border-border-muted text-center">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Layer 1 Pruned</span>
                  <p className="text-lg font-extrabold text-text-primary mt-1">{(resultsData.dfs_stats.pruned_layer1 || 0).toLocaleString()}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-3 border border-border-muted text-center">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Layer 2 Pruned</span>
                  <p className="text-lg font-extrabold text-text-primary mt-1">{(resultsData.dfs_stats.pruned_layer2_ub || 0).toLocaleString()}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-3 border border-border-muted text-center">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Empty Joins</span>
                  <p className="text-lg font-extrabold text-text-secondary mt-1">{(resultsData.dfs_stats.empty_join || 0).toLocaleString()}</p>
                </div>
                <div className="bg-bg-card rounded-lg p-3 border border-border-muted text-center">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">Depth Limited</span>
                  <p className="text-lg font-extrabold text-text-secondary mt-1">{(resultsData.dfs_stats.pruned_depth || 0).toLocaleString()}</p>
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Top Patterns Table */}
            <div className="lg:col-span-2 rounded-lg border border-border-default bg-bg-surface overflow-hidden">
              <div className="px-5 py-4 border-b border-border-default flex items-center justify-between">
                <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-text-secondary" />
                  Top Patterns Found
                </h2>
                <span className="text-[11px] text-text-muted bg-bg-muted px-2 py-0.5 rounded">Ranked by Average Utility</span>
              </div>

              {!resultsData.top_results || resultsData.top_results.length === 0 ? (
                <div className="py-12 flex flex-col items-center justify-center text-text-muted text-xs">
                  <CheckCircle2 className="w-8 h-8 text-border-default mb-3" />
                  No high-utility patterns survived the threshold. Try decreasing K or lowering min_util.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-text-muted uppercase tracking-wider border-b border-border-default bg-bg-card text-left">
                        <th className="px-5 py-3 font-medium w-[70px]">Rank</th>
                        <th className="px-5 py-3 font-medium">Pattern (Items)</th>
                        <th className="px-5 py-3 font-medium text-right">Avg Utility</th>
                        <th className="px-5 py-3 font-medium text-right">Batches Seen</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-muted">
                      {resultsData.top_results.map((r, i) => (
                        <tr key={i} className="hover:bg-bg-card transition-colors">
                          <td className="px-5 py-3 text-text-muted font-bold">#{i + 1}</td>
                          <td className="px-5 py-3 font-mono text-text-primary">
                            {r.pattern.split(',').map((it, idx) => (
                              <span key={idx} className="inline-block bg-bg-muted text-text-primary px-2 py-0.5 rounded mr-1.5">
                                {it}
                              </span>
                            ))}
                          </td>
                          <td className="px-5 py-3 font-mono text-text-primary text-right font-bold">
                            {r.avg_util}
                          </td>
                          <td className="px-5 py-3 font-mono text-text-secondary text-right">
                            {r.count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Performance Breakdown */}
            <div className="rounded-lg border border-border-default bg-bg-surface p-5">
              <h2 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-text-secondary" />
                Performance Breakdown
              </h2>
              
              <div className="space-y-4">
                {Object.entries(resultsData.timings || {}).map(([phase, ms]) => {
                  const totalMs = Object.values(resultsData.timings || {}).reduce((a, b) => a + b, 0);
                  const percent = totalMs > 0 ? (ms / totalMs) * 100 : 0;
                  const label = phase
                    .replace('_ms', '')
                    .replace('phase', 'Phase ')
                    .replace('1', '1: Window')
                    .replace('2', '2: Utility')
                    .replace('3', '3: HDkT')
                    .replace('4', '4: DFS Miner')
                    .replace('5', '5: Validation');

                  return (
                    <div key={phase} className="space-y-1.5">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-text-secondary">{label}</span>
                        <span className="text-text-primary font-mono">{ms.toFixed(1)} ms</span>
                      </div>
                      <div className="h-2 bg-bg-muted rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-text-primary rounded-full" 
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-8 pt-5 border-t border-border-default">
                <button
                  id="resetResultsBtn"
                  onClick={() => { setViewState('input'); setResultsData(null); setParsedDataset(null); }}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-lg border border-border-default hover:bg-bg-card text-text-primary text-xs font-bold transition-colors cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Run Another Dataset
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-lg bg-accent text-white px-5 py-3 text-sm font-medium shadow-lg">
          {toast.msg}
        </div>
      )}
    </div>
  );
}
