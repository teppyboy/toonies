use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{broadcast, RwLock};
use toonies_common::{ServerMessage, SessionId, UserId, Username};

pub struct UserRecord {
    pub user_id: UserId,
    pub username: Username,
    pub password_hash: String,
}

pub struct Session {
    pub user_id: UserId,
    pub username: Username,
}

pub struct AppState {
    pub users: RwLock<HashMap<String, UserRecord>>,
    pub sessions: RwLock<HashMap<SessionId, Session>>,
    pub broadcast_tx: broadcast::Sender<ServerMessage>,
}

pub type SharedState = Arc<AppState>;

impl AppState {
    pub fn new() -> SharedState {
        let (broadcast_tx, _) = broadcast::channel(256);
        Arc::new(Self {
            users: RwLock::new(HashMap::new()),
            sessions: RwLock::new(HashMap::new()),
            broadcast_tx,
        })
    }
}

impl Default for AppState {
    fn default() -> Self {
        let (broadcast_tx, _) = broadcast::channel(256);
        Self {
            users: RwLock::new(HashMap::new()),
            sessions: RwLock::new(HashMap::new()),
            broadcast_tx,
        }
    }
}
