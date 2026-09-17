export default function StatCard({ icon: Icon, label, value, subtitle }) {
  return (
    <div className="rounded-lg border border-border-default bg-bg-surface p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">{label}</p>
          <p className="text-2xl font-bold text-text-primary">{value ?? '—'}</p>
          {subtitle && (
            <p className="text-xs text-text-secondary mt-1">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-bg-muted">
            <Icon className="w-5 h-5 text-text-secondary" />
          </div>
        )}
      </div>
    </div>
  );
}
