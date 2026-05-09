import { useCallback } from 'react';
import { api } from '../api';
import { usePollingResource } from '../hooks';

function DownloadPage() {
  const { data, error, loading } = usePollingResource(useCallback(() => api.config(), []), 15000);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Deployment</p>
          <h2>Windows Client Download</h2>
        </div>
      </div>
      {loading && !data ? <p>Loading download info…</p> : null}
      {error ? <p>Unable to load download info: {error}</p> : null}
      {data ? (
        <div className="download-card">
          <p>
            Install the latest desktop client on each player machine, then point it at <code>{window.location.origin}</code>.
          </p>
          <dl className="detail-grid">
            <div>
              <dt>Server Name</dt>
              <dd>{data.server_name}</dd>
            </div>
            <div>
              <dt>Metrics Interval</dt>
              <dd>{data.metrics_interval_seconds} seconds</dd>
            </div>
            <div>
              <dt>UDP Echo Port</dt>
              <dd>{data.udp_echo_port}</dd>
            </div>
            <div>
              <dt>Minimum Client Version</dt>
              <dd>{data.client_min_version}</dd>
            </div>
          </dl>
          <a className="download-button" href="/downloads/client/latest">
            Download Windows Client
          </a>
          <ol className="install-list">
            <li>Download and install the client on the target PC.</li>
            <li>Launch the app and confirm the server URL.</li>
            <li>Keep the client open during the event so metrics continue uploading.</li>
          </ol>
        </div>
      ) : null}
    </section>
  );
}

export default DownloadPage;
