import { NavLink, Route, Routes } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import ClientsPage from './pages/ClientsPage';
import ClientDetailPage from './pages/ClientDetailPage';
import DownloadPage from './pages/DownloadPage';

function App() {
  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">LAN Pulse</p>
          <h1>LAN Party Network Quality Monitor</h1>
          <p className="hero-copy">
            Live visibility into latency, jitter, packet loss, and bandwidth across every client on the floor.
          </p>
        </div>
        <nav className="top-nav" aria-label="Primary">
          <NavLink to="/">Dashboard</NavLink>
          <NavLink to="/clients">Clients</NavLink>
          <NavLink to="/download">Download</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/clients/:clientId" element={<ClientDetailPage />} />
          <Route path="/download" element={<DownloadPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
