mod auth;
mod connection;
mod handler;
mod server;
mod state;

use std::net::SocketAddr;
use toonies_common::DEFAULT_PORT;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("toonies_server=debug".parse()?),
        )
        .init();

    let addr: SocketAddr = std::env::args()
        .nth(1)
        .unwrap_or_else(|| format!("0.0.0.0:{DEFAULT_PORT}"))
        .parse()?;

    let state = state::AppState::new();
    server::run(addr, state).await
}
