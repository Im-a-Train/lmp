#![cfg_attr(all(not(debug_assertions), target_os = "windows"), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;
use std::time::{Duration, Instant};

use chrono::Utc;
use local_ip_address::local_ip;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use sysinfo::Networks;
use tauri::{AppHandle, Builder, Manager};
use tokio::net::UdpSocket;
use tokio::time::timeout;
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
struct AppConfig {
    client_id: String,
    server_url: String,
    metrics_interval_seconds: u64,
}

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
    next_snapshot: NetworkSnapshot,
}

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
    }
}

fn compute_jitter(samples: &[f64]) -> Option<f64> {
    if samples.len() < 2 {
        return None;
    }

    let mut deltas = Vec::new();
    for pair in samples.windows(2) {
        deltas.push((pair[1] - pair[0]).abs());
    }

    let total: f64 = deltas.iter().sum();
    Some(total / deltas.len() as f64)
}

fn derive_bandwidth(previous: &Option<NetworkSnapshot>, next: &NetworkSnapshot) -> (f64, f64) {
    let Some(previous_snapshot) = previous else {
        return (0.0, 0.0);
    };

    let elapsed_ms = (next.captured_at_unix_ms - previous_snapshot.captured_at_unix_ms).max(1) as f64;
    let tx_delta = next.transmitted_bytes.saturating_sub(previous_snapshot.transmitted_bytes) as f64;
    let rx_delta = next.received_bytes.saturating_sub(previous_snapshot.received_bytes) as f64;

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
    let bind_addr = "0.0.0.0:0";
    let socket = match UdpSocket::bind(bind_addr).await {
        Ok(socket) => socket,
        Err(_) => return (Vec::new(), 100.0),
    };

    let target = format!("{host}:{port}");
    let mut latencies = Vec::new();
    let packets = 10usize;
    let mut received = 0usize;

    for seq in 0..packets {
        let payload = serde_json::json!({
            "client_id": client_id,
            "seq": seq,
            "sent_at_unix_ms": Utc::now().timestamp_millis(),
        });

        let start = Instant::now();
        if socket
            .send_to(payload.to_string().as_bytes(), &target)
            .await
            .is_err()
        {
            continue;
        }

        let mut buffer = [0_u8; 1024];
        if timeout(Duration::from_millis(400), socket.recv_from(&mut buffer))
            .await
            .is_ok()
        {
            received += 1;
            latencies.push(start.elapsed().as_secs_f64() * 1000.0);
        }
    }

    let loss = ((packets.saturating_sub(received)) as f64 / packets as f64) * 100.0;
    (latencies, loss)
}

async fn post_json<T: Serialize, R: for<'de> Deserialize<'de>>(
    client: &Client,
    url: &str,
    payload: &T,
) -> Result<R, String> {
    let response = client
        .post(url)
        .json(payload)
        .send()
        .await
        .map_err(|err| format!("Request failed: {err}"))?;

    if !response.status().is_success() {
        return Err(format!("Server returned {}", response.status()));
    }

    response
        .json::<R>()
        .await
        .map_err(|err| format!("Invalid response body: {err}"))
}

#[tauri::command]
fn load_config(app: AppHandle) -> Result<AppConfig, String> {
    let path = config_path(&app)?;
    if !path.exists() {
        return Ok(default_config());
    }

    let contents = fs::read_to_string(path).map_err(|err| format!("Unable to read config: {err}"))?;
    serde_json::from_str(&contents).map_err(|err| format!("Unable to parse config: {err}"))
}

#[tauri::command]
fn save_config(app: AppHandle, config: AppConfig) -> Result<AppConfig, String> {
    let path = config_path(&app)?;
    let contents = serde_json::to_string_pretty(&config).map_err(|err| format!("Unable to encode config: {err}"))?;
    fs::write(path, contents).map_err(|err| format!("Unable to save config: {err}"))?;
    Ok(config)
}

#[tauri::command]
fn get_client_info() -> ClientInfo {
    let hostname = SystemInfo::hostname();
    let username = std::env::var("USERNAME")
        .or_else(|_| std::env::var("USER"))
        .unwrap_or_else(|_| "unknown".to_string());
    let os = SystemInfo::os_name();
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
    let payload = serde_json::json!({
        "client_id": config.client_id,
        "hostname": info.hostname,
        "username": info.username,
        "os": info.os,
        "client_version": env!("CARGO_PKG_VERSION"),
        "local_ip": info.local_ip,
        "interface_name": info.interface_name,
    });
    let client = Client::new();
    post_json::<_, RegisterResponse>(
        &client,
        &format!("{}/api/clients/register", config.server_url.trim_end_matches('/')),
        &payload,
    )
    .await
}

#[tauri::command]
async fn report_metrics(
    config: AppConfig,
    udp_host: String,
    udp_port: u16,
    previous_snapshot: Option<NetworkSnapshot>,
) -> Result<ClientStatus, String> {
    let snapshot = current_network_snapshot();
    let (latencies, packet_loss_percent) = udp_measurement(&udp_host, udp_port, &config.client_id).await;
    let latency_ms = if latencies.is_empty() {
        None
    } else {
        Some(latencies.iter().sum::<f64>() / latencies.len() as f64)
    };
    let jitter_ms = compute_jitter(&latencies);
    let (tx_mbps, rx_mbps) = derive_bandwidth(&previous_snapshot, &snapshot);
    let client = Client::new();
    let local_ip = local_ip().ok().map(|ip| ip.to_string());

    let payload = serde_json::json!({
        "client_id": config.client_id,
        "timestamp": Utc::now(),
        "latency_ms": latency_ms,
        "jitter_ms": jitter_ms,
        "packet_loss_percent": packet_loss_percent,
        "tx_mbps": tx_mbps,
        "rx_mbps": rx_mbps,
        "server_reachable": packet_loss_percent < 100.0,
        "game_server_latency_ms": serde_json::Value::Null,
        "game_server_packet_loss_percent": serde_json::Value::Null,
        "local_ip": local_ip,
        "interface_name": snapshot.interface_name,
    });

    post_json::<_, serde_json::Value>(
        &client,
        &format!("{}/api/metrics/", config.server_url.trim_end_matches('/')),
        &payload,
    )
    .await?;

    Ok(ClientStatus {
        timestamp: Utc::now().to_rfc3339(),
        latency_ms,
        jitter_ms,
        packet_loss_percent,
        tx_mbps,
        rx_mbps,
        server_reachable: packet_loss_percent < 100.0,
        local_ip,
        interface_name: snapshot.interface_name.clone(),
        next_snapshot: snapshot,
    })
}

struct SystemInfo;

impl SystemInfo {
    fn hostname() -> String {
        sysinfo::System::host_name().unwrap_or_else(|| "unknown-host".to_string())
    }

    fn os_name() -> String {
        sysinfo::System::long_os_version().unwrap_or_else(|| "Unknown OS".to_string())
    }
}

fn main() {
    Builder::default()
        .invoke_handler(tauri::generate_handler![
            load_config,
            save_config,
            get_client_info,
            register_client,
            report_metrics
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
