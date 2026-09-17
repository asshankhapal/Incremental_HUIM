const styles = {
  queued: 'bg-bg-muted text-text-secondary',
  processed: 'bg-bg-muted text-text-primary',
  running: 'bg-accent text-white',
  success: 'bg-bg-muted text-text-primary',
  error: 'bg-bg-muted text-text-primary',
  no_data: 'bg-bg-muted text-text-muted',
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
