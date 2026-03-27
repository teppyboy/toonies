use std::net::SocketAddr;
use toonies_common::{read_message, write_message, ClientMessage, ProtocolError};
use tokio::net::TcpStream;
use tokio::sync::broadcast;
use crate::state::SharedState;
use crate::handler;

pub async fn handle(stream: TcpStream, peer: SocketAddr, state: SharedState) -> anyhow::Result<()> {
    let (mut reader, mut writer) = stream.into_split();
    let mut broadcast_rx = state.broadcast_tx.subscribe();

    loop {
        tokio::select! {
            result = read_message::<_, ClientMessage>(&mut reader) => {
                match result {
                    Ok(msg) => {
                        let responses = handler::process(msg, &state).await;
                        for response in responses {
                            write_message(&mut writer, &response).await?;
                        }
                    }
                    Err(ProtocolError::ConnectionClosed) => break,
                    Err(e) => return Err(e.into()),
                }
            }
            result = broadcast_rx.recv() => {
                match result {
                    Ok(msg) => write_message(&mut writer, &msg).await?,
                    Err(broadcast::error::RecvError::Lagged(n)) => {
                        tracing::warn!(%peer, "broadcast lagged by {n} messages");
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                }
            }
        }
    }
    Ok(())
}
