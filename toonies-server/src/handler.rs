use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;
use toonies_common::{ClientMessage, ServerMessage, Username};
use crate::state::{SharedState, UserRecord, Session};
use crate::auth;

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

pub async fn process(msg: ClientMessage, state: &SharedState) -> Vec<ServerMessage> {
    match msg {
        ClientMessage::Register { username, password } => {
            let key = username.to_string();
            {
                let users = state.users.read().await;
                if users.contains_key(&key) {
                    return vec![ServerMessage::RegisterResult {
                        success: false,
                        message: "Username already taken".into(),
                    }];
                }
            }
            let password_hash = match auth::hash_password(password).await {
                Ok(h) => h,
                Err(e) => {
                    tracing::warn!("password hashing error: {e}");
                    return vec![ServerMessage::RegisterResult {
                        success: false,
                        message: "Internal error during registration".into(),
                    }];
                }
            };
            let user_id = Uuid::new_v4();
            let record = UserRecord {
                user_id,
                username: username.clone(),
                password_hash,
            };
            state.users.write().await.insert(key, record);
            tracing::info!("registered user: {username}");
            vec![ServerMessage::RegisterResult {
                success: true,
                message: "Registration successful".into(),
            }]
        }

        ClientMessage::Login { username, password } => {
            let key = username.to_string();
            let (user_id, stored_username, password_hash) = {
                let users = state.users.read().await;
                match users.get(&key) {
                    Some(r) => (r.user_id, r.username.clone(), r.password_hash.clone()),
                    None => {
                        return vec![ServerMessage::LoginResult {
                            success: false,
                            session_id: None,
                            user_id: None,
                            message: "Unknown username or wrong password".into(),
                        }];
                    }
                }
            };
            let ok = match auth::verify_password(password, password_hash).await {
                Ok(v) => v,
                Err(e) => {
                    tracing::warn!("password verification error: {e}");
                    return vec![ServerMessage::LoginResult {
                        success: false,
                        session_id: None,
                        user_id: None,
                        message: "Internal error during login".into(),
                    }];
                }
            };
            if !ok {
                return vec![ServerMessage::LoginResult {
                    success: false,
                    session_id: None,
                    user_id: None,
                    message: "Unknown username or wrong password".into(),
                }];
            }
            let session_id = Uuid::new_v4();
            state.sessions.write().await.insert(session_id, Session {
                user_id,
                username: stored_username.clone(),
            });
            let notice = ServerMessage::SystemNotice {
                content: format!("{stored_username} joined"),
                timestamp: now_ms(),
            };
            let _ = state.broadcast_tx.send(notice);
            tracing::info!("user logged in: {stored_username}");
            vec![ServerMessage::LoginResult {
                success: true,
                session_id: Some(session_id),
                user_id: Some(user_id),
                message: "Login successful".into(),
            }]
        }

        ClientMessage::ChatSend { session_id, content } => {
            let from_user = {
                let sessions = state.sessions.read().await;
                match sessions.get(&session_id) {
                    Some(s) => {
                        tracing::debug!(user_id = %s.user_id, "chat message from session {session_id}");
                        s.username.clone()
                    }
                    None => {
                        tracing::warn!("ChatSend with invalid session {session_id}");
                        return vec![];
                    }
                }
            };
            let broadcast_msg = ServerMessage::ChatBroadcast {
                from_user,
                content,
                timestamp: now_ms(),
            };
            let _ = state.broadcast_tx.send(broadcast_msg);
            vec![]
        }

        ClientMessage::ListUsers { session_id } => {
            let sessions = state.sessions.read().await;
            if sessions.get(&session_id).is_none() {
                tracing::warn!("ListUsers with invalid session {session_id}");
                return vec![];
            }
            let users: Vec<Username> = sessions.values().map(|s| s.username.clone()).collect();
            vec![ServerMessage::UserList { users }]
        }

        ClientMessage::Disconnect { session_id } => {
            let username = {
                let mut sessions = state.sessions.write().await;
                sessions.remove(&session_id).map(|s| s.username)
            };
            if let Some(username) = username {
                let notice = ServerMessage::SystemNotice {
                    content: format!("{username} left"),
                    timestamp: now_ms(),
                };
                let _ = state.broadcast_tx.send(notice);
                tracing::info!("user disconnected: {username}");
            }
            vec![]
        }

        ClientMessage::ChangePassword { session_id, old_password, new_password } => {
            // Validate session → get username key
            let username_key = {
                let sessions = state.sessions.read().await;
                match sessions.get(&session_id) {
                    Some(s) => s.username.to_string(),
                    None => {
                        tracing::warn!("ChangePassword with invalid session {session_id}");
                        return vec![ServerMessage::ChangePasswordResult {
                            success: false,
                            message: "Not authenticated".into(),
                        }];
                    }
                }
            };
            // Look up stored hash
            let stored_hash = {
                let users = state.users.read().await;
                match users.get(&username_key) {
                    Some(r) => r.password_hash.clone(),
                    None => {
                        return vec![ServerMessage::ChangePasswordResult {
                            success: false,
                            message: "User record not found".into(),
                        }];
                    }
                }
            };
            // Verify old password
            let ok = match auth::verify_password(old_password, stored_hash).await {
                Ok(v) => v,
                Err(e) => {
                    tracing::warn!("ChangePassword verification error: {e}");
                    return vec![ServerMessage::ChangePasswordResult {
                        success: false,
                        message: "Internal error during verification".into(),
                    }];
                }
            };
            if !ok {
                return vec![ServerMessage::ChangePasswordResult {
                    success: false,
                    message: "Old password is incorrect".into(),
                }];
            }
            // Hash new password and update record
            let new_hash = match auth::hash_password(new_password).await {
                Ok(h) => h,
                Err(e) => {
                    tracing::warn!("ChangePassword hashing error: {e}");
                    return vec![ServerMessage::ChangePasswordResult {
                        success: false,
                        message: "Internal error while updating password".into(),
                    }];
                }
            };
            state.users.write().await
                .entry(username_key.clone())
                .and_modify(|r| r.password_hash = new_hash);
            tracing::info!("password changed for user: {username_key}");
            vec![ServerMessage::ChangePasswordResult {
                success: true,
                message: "Password changed successfully".into(),
            }]
        }

        ClientMessage::Ping => vec![ServerMessage::Pong],
    }
}
