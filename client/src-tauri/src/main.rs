#![cfg_attr(all(not(debug_assertions), target_os = "windows"), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use chrono::Utc;
use futures_util::SinkExt;
use local_ip_address::local_ip;
use serde::{Deserialize, Serialize};
use sysinfo::Networks;
use tauri::{AppHandle, Builder, Emitter, Manager};
use tokio::net::UdpSocket;
use tokio::sync::Mutex;
use tokio::task::JoinHandle;
use tokio::time::timeout;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use uuid::Uuid;

// ── Config ──────────────────────────────────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
struct AppConfig {
    client_id: String,
    server_url: String,
    metrics_interval_seconds: u64,
    #[serde(default)]
    username: Option<String>,
}

// ── Data types ───────────────────────────────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ClientInfo {
    hostname: String,
    username: String,
    os: String,
    local_ip: Option<String>,
    interface_name: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct RegisterResponse {
    client_id: String,
    accepted: bool,
    metrics_interval_seconds: u64,
    udp_echo_host: String,
    udp_echo_port: u16,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct NetworkSnapshot {
    interface_name: Option<String>,
    transmitted_bytes: u64,
    received_bytes: u64,
    captured_at_unix_ms: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ClientStatus {
    timestamp: String,
    latency_ms: Option<f64>,
    jitter_ms: Option<f64>,
    packet_loss_percent: f64,
    tx_mbps: f64,
    rx_mbps: f64,
    server_reachable: bool,
    local_ip: Option<String>,
    interface_name: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct DiscoveredServer {
    name: String,
    url: String,
}

// ── Monitoring state ─────────────────────────────────────────────────────────

struct MonitoringState {
    handle: Arc<Mutex<Option<JoinHandle<()>>>>,
}

impl MonitoringState {
    fn new() -> Self {
        MonitoringState {
            handle: Arc::new(Mutex::new(None)),
        }
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

fn config_path(app: &AppHandle) -> Result<PathBuf, String> {
    let base_dir = app
        .path()
        .app_data_dir()
        .map_err(|err| format!("Unable to resolve app data directory: {err}"))?;
    fs::create_dir_all(&base_dir).map_err(|err| format!("Unable to create app data directory: {err}"))?;
    Ok(base_dir.join("config.json"))
}

fn default_config() -> AppConfig {
    AppConfig {
        client_id: Uuid::new_v4().to_string(),
        server_url: String::new(),
        metrics_interval_seconds: 2,
        username: None,
    }
}

fn compute_jitter(samples: &[f64]) -> Option<f64> {
    if samples.len() < 2 {
        return None;
    }
    let total: f64 = samples.windows(2).map(|p| (p[1] - p[0]).abs()).sum();
    Some(total / (samples.len() - 1) as f64)
}

fn derive_bandwidth(previous: &Option<NetworkSnapshot>, next: &NetworkSnapshot) -> (f64, f64) {
    let Some(prev) = previous else {
        return (0.0, 0.0);
    };
    let elapsed_ms = (next.captured_at_unix_ms - prev.captured_at_unix_ms).max(1) as f64;
    let tx_delta = next.transmitted_bytes.saturating_sub(prev.transmitted_bytes) as f64;
    let rx_delta = next.received_bytes.saturating_sub(prev.received_bytes) as f64;
    let tx_mbps = (tx_delta * 8.0) / elapsed_ms / 1000.0;
    let rx_mbps = (rx_delta * 8.0) / elapsed_ms / 1000.0;
    (tx_mbps, rx_mbps)
}

fn current_network_snapshot() -> NetworkSnapshot {
    let mut networks = Networks::new_with_refreshed_list();
    networks.refresh(true);
    let chosen = networks
        .iter()
        .max_by_key(|(_, data)| data.total_received() + data.total_transmitted());
    if let Some((name, data)) = chosen {
        NetworkSnapshot {
            interface_name: Some(name.to_string()),
            transmitted_bytes: data.total_transmitted(),
            received_bytes: data.total_received(),
            captured_at_unix_ms: Utc::now().timestamp_millis(),
        }
    } else {
        NetworkSnapshot {
            interface_name: None,
            transmitted_bytes: 0,
            received_bytes: 0,
            captured_at_unix_ms: Utc::now().timestamp_millis(),
        }
    }
}

async fn udp_measurement(host: &str, port: u16, client_id: &str) -> (Vec<f64>, f64) {
    let socket = match UdpSocket::bind("0.0.0.0:0").await {
        Ok(s) => s,
        Err(_) => return (Vec::new(), 100.0),
    };
    let target = format!("{host}:{port}");
    let packets = 10usize;
    let mut latencies = Vec::new();
    let mut received = 0usize;

    for seq in 0..packets {
        let payload = serde_json::json!({
            "client_id": client_id,
            "seq": seq,
            "sent_at_unix_ms": Utc::now().timestamp_millis(),
        });
        let start = Instant::now();
        if socket.send_to(payload.to_string().as_bytes(), &target).await.is_err() {
            continue;
        }
        let mut buf = [0_u8; 1024];
        if timeout(Duration::from_millis(400), socket.recv_from(&mut buf)).await.is_ok() {
            received += 1;
            latencies.push(start.elapsed().as_secs_f64() * 1000.0);
        }
    }

    let loss = ((packets.saturating_sub(received)) as f64 / packets as f64) * 100.0;
    (latencies, loss)
}

fn ws_url(server_url: &str, path: &str) -> String {
    let base = server_url
        .trim_end_matches('/')
        .replace("https://", "wss://")
        .replace("http://", "ws://");
    format!("{base}{path}")
}

// ── Background monitoring loop ────────────────────────────────────────────────

async fn monitoring_loop(app: AppHandle, config: AppConfig, udp_host: String, udp_port: u16) {
    let url = ws_url(&config.server_url, "/ws/client");
    let mut previous_snapshot: Option<NetworkSnapshot> = None;

    loop {
        match connect_async(&url).await {
            Ok((ws_stream, _)) => {
                let (mut write, _read) = futures_util::StreamExt::split(ws_stream);

                loop {
                    let snapshot = current_network_snapshot();
                    let (latencies, loss) = udp_measurement(&udp_host, udp_port, &config.client_id).await;
                    let latency_ms = if latencies.is_empty() {
                        None
                    } else {
                        Some(latencies.iter().sum::<f64>() / latencies.len() as f64)
                    };
                    let jitter_ms = compute_jitter(&latencies);
                    let (tx_mbps, rx_mbps) = derive_bandwidth(&previous_snapshot, &snapshot);
                    let ip = local_ip().ok().map(|ip| ip.to_string());

                    let payload = serde_json::json!({
                        "client_id": config.client_id,
                        "timestamp": Utc::now(),
                        "latency_ms": latency_ms,
                        "jitter_ms": jitter_ms,
                        "packet_loss_percent": loss,
                        "tx_mbps": tx_mbps,
                        "rx_mbps": rx_mbps,
                        "server_reachable": loss < 100.0,
                        "game_server_latency_ms": serde_json::Value::Null,
                        "game_server_packet_loss_percent": serde_json::Value::Null,
                        "local_ip": ip,
                        "interface_name": snapshot.interface_name,
                    });

                    let status = ClientStatus {
                        timestamp: Utc::now().to_rfc3339(),
                        latency_ms,
                        jitter_ms,
                        packet_loss_percent: loss,
                        tx_mbps,
                        rx_mbps,
                        server_reachable: loss < 100.0,
                        local_ip: ip,
                        interface_name: snapshot.interface_name.clone(),
                    };

                    let _ = app.emit("metric_update", &status);

                    if write.send(Message::Text(payload.to_string().into())).await.is_err() {
                        break; // reconnect
                    }

                    previous_snapshot = Some(snapshot);
                    tokio::time::sleep(Duration::from_secs(config.metrics_interval_seconds)).await;
                }
            }
            Err(_) => {
                // Server not reachable yet — wait before retrying
                tokio::time::sleep(Duration::from_secs(5)).await;
            }
        }
    }
}

// ── Tauri commands ────────────────────────────────────────────────────────────

#[tauri::command]
fn load_config(app: AppHandle) -> Result<AppConfig, String> {
    let path = config_path(&app)?;
    if !path.exists() {
        return Ok(default_config());
    }
    let contents = fs::read_to_string(path).map_err(|e| format!("Unable to read config: {e}"))?;
    serde_json::from_str(&contents).map_err(|e| format!("Unable to parse config: {e}"))
}

#[tauri::command]
fn save_config(app: AppHandle, config: AppConfig) -> Result<AppConfig, String> {
    let path = config_path(&app)?;
    let contents = serde_json::to_string_pretty(&config).map_err(|e| format!("Unable to encode config: {e}"))?;
    fs::write(path, contents).map_err(|e| format!("Unable to save config: {e}"))?;
    Ok(config)
}

#[tauri::command]
fn get_client_info() -> ClientInfo {
    let hostname = sysinfo::System::host_name().unwrap_or_else(|| "unknown-host".to_string());
    let os = sysinfo::System::long_os_version().unwrap_or_else(|| "Unknown OS".to_string());
    let username = std::env::var("USERNAME")
        .or_else(|_| std::env::var("USER"))
        .unwrap_or_else(|_| "unknown".to_string());
    let snapshot = current_network_snapshot();
    ClientInfo {
        hostname,
        username,
        os,
        local_ip: local_ip().ok().map(|ip| ip.to_string()),
        interface_name: snapshot.interface_name,
    }
}

#[tauri::command]
async fn register_client(config: AppConfig) -> Result<RegisterResponse, String> {
    let info = get_client_info();
    let effective_username = config
        .username
        .clone()
        .filter(|u| !u.trim().is_empty())
        .unwrap_or(info.username);

    let payload = serde_json::json!({
        "client_id": config.client_id,
        "hostname": info.hostname,
        "username": effective_username,
        "os": info.os,
        "client_version": env!("CARGO_PKG_VERSION"),
        "local_ip": info.local_ip,
        "interface_name": info.interface_name,
    });

    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/clients/register", config.server_url.trim_end_matches('/')))
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Request failed: {e}"))?;

    if !response.status().is_success() {
        return Err(format!("Server returned {}", response.status()));
    }

    response.json::<RegisterResponse>().await.map_err(|e| format!("Invalid response body: {e}"))
}

#[tauri::command]
async fn start_monitoring(
    app: AppHandle,
    state: tauri::State<'_, MonitoringState>,
    config: AppConfig,
    udp_host: String,
    udp_port: u16,
) -> Result<(), String> {
    let mut guard = state.handle.lock().await;
    if let Some(existing) = guard.take() {
        existing.abort();
    }
    let handle = tauri::async_runtime::spawn(monitoring_loop(app, config, udp_host, udp_port));
    *guard = Some(handle);
    Ok(())
}

#[tauri::command]
async fn stop_monitoring(state: tauri::State<'_, MonitoringState>) -> Result<(), String> {
    let mut guard = state.handle.lock().await;
    if let Some(handle) = guard.take() {
        handle.abort();
    }
    Ok(())
}

#[tauri::command]
async fn discover_servers() -> Result<Vec<DiscoveredServer>, String> {
    tokio::task::spawn_blocking(|| -> Result<Vec<DiscoveredServer>, String> {
        use mdns_sd::{ServiceDaemon, ServiceEvent};

        let mdns = ServiceDaemon::new().map_err(|e| e.to_string())?;
        let receiver = mdns.browse("_lpm._tcp.local.").map_err(|e| e.to_string())?;

        let mut servers: Vec<DiscoveredServer> = Vec::new();
        let deadline = Instant::now() + Duration::from_secs(3);

        while Instant::now() < deadline {
            match receiver.try_recv() {
                Ok(ServiceEvent::ServiceResolved(info)) => {
                    let name = info.get_hostname().trim_end_matches('.').to_string();
                    for addr in info.get_addresses() {
                        let url = format!("http://{}:{}", addr, info.get_port());
                        if !servers.iter().any(|s: &DiscoveredServer| s.url == url) {
                            servers.push(DiscoveredServer { name: name.clone(), url });
                        }
                    }
                }
                Ok(_) | Err(_) => {
                    std::thread::sleep(Duration::from_millis(100));
                }
            }
        }

        mdns.shutdown().ok();
        Ok(servers)
    })
    .await
    .map_err(|e| e.to_string())?
}

// ── Entry point ───────────────────────────────────────────────────────────────

fn main() {
    Builder::default()
        .manage(MonitoringState::new())
        .invoke_handler(tauri::generate_handler![
            load_config,
            save_config,
            get_client_info,
            register_client,
            start_monitoring,
            stop_monitoring,
            discover_servers,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::{compute_jitter, derive_bandwidth, NetworkSnapshot};

    #[test]
    fn computes_average_jitter() {
        let jitter = compute_jitter(&[2.0, 4.0, 7.0, 8.0]).expect("jitter should exist");
        assert!((jitter - 2.0).abs() < 0.0001);
    }

    #[test]
    fn computes_bandwidth_from_network_deltas() {
        let previous = Some(NetworkSnapshot {
            interface_name: Some("eth0".to_string()),
            transmitted_bytes: 1_000,
            received_bytes: 2_000,
            captured_at_unix_ms: 1000,
        });
        let next = NetworkSnapshot {
            interface_name: Some("eth0".to_string()),
            transmitted_bytes: 3_000,
            received_bytes: 6_000,
            captured_at_unix_ms: 2000,
        };
        let (tx, rx) = derive_bandwidth(&previous, &next);
        assert!(tx > 0.0);
        assert!(rx > tx);
    }
}
