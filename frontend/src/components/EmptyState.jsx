import { Inbox } from 'lucide-react';

export default function EmptyState({ title = 'No data yet', message = 'Get started by ingesting some transaction data.', icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-bg-muted border border-border-default mb-5">
        <Icon className="w-8 h-8 text-text-muted" />
      </div>
      <h3 className="text-base font-semibold text-text-primary mb-1">{title}</h3>
      <p className="text-sm text-text-muted max-w-sm text-center">{message}</p>
    </div>
  );
}
