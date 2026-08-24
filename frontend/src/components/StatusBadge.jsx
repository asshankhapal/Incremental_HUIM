const styles = {
  queued: 'bg-warning-500/15 text-warning-400 border border-warning-500/20',
  processed: 'bg-success-500/15 text-success-400 border border-success-500/20',
  running: 'bg-info-500/15 text-info-400 border border-info-500/20 animate-pulse-subtle',
  success: 'bg-success-500/15 text-success-400 border border-success-500/20',
  error: 'bg-error-500/15 text-error-400 border border-error-500/20',
  no_data: 'bg-white/5 text-text-muted border border-border-subtle',
};

export default function StatusBadge({ status }) {
  const cls = styles[status] || styles.no_data;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${cls}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}
