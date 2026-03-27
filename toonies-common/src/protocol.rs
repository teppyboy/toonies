use serde::{de::DeserializeOwned, Serialize};
use tokio::io::{AsyncReadExt, AsyncWriteExt};

use crate::{
    error::ProtocolError,
    types::{SessionId, Timestamp, UserId, Username},
};

/// Default TCP port the server listens on.
pub const DEFAULT_PORT: u16 = 7878;

/// Maximum allowed payload size (64 KiB). Prevents memory exhaustion attacks.
pub const MAX_PAYLOAD_SIZE: u32 = 64 * 1024;

/// Messages sent from a client to the server.
#[derive(Debug, Clone, Serialize, serde::Deserialize)]
pub enum ClientMessage {
    /// Create a new account.
    Register { username: Username, password: String },
    /// Authenticate with an existing account.
    Login { username: Username, password: String },
    /// Send a chat message to all connected users.
    ChatSend { session_id: SessionId, content: String },
    /// Request the list of currently online users.
    ListUsers { session_id: SessionId },
    /// Notify the server of a graceful disconnect.
    Disconnect { session_id: SessionId },
    /// Keep-alive ping.
    Ping,
}

/// Messages sent from the server to a client.
#[derive(Debug, Clone, Serialize, serde::Deserialize)]
pub enum ServerMessage {
    /// Result of a registration attempt.
    RegisterResult { success: bool, message: String },
    /// Result of a login attempt. On success, includes the session and user IDs.
    LoginResult {
        success: bool,
        session_id: Option<SessionId>,
        user_id: Option<UserId>,
        message: String,
    },
    /// A chat message broadcast to all connected clients.
    ChatBroadcast {
        from_user: Username,
        content: String,
        timestamp: Timestamp,
    },
    /// List of currently online usernames.
    UserList { users: Vec<Username> },
    /// Server-initiated notification (join/leave notices, errors, etc.).
    SystemNotice { content: String, timestamp: Timestamp },
    /// Keep-alive pong.
    Pong,
    /// Server is shutting down.
    ServerShutdown { message: String },
}

/// Write a length-prefixed MessagePack message to an async writer.
///
/// Frame format: `[u32 big-endian length][MessagePack payload]`
pub async fn write_message<W, M>(writer: &mut W, msg: &M) -> Result<(), ProtocolError>
where
    W: AsyncWriteExt + Unpin,
    M: Serialize,
{
    let payload = rmp_serde::to_vec_named(msg)?;
    let len = payload.len() as u32;
    if len > MAX_PAYLOAD_SIZE {
        return Err(ProtocolError::PayloadTooLarge {
            max: MAX_PAYLOAD_SIZE,
            actual: len,
        });
    }
    writer.write_all(&len.to_be_bytes()).await?;
    writer.write_all(&payload).await?;
    writer.flush().await?;
    Ok(())
}

/// Read a length-prefixed MessagePack message from an async reader.
pub async fn read_message<R, M>(reader: &mut R) -> Result<M, ProtocolError>
where
    R: AsyncReadExt + Unpin,
    M: DeserializeOwned,
{
    let mut len_buf = [0u8; 4];
    match reader.read_exact(&mut len_buf).await {
        Ok(_) => {}
        Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
            return Err(ProtocolError::ConnectionClosed);
        }
        Err(e) => return Err(e.into()),
    }
    let len = u32::from_be_bytes(len_buf);
    if len > MAX_PAYLOAD_SIZE {
        return Err(ProtocolError::PayloadTooLarge {
            max: MAX_PAYLOAD_SIZE,
            actual: len,
        });
    }
    let mut payload = vec![0u8; len as usize];
    reader.read_exact(&mut payload).await?;
    let msg = rmp_serde::from_slice(&payload)?;
    Ok(msg)
}
