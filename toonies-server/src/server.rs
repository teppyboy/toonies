use std::net::SocketAddr;
use tokio::net::{TcpListener, UdpSocket};
use toonies_common::ServerMessage;
use crate::state::SharedState;
use crate::connection;

pub async fn run(addr: SocketAddr, state: SharedState) -> anyhow::Result<()> {
    let tcp = TcpListener::bind(addr).await?;
    let udp = UdpSocket::bind(addr).await?;
    tracing::info!("server listening on {addr}");

    let mut udp_buf = [0u8; 1024];
    loop {
        tokio::select! {
            Ok((stream, peer)) = tcp.accept() => {
                let state = state.clone();
                tokio::spawn(async move {
                    if let Err(e) = connection::handle(stream, peer, state).await {
                        tracing::warn!(%peer, "connection error: {e}");
                    }
                });
            }
            Ok((len, peer)) = udp.recv_from(&mut udp_buf) => {
                tracing::debug!(%peer, "UDP datagram ({len} bytes) — voice not yet implemented");
            }
            _ = tokio::signal::ctrl_c() => {
                tracing::info!("shutdown signal received");
                let _ = state.broadcast_tx.send(ServerMessage::ServerShutdown {
                    message: "Server is shutting down".into(),
                });
                break;
            }
        }
    }
    Ok(())
}
