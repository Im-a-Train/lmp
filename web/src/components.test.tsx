import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { ClientTable, HealthBadge, formatMetric } from './components';

describe('components', () => {
  it('formats numeric metrics consistently', () => {
    expect(formatMetric(12.345, 'ms')).toBe('12.3 ms');
    expect(formatMetric(null, 'ms')).toBe('N/A');
  });

  it('renders health badges', () => {
    render(<HealthBadge health="green" />);
    expect(screen.getByText('green')).toBeInTheDocument();
  });

  it('renders the client table rows', () => {
    render(
      <BrowserRouter>
        <ClientTable
          clients={[
            {
              client_id: 'abc',
              hostname: 'PC-01',
              username: 'alex',
              os: 'Windows 11',
              client_version: '0.1.0',
              local_ip: '192.168.1.100',
              interface_name: 'Ethernet',
              online: true,
              last_seen: '2026-05-09T20:15:00Z',
              latency_ms: 1.2,
              jitter_ms: 0.4,
              packet_loss_percent: 0,
              tx_mbps: 10.5,
              rx_mbps: 22.7,
              health: 'green',
            },
          ]}
        />
      </BrowserRouter>
    );
    expect(screen.getByText('PC-01')).toBeInTheDocument();
    expect(screen.getByText('Ethernet')).toBeInTheDocument();
  });
});
