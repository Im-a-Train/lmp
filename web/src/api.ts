export type Health = 'green' | 'yellow' | 'red' | 'offline' | 'unknown';

export type ClientListItem = {
  client_id: string;
  hostname: string;
  username?: string | null;
  os?: string | null;
  client_version?: string | null;
  local_ip?: string | null;
  interface_name?: string | null;
  online: boolean;
  last_seen: string;
  latency_ms?: number | null;
  jitter_ms?: number | null;
  packet_loss_percent?: number | null;
  tx_mbps?: number | null;
  rx_mbps?: number | null;
  health: Health;
};

export type ClientSummary = {
  client_id: string;
  hostname: string;
  username?: string | null;
  local_ip?: string | null;
  health: Health;
  latency_ms?: number | null;
  jitter_ms?: number | null;
  packet_loss_percent?: number | null;
  tx_mbps?: number | null;
  rx_mbps?: number | null;
};

export type DashboardResponse = {
  summary: {
    online_clients: number;
    offline_clients: number;
    global_health: Health;
    worst_latency_clients: ClientSummary[];
    packet_loss_alerts: ClientSummary[];
    jitter_alerts: ClientSummary[];
    top_bandwidth_users: ClientSummary[];
  };
  recent_events: EventItem[];
  generated_at: string;
  window_start: string;
};

export type ClientDetailResponse = {
  client: {
    client_id: string;
    hostname: string;
    username?: string | null;
    os?: string | null;
    client_version?: string | null;
    local_ip?: string | null;
    interface_name?: string | null;
    first_seen: string;
    last_seen: string;
    online: boolean;
    health: Health;
  };
  metrics: MetricPoint[];
  events: EventItem[];
  last_metrics_payload: Record<string, unknown> | null;
};

export type MetricPoint = {
  timestamp: string;
  latency_ms?: number | null;
  jitter_ms?: number | null;
  packet_loss_percent?: number | null;
  tx_mbps?: number | null;
  rx_mbps?: number | null;
  server_reachable: boolean;
};

export type EventItem = {
  id: number;
  ts: string;
  severity: string;
  client_id?: string | null;
  event_type: string;
  message: string;
  data?: Record<string, unknown> | null;
};

export type PublicConfig = {
  server_name: string;
  metrics_interval_seconds: number;
  udp_echo_port: number;
  client_min_version: string;
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => getJson<DashboardResponse>('/api/dashboard/'),
  clients: () => getJson<ClientListItem[]>('/api/clients/'),
  clientDetail: (clientId: string) => getJson<ClientDetailResponse>(`/api/clients/${clientId}`),
  config: () => getJson<PublicConfig>('/api/config'),
};
