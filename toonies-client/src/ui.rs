use ratatui::{
    Frame,
    layout::{Constraint, Layout},
    style::{Color, Style},
    text::{Line, Span},
    widgets::{Block, Paragraph},
};
use crate::app::{App, ChatLine, ChatLineKind, ConnectionStatus};

fn render_line(m: &ChatLine) -> Line<'_> {
    match m.kind {
        ChatLineKind::Chat => Line::from(vec![
            Span::styled(format!("[{}] ", m.timestamp), Style::default().fg(Color::DarkGray)),
            Span::styled(
                format!("{} ", m.prefix.as_deref().unwrap_or("")),
                Style::default().fg(Color::Cyan),
            ),
            Span::raw(m.content.clone()),
        ]),
        ChatLineKind::System => Line::from(Span::styled(
            format!("[{}] * {}", m.timestamp, m.content),
            Style::default().fg(Color::Yellow),
        )),
        ChatLineKind::Error => Line::from(Span::styled(
            format!("[{}] ! {}", m.timestamp, m.content),
            Style::default().fg(Color::Red),
        )),
        ChatLineKind::Info => Line::from(Span::styled(
            format!("[{}]   {}", m.timestamp, m.content),
            Style::default().fg(Color::Green),
        )),
    }
}

pub fn draw(frame: &mut Frame, app: &App) {
    let area = frame.area();
    let chunks = Layout::vertical([
        Constraint::Length(1),
        Constraint::Min(1),
        Constraint::Length(1),
        Constraint::Length(3),
    ])
    .split(area);

    let title = Paragraph::new(" \u{25a0} TOONIES MESSENGER ")
        .centered()
        .style(Style::default().fg(Color::White).bg(Color::DarkGray));
    frame.render_widget(title, chunks[0]);

    let msg_height = chunks[1].height as usize;
    let total = app.messages.len();
    let skip = if total > msg_height {
        let base = total - msg_height;
        base.saturating_sub(app.scroll_offset as usize)
    } else {
        0
    };
    let visible: Vec<Line> = app.messages.iter().skip(skip).map(render_line).collect();
    frame.render_widget(Paragraph::new(visible), chunks[1]);

    let status_text = match &app.connection_status {
        ConnectionStatus::Connected => {
            let user = app
                .session
                .as_ref()
                .map(|s| s.username.to_string())
                .unwrap_or_else(|| "?".into());
            format!(" \u{25cf} Connected as {user} \u{2502} {}", app.server_addr)
        }
        ConnectionStatus::Connecting => format!(" \u{25cc} Connecting to {}...", app.server_addr),
        ConnectionStatus::Disconnected => {
            " \u{25cb} Disconnected \u{2502} type /set-server <addr> then /login".to_string()
        }
        ConnectionStatus::Error(e) => format!(" \u{2717} Error: {e}"),
    };
    frame.render_widget(
        Paragraph::new(status_text).style(Style::default().fg(Color::White).bg(Color::DarkGray)),
        chunks[2],
    );

    frame.render_widget(
        Paragraph::new(format!("> {}", app.input)).block(Block::bordered().title(" Chat ")),
        chunks[3],
    );
    frame.set_cursor_position((
        chunks[3].x + 1 + 2 + app.cursor_pos as u16,
        chunks[3].y + 1,
    ));
}
