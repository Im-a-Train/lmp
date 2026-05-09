import { useCallback, useState } from 'react';
import { api } from '../api';
import { EventList, MetricCard, RankingList } from '../components';
import { useDashboardSocket, usePollingResource } from '../hooks';

function DashboardPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const loader = useCallback(() => api.dashboard(), [refreshKey]);
  const { data, error, loading } = usePollingResource(loader, 8000);

  useDashboardSocket(() => {
    setRefreshKey((current) => current + 1);
  });

  if (loading && !data) {
    return <section className="panel">Loading dashboard…</section>;
  }

  if (error || !data) {
    return <section className="panel">Unable to load dashboard: {error}</section>;
  }

  return (
    <div className="page-grid">
      <section className="metrics-grid">
        <MetricCard label="Global Health" value={data.summary.global_health.toUpperCase()} tone={data.summary.global_health} />
        <MetricCard label="Online Clients" value={String(data.summary.online_clients)} tone="green" />
        <MetricCard label="Offline Clients" value={String(data.summary.offline_clients)} tone={data.summary.offline_clients > 0 ? 'yellow' : 'neutral'} />
        <MetricCard label="Last Snapshot" value={new Date(data.generated_at).toLocaleTimeString()} />
      </section>

      <section className="rankings-grid">
        <RankingList title="Worst Latency" clients={data.summary.worst_latency_clients} metric="latency_ms" unit="ms" />
        <RankingList title="Packet Loss Alerts" clients={data.summary.packet_loss_alerts} metric="packet_loss_percent" unit="%" />
        <RankingList title="Jitter Alerts" clients={data.summary.jitter_alerts} metric="jitter_ms" unit="ms" />
        <RankingList title="Top Bandwidth Users" clients={data.summary.top_bandwidth_users} metric="rx_mbps" unit="Mbps" />
      </section>

      <EventList events={data.recent_events} />
    </div>
  );
}

export default DashboardPage;
