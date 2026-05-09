import { Link } from 'react-router-dom';
import type { ClientListItem, ClientSummary, EventItem, Health, MetricPoint } from './api';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export function HealthBadge({ health }: { health: Health }) {
  return <span className={`health-badge health-${health}`}>{health}</span>;
}

export function MetricCard({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: 'neutral' | Health;
}) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

export function ClientTable({ clients }: { clients: ClientListItem[] }) {
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            <th>Client</th>
            <th>Network</th>
            <th>Status</th>
            <th>Latency</th>
            <th>Jitter</th>
            <th>Loss</th>
            <th>Upload</th>
            <th>Download</th>
          </tr>
        </thead>
        <tbody>
          {clients.map((client) => (
            <tr key={client.client_id}>
              <td>
                <Link to={`/clients/${client.client_id}`}>{client.hostname}</Link>
                <span className="cell-subtle">
                  {[client.username, client.os, client.client_version].filter(Boolean).join(' • ')}
                </span>
              </td>
              <td>
                {client.local_ip ?? 'Unknown'}
                <span className="cell-subtle">{client.interface_name ?? 'Interface unavailable'}</span>
              </td>
              <td>
                <HealthBadge health={client.health} />
                <span className="cell-subtle">{client.online ? 'Online' : 'Offline'}</span>
              </td>
              <td>{formatMetric(client.latency_ms, 'ms')}</td>
              <td>{formatMetric(client.jitter_ms, 'ms')}</td>
              <td>{formatMetric(client.packet_loss_percent, '%')}</td>
              <td>{formatMetric(client.tx_mbps, 'Mbps')}</td>
              <td>{formatMetric(client.rx_mbps, 'Mbps')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RankingList({
  title,
  clients,
  metric,
  unit,
}: {
  title: string;
  clients: ClientSummary[];
  metric: keyof ClientSummary;
  unit: string;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h3>{title}</h3>
      </div>
      <ul className="rank-list">
        {clients.length === 0 ? <li>No active alerts.</li> : null}
        {clients.map((client) => (
          <li key={client.client_id}>
            <div>
              <strong>{client.hostname}</strong>
              <span>{client.local_ip ?? 'No IP reported'}</span>
            </div>
            <div>
              <HealthBadge health={client.health} />
              <span>{formatMetric(client[metric] as number | null | undefined, unit)}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function EventList({ events }: { events: EventItem[] }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h3>Recent Events</h3>
      </div>
      <ul className="event-list">
        {events.length === 0 ? <li>No recent events.</li> : null}
        {events.map((event) => (
          <li key={event.id}>
            <span className={`event-dot severity-${event.severity}`} />
            <div>
              <strong>{event.message}</strong>
              <p>
                {new Date(event.ts).toLocaleString()} • {event.event_type}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function MetricsCharts({ metrics }: { metrics: MetricPoint[] }) {
  const chartData = metrics.map((metric) => ({
    time: new Date(metric.timestamp).toLocaleTimeString(),
    latency: metric.latency_ms,
    jitter: metric.jitter_ms,
    loss: metric.packet_loss_percent,
    tx: metric.tx_mbps,
    rx: metric.rx_mbps,
  }));

  return (
    <div className="charts-grid">
      <ChartPanel
        title="Latency and Jitter"
        data={chartData}
        lines={[
          { key: 'latency', color: '#2f7cf6', label: 'Latency ms' },
          { key: 'jitter', color: '#f5a524', label: 'Jitter ms' },
        ]}
      />
      <ChartPanel
        title="Packet Loss"
        data={chartData}
        lines={[{ key: 'loss', color: '#d64545', label: 'Loss %' }]}
      />
      <ChartPanel
        title="Throughput"
        data={chartData}
        lines={[
          { key: 'tx', color: '#0f9d7a', label: 'Upload Mbps' },
          { key: 'rx', color: '#6f56d9', label: 'Download Mbps' },
        ]}
      />
    </div>
  );
}

function ChartPanel({
  title,
  data,
  lines,
}: {
  title: string;
  data: Record<string, number | string | null | undefined>[];
  lines: Array<{ key: string; color: string; label: string }>;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h3>{title}</h3>
      </div>
      <div className="chart-shell">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(150, 160, 180, 0.2)" />
            <XAxis dataKey="time" minTickGap={24} stroke="#60708a" />
            <YAxis stroke="#60708a" />
            <Tooltip />
            <Legend />
            {lines.map((line) => (
              <Line
                key={line.key}
                type="monotone"
                dataKey={line.key}
                name={line.label}
                stroke={line.color}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function formatMetric(value: number | null | undefined, unit: string) {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  return `${value.toFixed(1)} ${unit}`;
}
