import type { ReactNode } from 'react';

export function Badge({ tone = 'neutral', children }: { tone?: 'success' | 'danger' | 'warning' | 'violet' | 'neutral'; children: ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

