import { useCallback } from 'react';
import { api } from '../api';
import { ClientTable } from '../components';
import { usePollingResource } from '../hooks';

function ClientsPage() {
  const { data, error, loading } = usePollingResource(useCallback(() => api.clients(), []), 6000);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Fleet</p>
          <h2>Connected Clients</h2>
        </div>
      </div>
      {loading && !data ? <p>Loading clients…</p> : null}
      {error ? <p>Unable to load clients: {error}</p> : null}
      {data ? <ClientTable clients={data} /> : null}
    </section>
  );
}

export default ClientsPage;
