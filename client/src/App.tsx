import type { CSSProperties } from 'react';
import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

type AppConfig = {
  client_id: string;
  server_url: string;
  metrics_interval_seconds: number;
  username?: string | null;
};

type RegisterResponse = {
  client_id: string;
  accepted: boolean;
  metrics_interval_seconds: number;
  udp_echo_host: string;
  udp_echo_port: number;
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
};

type DiscoveredServer = {
  name: string;
  url: string;
};

function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [draftServerUrl, setDraftServerUrl] = useState('http://localhost:8080');
  const [draftUsername, setDraftUsername] = useState('');
  const [registration, setRegistration] = useState<RegisterResponse | null>(null);
  const [monitoring, setMonitoring] = useState(false);
  const [status, setStatus] = useState<ClientStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [discovered, setDiscovered] = useState<DiscoveredServer[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const unlistenRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    invoke<AppConfig>('load_config')
      .then((loaded) => {
        setConfig(loaded);
        setDraftServerUrl(loaded.server_url || 'http://localhost:8080');
        setDraftUsername(loaded.username || '');
      })
      .catch((err) => setError(String(err)));
  }, []);

  // Listen to metric updates emitted by the Rust monitoring loop
  useEffect(() => {
    let active = true;
    listen<ClientStatus>('metric_update', (event) => {
      if (active) {
        setStatus(event.payload);
        setError(null);
      }
    }).then((unlisten) => {
      unlistenRef.current = unlisten;
    });
    return () => {
      active = false;
      unlistenRef.current?.();
    };
  }, []);

  async function handleConnect() {
    if (!config) return;
    setBusy(true);
    try {
      const nextConfig: AppConfig = {
        ...config,
        server_url: draftServerUrl.trim(),
        username: draftUsername.trim() || null,
      };
      const saved = await invoke<AppConfig>('save_config', { config: nextConfig });
      const registered = await invoke<RegisterResponse>('register_client', { config: saved });
      const syncedConfig: AppConfig = {
        ...saved,
        metrics_interval_seconds: registered.metrics_interval_seconds,
      };
      await invoke<AppConfig>('save_config', { config: syncedConfig });
      setConfig(syncedConfig);
      setRegistration(registered);
      await invoke('start_monitoring', {
        config: syncedConfig,
        udpHost: registered.udp_echo_host,
        udpPort: registered.udp_echo_port,
      });
      setMonitoring(true);
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisconnect() {
    try {
      await invoke('stop_monitoring');
    } catch {
      // best-effort
    }
    setMonitoring(false);
    setRegistration(null);
    setStatus(null);
  }

  async function handleDiscover() {
    setDiscovering(true);
    setDiscovered([]);
    try {
      const found = await invoke<DiscoveredServer[]>('discover_servers');
      setDiscovered(found);
      if (found.length === 0) setError('No servers found on the network.');
    } catch (err) {
      setError(String(err));
    } finally {
      setDiscovering(false);
    }
  }

  return (
    <div style={shellStyle}>
      <div style={cardStyle}>
        <p style={eyebrowStyle}>LAN Pulse Client</p>
        <h1 style={{ marginTop: 0 }}>Desktop Monitor Agent</h1>
        <p style={{ color: '#546579', lineHeight: 1.6 }}>
          Register this machine with the LAN Pulse server and keep the window open during the event to
          continue reporting latency, jitter, packet loss, and throughput.
        </p>

        <label style={labelStyle}>
          Username (optional)
          <input
            value={draftUsername}
            onChange={(e) => setDraftUsername(e.target.value)}
            placeholder="Leave blank to use system username"
            style={inputStyle}
            disabled={monitoring}
          />
        </label>

        <label style={labelStyle}>
          Server URL
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={draftServerUrl}
              onChange={(e) => setDraftServerUrl(e.target.value)}
              placeholder="http://192.168.1.10:8080"
              style={{ ...inputStyle, flex: 1 }}
              disabled={monitoring}
            />
            <button
              onClick={handleDiscover}
              disabled={discovering || monitoring}
              style={secondaryButtonStyle}
              title="Discover servers on this network"
            >
              {discovering ? 'Scanning…' : 'Discover'}
            </button>
          </div>
        </label>

        {discovered.length > 0 && (
          <div style={discoveryListStyle}>
            {discovered.map((s) => (
              <button
                key={s.url}
                style={discoveryItemStyle}
                onClick={() => {
                  setDraftServerUrl(s.url);
                  setDiscovered([]);
                }}
              >
                <span style={{ fontWeight: 600 }}>{s.name}</span>
                <span style={{ color: '#546579', fontSize: 13 }}>{s.url}</span>
              </button>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
          <button onClick={handleConnect} disabled={busy || monitoring} style={buttonStyle}>
            {busy ? 'Connecting…' : 'Save and Connect'}
          </button>
          {monitoring && (
            <button onClick={handleDisconnect} style={disconnectButtonStyle}>
              Disconnect
            </button>
          )}
        </div>

        {config ? (
          <div style={gridStyle}>
            <StatusTile label="Client ID" value={config.client_id.slice(0, 8) + '…'} />
            <StatusTile
              label="Connection"
              value={monitoring ? 'Connected' : 'Disconnected'}
              accent={monitoring ? '#22c55e' : '#94a3b8'}
            />
            <StatusTile
              label="Last Latency"
              value={status?.latency_ms != null ? `${status.latency_ms.toFixed(1)} ms` : 'N/A'}
            />
            <StatusTile
              label="Packet Loss"
              value={status ? `${status.packet_loss_percent.toFixed(1)} %` : 'N/A'}
            />
            <StatusTile label="Upload" value={status ? `${status.tx_mbps.toFixed(2)} Mbps` : 'N/A'} />
            <StatusTile label="Download" value={status ? `${status.rx_mbps.toFixed(2)} Mbps` : 'N/A'} />
          </div>
        ) : null}

        <div style={detailsStyle}>
          <p>
            <strong>Server:</strong> {config?.server_url || draftServerUrl}
          </p>
          <p>
            <strong>Last Report:</strong>{' '}
            {status ? new Date(status.timestamp).toLocaleTimeString() : 'No data yet'}
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

function StatusTile({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div style={tileStyle}>
      <span style={{ color: '#5e7188', fontSize: 14 }}>{label}</span>
      <strong style={{ fontSize: 16, color: accent }}>{value}</strong>
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
  marginTop: 0,
  padding: '12px 18px',
  borderRadius: 14,
  border: 'none',
  background: '#122033',
  color: 'white',
  fontSize: 16,
  fontWeight: 700,
  cursor: 'pointer',
};

const secondaryButtonStyle: CSSProperties = {
  padding: '12px 16px',
  borderRadius: 14,
  border: '1px solid #c7d4e7',
  background: 'white',
  color: '#122033',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
};

const disconnectButtonStyle: CSSProperties = {
  marginTop: 0,
  padding: '12px 18px',
  borderRadius: 14,
  border: '1px solid #e9b8b8',
  background: '#fff5f5',
  color: '#c23838',
  fontSize: 16,
  fontWeight: 700,
  cursor: 'pointer',
};

const discoveryListStyle: CSSProperties = {
  marginTop: 8,
  border: '1px solid #c7d4e7',
  borderRadius: 14,
  overflow: 'hidden',
};

const discoveryItemStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
  width: '100%',
  padding: '10px 14px',
  border: 'none',
  borderBottom: '1px solid #e8eef7',
  background: 'white',
  textAlign: 'left',
  cursor: 'pointer',
  fontSize: 14,
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
