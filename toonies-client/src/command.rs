use toonies_common::{ClientMessage, Username};
use crate::app::{App, ConnectionStatus};
use crate::network;

pub async fn execute(input: &str, app: &mut App) {
    let mut parts = input.splitn(3, ' ');
    let cmd = parts.next().unwrap_or("");
    let arg1 = parts.next();
    let arg2 = parts.next();

    match cmd {
        "/help" => {
            app.push_info("Available commands:");
            app.push_info("  /register <username> <password>  - create account");
            app.push_info("  /login <username> <password>     - log in");
            app.push_info("  /set-server <host:port>          - set server address");
            app.push_info("  /users                           - list online users");
            app.push_info("  /quit                            - exit");
        }
        "/quit" => {
            app.should_quit = true;
        }
        "/set-server" => {
            let Some(addr) = arg1 else {
                app.push_error("Usage: /set-server <host:port>");
                return;
            };
            app.server_addr = addr.to_string();
            app.connection_status = ConnectionStatus::Connecting;

            let (event_tx, event_rx) = tokio::sync::mpsc::channel(64);
            app.net_rx = event_rx;
            let net_tx = network::spawn_connection(app.server_addr.clone(), event_tx);
            app.net_tx = Some(net_tx);
            app.push_system(&format!("Connecting to {addr}..."));
        }
        "/register" => {
            let (Some(user), Some(pass)) = (arg1, arg2) else {
                app.push_error("Usage: /register <username> <password>");
                return;
            };
            let username = match Username::new(user) {
                Ok(u) => u,
                Err(e) => {
                    app.push_error(&format!("Invalid username: {e}"));
                    return;
                }
            };
            if let Some(tx) = &app.net_tx {
                let _ = tx.send(ClientMessage::Register {
                    username,
                    password: pass.to_string(),
                }).await;
            } else {
                app.push_error("Not connected. Use /set-server <addr> first.");
            }
        }
        "/login" => {
            let (Some(user), Some(pass)) = (arg1, arg2) else {
                app.push_error("Usage: /login <username> <password>");
                return;
            };
            let username = match Username::new(user) {
                Ok(u) => u,
                Err(e) => {
                    app.push_error(&format!("Invalid username: {e}"));
                    return;
                }
            };
            if let Some(tx) = &app.net_tx {
                app.pending_login = Some(username.clone());
                let _ = tx.send(ClientMessage::Login {
                    username,
                    password: pass.to_string(),
                }).await;
            } else {
                app.push_error("Not connected. Use /set-server <addr> first.");
            }
        }
        "/users" => {
            let Some(ref session) = app.session else {
                app.push_error("Not logged in.");
                return;
            };
            if let Some(tx) = &app.net_tx {
                let _ = tx.send(ClientMessage::ListUsers {
                    session_id: session.session_id,
                }).await;
            }
        }
        _ => {
            app.push_error(&format!(
                "Unknown command: {cmd}. Type /help for available commands."
            ));
        }
    }
}
