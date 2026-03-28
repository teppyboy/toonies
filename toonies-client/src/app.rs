use toonies_common::{ClientMessage, ServerMessage, SessionId, UserId, Username};

#[derive(Debug, Clone)]
pub struct ChatLine {
    pub timestamp: String,
    pub prefix: Option<String>,
    pub content: String,
    pub kind: ChatLineKind,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ChatLineKind {
    Chat,
    System,
    Error,
    Info,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ConnectionStatus {
    Disconnected,
    Connecting,
    Connected,
    Error(String),
}

pub struct SessionInfo {
    pub session_id: SessionId,
    #[allow(dead_code)]
    pub user_id: UserId,
    pub username: Username,
}

/// Events from the background network task to the UI.
pub enum NetEvent {
    Connected,
    Message(ServerMessage),
    Disconnected(String),
    Error(String),
}

pub struct App {
    pub messages: Vec<ChatLine>,
    pub input: String,
    pub cursor_pos: usize,
    pub should_quit: bool,
    pub connection_status: ConnectionStatus,
    pub session: Option<SessionInfo>,
    pub server_addr: String,
    pub scroll_offset: u16,
    pub net_tx: Option<tokio::sync::mpsc::Sender<ClientMessage>>,
    pub net_rx: tokio::sync::mpsc::Receiver<NetEvent>,
    /// Username pending login confirmation.
    pub pending_login: Option<Username>,
    /// Set on first Ctrl+C; a second Ctrl+C within the same key sequence quits.
    pub ctrl_c_pending: bool,
    /// Input history, oldest entry first.
    pub history: Vec<String>,
    /// Index into `history` while browsing (None = not browsing).
    pub history_pos: Option<usize>,
    /// Saved input from before the user started browsing history.
    pub history_draft: String,
}

impl App {
    pub fn new() -> Self {
        let (_dummy_tx, net_rx) = tokio::sync::mpsc::channel(1);
        Self {
            messages: Vec::new(),
            input: String::new(),
            cursor_pos: 0,
            should_quit: false,
            connection_status: ConnectionStatus::Disconnected,
            session: None,
            server_addr: format!("127.0.0.1:{}", toonies_common::DEFAULT_PORT),
            scroll_offset: 0,
            net_tx: None,
            net_rx,
            pending_login: None,
            ctrl_c_pending: false,
            history: Vec::new(),
            history_pos: None,
            history_draft: String::new(),
        }
    }

    fn timestamp() -> String {
        use std::time::{SystemTime, UNIX_EPOCH};
        let secs = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let s = secs % 60;
        let m = (secs / 60) % 60;
        let h = (secs / 3600) % 24;
        format!("{h:02}:{m:02}:{s:02}")
    }

    pub fn push_chat(&mut self, username: &str, content: &str) {
        self.push_line(ChatLineKind::Chat, Some(format!("<{username}>")), content);
    }

    pub fn push_system(&mut self, content: &str) {
        self.push_line(ChatLineKind::System, None, content);
    }

    pub fn push_error(&mut self, content: &str) {
        self.push_line(ChatLineKind::Error, None, content);
    }

    pub fn push_info(&mut self, content: &str) {
        self.push_line(ChatLineKind::Info, None, content);
    }

    fn push_line(&mut self, kind: ChatLineKind, prefix: Option<String>, content: &str) {
        self.messages.push(ChatLine {
            timestamp: Self::timestamp(),
            prefix,
            content: content.to_string(),
            kind,
        });
        self.scroll_offset = 0;
    }
}
