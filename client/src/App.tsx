import type { CSSProperties } from 'react';
import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';

type AppConfig = {
  client_id: string;
  server_url: string;
  metrics_interval_seconds: number;
};

type RegisterResponse = {
  client_id: string;
  accepted: boolean;
  metrics_interval_seconds: number;
  udp_echo_host: string;
  udp_echo_port: number;
};

type NetworkSnapshot = {
  interface_name?: string | null;
  transmitted_bytes: number;
  received_bytes: number;
  captured_at_unix_ms: number;
};

type ClientStatus = {
  timestamp: string;
  latency_ms?: number | null;
  jitter_ms?: number | null;
  packet_loss_percent: number;
  tx_mbps: number;
  rx_mbps: number;
  server_reachable: boolean;
  local_ip?: string | null;
  interface_name?: string | null;
  next_snapshot: NetworkSnapshot;
};

function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [draftServerUrl, setDraftServerUrl] = useState('http://localhost:8080');
  const [registration, setRegistration] = useState<RegisterResponse | null>(null);
  const [status, setStatus] = useState<ClientStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const previousSnapshotRef = useRef<NetworkSnapshot | null>(null);

  useEffect(() => {
    invoke<AppConfig>('load_config')
      .then((loaded) => {
        setConfig(loaded);
        setDraftServerUrl(loaded.server_url || 'http://localhost:8080');
      })
      .catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!config || !registration) {
      return;
    }

    let cancelled = false;
    let timer = 0;

    const run = async () => {
      try {
        const nextStatus = await invoke<ClientStatus>('report_metrics', {
          config,
          udpHost: registration.udp_echo_host,
          udpPort: registration.udp_echo_port,
          previousSnapshot: previousSnapshotRef.current,
        });
        if (!cancelled) {
          previousSnapshotRef.current = nextStatus.next_snapshot;
          setStatus(nextStatus);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(String(err));
        }
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(run, config.metrics_interval_seconds * 1000);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [config, registration]);

  async function handleConnect() {
    if (!config) {
      return;
    }

    setBusy(true);
    try {
      const nextConfig = {
        ...config,
        server_url: draftServerUrl.trim(),
      };
      const saved = await invoke<AppConfig>('save_config', { config: nextConfig });
      const registered = await invoke<RegisterResponse>('register_client', { config: saved });
      const syncedConfig = {
        ...saved,
        metrics_interval_seconds: registered.metrics_interval_seconds,
      };
      await invoke<AppConfig>('save_config', { config: syncedConfig });
      setConfig(syncedConfig);
      setRegistration(registered);
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={shellStyle}>
      <div style={cardStyle}>
        <p style={eyebrowStyle}>LAN Pulse Client</p>
        <h1 style={{ marginTop: 0 }}>Desktop Monitor Agent</h1>
        <p style={{ color: '#546579', lineHeight: 1.6 }}>
          Register this machine with the LAN Pulse server and keep the window open during the event to continue reporting
          latency, jitter, packet loss, and throughput.
        </p>

        <label style={labelStyle}>
          Server URL
          <input
            value={draftServerUrl}
            onChange={(event) => setDraftServerUrl(event.target.value)}
            placeholder="http://192.168.1.10:8080"
            style={inputStyle}
          />
        </label>

        <button onClick={handleConnect} disabled={busy} style={buttonStyle}>
          {busy ? 'Connecting…' : 'Save and Connect'}
        </button>

        {config ? (
          <div style={gridStyle}>
            <StatusTile label="Client ID" value={config.client_id} />
            <StatusTile label="Connection" value={registration ? 'Connected' : 'Waiting'} />
            <StatusTile label="Last Latency" value={status?.latency_ms ? `${status.latency_ms.toFixed(1)} ms` : 'N/A'} />
            <StatusTile label="Packet Loss" value={status ? `${status.packet_loss_percent.toFixed(1)} %` : 'N/A'} />
            <StatusTile label="Upload" value={status ? `${status.tx_mbps.toFixed(2)} Mbps` : 'N/A'} />
            <StatusTile label="Download" value={status ? `${status.rx_mbps.toFixed(2)} Mbps` : 'N/A'} />
          </div>
        ) : null}

        <div style={detailsStyle}>
          <p>
            <strong>Server:</strong> {config?.server_url || draftServerUrl}
          </p>
          <p>
            <strong>Last Report:</strong> {status ? new Date(status.timestamp).toLocaleTimeString() : 'No data yet'}
          </p>
          <p>
            <strong>Interface:</strong> {status?.interface_name ?? 'Unknown'}
          </p>
          <p>
            <strong>IP Address:</strong> {status?.local_ip ?? 'Unknown'}
          </p>
        </div>

        {error ? <p style={{ color: '#c23838', marginBottom: 0 }}>{error}</p> : null}
      </div>
    </div>
  );
}

function StatusTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={tileStyle}>
      <span style={{ color: '#5e7188', fontSize: 14 }}>{label}</span>
      <strong style={{ fontSize: 16 }}>{value}</strong>
    </div>
  );
}

const shellStyle: CSSProperties = {
  minHeight: '100vh',
  padding: 24,
  background: 'linear-gradient(180deg, #eef5ff 0%, #f7fbff 100%)',
  fontFamily: '"Segoe UI", sans-serif',
  color: '#152235',
};

const cardStyle: CSSProperties = {
  maxWidth: 900,
  margin: '0 auto',
  padding: 28,
  borderRadius: 24,
  background: 'rgba(255,255,255,0.92)',
  boxShadow: '0 18px 42px rgba(17, 49, 84, 0.1)',
  border: '1px solid rgba(94, 119, 156, 0.18)',
};

const eyebrowStyle: CSSProperties = {
  margin: 0,
  textTransform: 'uppercase',
  letterSpacing: '0.14em',
  color: '#2f7cf6',
  fontSize: 12,
  fontWeight: 700,
};

const labelStyle: CSSProperties = {
  display: 'grid',
  gap: 8,
  marginTop: 20,
  fontWeight: 600,
};

const inputStyle: CSSProperties = {
  padding: '12px 14px',
  borderRadius: 14,
  border: '1px solid #c7d4e7',
  fontSize: 16,
};

const buttonStyle: CSSProperties = {
  marginTop: 16,
  padding: '12px 18px',
  borderRadius: 14,
  border: 'none',
  background: '#122033',
  color: 'white',
  fontSize: 16,
  fontWeight: 700,
  cursor: 'pointer',
};

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: 14,
  marginTop: 24,
};

const tileStyle: CSSProperties = {
  display: 'grid',
  gap: 6,
  padding: 16,
  borderRadius: 18,
  background: '#f5f9ff',
};

const detailsStyle: CSSProperties = {
  marginTop: 24,
  color: '#43566d',
};

export default App;
