import type { ReactNode } from 'react';
import { Alert, AlertDescription } from './ui/alert';
export { Button } from './ui/button';

export function Notice({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return (
    <Alert
      variant={error ? 'destructive' : 'default'}
      className="notice"
      role={error ? 'alert' : undefined}
    >
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

export function formatBytes(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1).replace(/\.0$/, '')} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
