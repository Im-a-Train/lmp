import { useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';
import { EventList, HealthBadge, MetricsCharts } from '../components';
import { usePollingResource } from '../hooks';

function ClientDetailPage() {
  const { clientId } = useParams();
  const loader = useCallback(() => api.clientDetail(clientId ?? ''), [clientId]);
  const { data, error, loading } = usePollingResource(loader, 6000);

  if (!clientId) {
    return <section className="panel">Client ID is missing.</section>;
  }

  if (loading && !data) {
    return <section className="panel">Loading client detail…</section>;
  }

  if (error || !data) {
    return <section className="panel">Unable to load client detail: {error}</section>;
  }

  return (
    <div className="page-grid">
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Client Detail</p>
            <h2>{data.client.hostname}</h2>
          </div>
          <HealthBadge health={data.client.health} />
        </div>
        <dl className="detail-grid">
          <div>
            <dt>Username</dt>
            <dd>{data.client.username ?? 'Unknown'}</dd>
          </div>
          <div>
            <dt>Operating System</dt>
            <dd>{data.client.os ?? 'Unknown'}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{data.client.client_version ?? 'Unknown'}</dd>
          </div>
          <div>
            <dt>IP Address</dt>
            <dd>{data.client.local_ip ?? 'Unknown'}</dd>
          </div>
          <div>
            <dt>Interface</dt>
            <dd>{data.client.interface_name ?? 'Unknown'}</dd>
          </div>
          <div>
            <dt>Last Seen</dt>
            <dd>{new Date(data.client.last_seen).toLocaleString()}</dd>
          </div>
        </dl>
      </section>

      <MetricsCharts metrics={data.metrics} />
      <EventList events={data.events} />

      <section className="panel">
        <div className="panel-header">
          <h3>Last Submitted Payload</h3>
        </div>
        <pre className="payload-view">{JSON.stringify(data.last_metrics_payload, null, 2)}</pre>
      </section>
    </div>
  );
}

export default ClientDetailPage;
