export default function StatCard({ icon: Icon, label, value, subtitle, color = 'primary' }) {
  const colorMap = {
    primary: 'from-primary-500/20 to-primary-500/5 text-primary-400 border-primary-500/20',
    success: 'from-success-500/20 to-success-500/5 text-success-400 border-success-500/20',
    warning: 'from-warning-500/20 to-warning-500/5 text-warning-400 border-warning-500/20',
    error: 'from-error-500/20 to-error-500/5 text-error-400 border-error-500/20',
    info: 'from-info-500/20 to-info-500/5 text-info-400 border-info-500/20',
  };

  const iconColorMap = {
    primary: 'bg-primary-500/15 text-primary-400',
    success: 'bg-success-500/15 text-success-400',
    warning: 'bg-warning-500/15 text-warning-400',
    error: 'bg-error-500/15 text-error-400',
    info: 'bg-info-500/15 text-info-400',
  };

  return (
    <div
      className={`card-hover glass rounded-xl p-5 bg-gradient-to-br ${colorMap[color]}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">{label}</p>
          <p className="text-2xl font-bold text-text-primary">{value ?? '—'}</p>
          {subtitle && (
            <p className="text-xs text-text-secondary mt-1">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className={`flex items-center justify-center w-10 h-10 rounded-lg ${iconColorMap[color]}`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>
    </div>
  );
}
