import { Loader2 } from 'lucide-react';

export default function LoadingSpinner({ message = 'Loading…' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
      <Loader2 className="w-8 h-8 text-primary-400 animate-spin mb-3" />
      <p className="text-sm text-text-muted">{message}</p>
    </div>
  );
}
