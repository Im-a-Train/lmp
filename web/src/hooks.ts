import { useEffect, useState } from 'react';

export function usePollingResource<T>(loader: () => Promise<T>, intervalMs = 5000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        const next = await loader();
        if (!cancelled) {
          setData(next);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    run();
    const timer = window.setInterval(run, intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [loader, intervalMs]);

  return { data, error, loading };
}

export function useDashboardSocket(onMessage: () => void) {
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/dashboard`);

    socket.onmessage = () => {
      onMessage();
    };

    return () => {
      socket.close();
    };
  }, [onMessage]);
}
