use ratatui::crossterm::event::{Event, KeyCode, KeyModifiers};
use toonies_common::{ClientMessage, ServerMessage, Username};
use crate::app::{App, ConnectionStatus, NetEvent, SessionInfo};

pub async fn handle_key(event: Event, app: &mut App) {
    let Event::Key(key) = event else { return };

    match key.code {
        KeyCode::Enter => {
            let line: String = app.input.drain(..).collect();
            app.cursor_pos = 0;
            if line.is_empty() {
                return;
            }
            if line.starts_with('/') {
                crate::command::execute(&line, app).await;
            } else {
                let Some(ref session) = app.session else {
                    app.push_error("Not logged in. Use /login <username> <password>.");
                    return;
                };
                if let Some(tx) = &app.net_tx {
                    let _ = tx.send(ClientMessage::ChatSend {
                        session_id: session.session_id,
                        content: line,
                    }).await;
                }
            }
        }
        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            app.should_quit = true;
        }
        KeyCode::Esc => {
            app.should_quit = true;
        }
        KeyCode::Char(c) => {
            app.input.insert(app.cursor_pos, c);
            app.cursor_pos += 1;
        }
        KeyCode::Backspace => {
            if app.cursor_pos > 0 {
                app.cursor_pos -= 1;
                app.input.remove(app.cursor_pos);
            }
        }
        KeyCode::Delete => {
            if app.cursor_pos < app.input.len() {
                app.input.remove(app.cursor_pos);
            }
        }
        KeyCode::Left => {
            app.cursor_pos = app.cursor_pos.saturating_sub(1);
        }
        KeyCode::Right => {
            if app.cursor_pos < app.input.len() {
                app.cursor_pos += 1;
            }
        }
        KeyCode::Home => {
            app.cursor_pos = 0;
        }
        KeyCode::End => {
            app.cursor_pos = app.input.len();
        }
        KeyCode::PageUp => {
            app.scroll_offset = app.scroll_offset.saturating_add(5);
        }
        KeyCode::PageDown => {
            app.scroll_offset = app.scroll_offset.saturating_sub(5);
        }
        _ => {}
    }
}

pub fn handle_net(event: NetEvent, app: &mut App) {
    match event {
        NetEvent::Connected => {
            app.connection_status = ConnectionStatus::Connected;
            app.push_system("Connected to server.");
        }
        NetEvent::Message(msg) => dispatch_server_message(msg, app),
        NetEvent::Disconnected(reason) => {
            app.connection_status = ConnectionStatus::Disconnected;
            app.push_error(&format!("Disconnected: {reason}"));
            app.session = None;
        }
        NetEvent::Error(e) => {
            app.connection_status = ConnectionStatus::Error(e.clone());
            app.push_error(&format!("Network error: {e}"));
        }
    }
}

fn dispatch_server_message(msg: ServerMessage, app: &mut App) {
    match msg {
        ServerMessage::ChatBroadcast { from_user, content, .. } => {
            app.push_chat(&from_user.to_string(), &content);
        }
        ServerMessage::RegisterResult { success, message } => {
            if success {
                app.push_system(&format!("Registered: {message}"));
            } else {
                app.push_error(&format!("Registration failed: {message}"));
            }
        }
        ServerMessage::LoginResult { success, session_id, user_id, message } => {
            if success {
                if let (Some(sid), Some(uid)) = (session_id, user_id) {
                    app.push_system(&format!("Logged in: {message}"));
                    let username = app.pending_login.take().unwrap_or_else(|| {
                        Username::new("unknown").expect("fallback username is valid")
                    });
                    app.session = Some(SessionInfo { session_id: sid, user_id: uid, username });
                    app.connection_status = ConnectionStatus::Connected;
                }
            } else {
                app.pending_login = None;
                app.push_error(&format!("Login failed: {message}"));
            }
        }
        ServerMessage::UserList { users } => {
            let names: Vec<_> = users.iter().map(|u| u.to_string()).collect();
            app.push_info(&format!("Online ({} user(s)): {}", names.len(), names.join(", ")));
        }
        ServerMessage::SystemNotice { content, .. } => {
            app.push_system(&content);
        }
        ServerMessage::Pong => {}
        ServerMessage::ServerShutdown { message } => {
            app.push_error(&format!("Server shutting down: {message}"));
            app.connection_status = ConnectionStatus::Disconnected;
            app.session = None;
        }
    }
}
