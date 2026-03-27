use tokio::net::TcpStream;
use toonies_common::{read_message, write_message, ClientMessage, ProtocolError, ServerMessage};
use crate::app::NetEvent;

/// Spawns a background tokio task that manages the TCP connection.
/// Returns an `mpsc::Sender<ClientMessage>` the UI uses to send messages.
pub fn spawn_connection(
    addr: String,
    event_tx: tokio::sync::mpsc::Sender<NetEvent>,
) -> tokio::sync::mpsc::Sender<ClientMessage> {
    let (msg_tx, mut msg_rx) = tokio::sync::mpsc::channel::<ClientMessage>(64);

    tokio::spawn(async move {
        match TcpStream::connect(&addr).await {
            Err(e) => {
                let _ = event_tx.send(NetEvent::Error(format!("connect failed: {e}"))).await;
            }
            Ok(stream) => {
                let _ = event_tx.send(NetEvent::Connected).await;
                let (mut reader, mut writer) = stream.into_split();

                loop {
                    tokio::select! {
                        Some(msg) = msg_rx.recv() => {
                            if let Err(e) = write_message(&mut writer, &msg).await {
                                let _ = event_tx.send(NetEvent::Error(e.to_string())).await;
                                break;
                            }
                        }
                        result = read_message::<_, ServerMessage>(&mut reader) => {
                            match result {
                                Ok(msg) => {
                                    if event_tx.send(NetEvent::Message(msg)).await.is_err() {
                                        break;
                                    }
                                }
                                Err(ProtocolError::ConnectionClosed) => {
                                    let _ = event_tx.send(NetEvent::Disconnected(
                                        "server closed connection".into()
                                    )).await;
                                    break;
                                }
                                Err(e) => {
                                    let _ = event_tx.send(NetEvent::Error(e.to_string())).await;
                                    break;
                                }
                            }
                        }
                    }
                }
            }
        }
    });

    msg_tx
}
