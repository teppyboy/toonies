use thiserror::Error;

/// Errors that can occur during protocol framing or message parsing.
#[derive(Error, Debug)]
pub enum ProtocolError {
    #[error("payload size {actual} exceeds maximum {max} bytes")]
    PayloadTooLarge { max: u32, actual: u32 },

    #[error("failed to serialize message: {0}")]
    Serialize(#[from] rmp_serde::encode::Error),

    #[error("failed to deserialize message: {0}")]
    Deserialize(#[from] rmp_serde::decode::Error),

    #[error("connection closed")]
    ConnectionClosed,

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
}
