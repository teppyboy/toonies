mod app;
mod command;
mod event;
mod network;
mod ui;

use std::io;
use futures::StreamExt as _;
use crossterm::{
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
    event::EventStream,
};
use ratatui::{
    backend::CrosstermBackend,
    Terminal,
};
use crate::app::App;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let log_file = std::fs::File::create("toonies-client.log")?;
    tracing_subscriber::fmt()
        .with_writer(log_file)
        .with_ansi(false)
        .init();

    let original_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let _ = disable_raw_mode();
        let _ = execute!(io::stderr(), LeaveAlternateScreen);
        original_hook(info);
    }));

    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut app = App::new();
    app.push_info("Welcome to Toonies! Type /help for commands.");

    let result = run_app(&mut terminal, &mut app).await;

    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;

    if let Err(e) = result {
        eprintln!("Error: {e}");
    }
    Ok(())
}

async fn run_app(
    terminal: &mut ratatui::Terminal<CrosstermBackend<io::Stdout>>,
    app: &mut App,
) -> anyhow::Result<()> {
    let mut event_stream = EventStream::new();

    loop {
        terminal.draw(|f| ui::draw(f, app))?;

        tokio::select! {
            Some(Ok(ev)) = event_stream.next() => {
                event::handle_key(ev, app).await;
            }
            Some(net_ev) = app.net_rx.recv() => {
                event::handle_net(net_ev, app);
            }
        }

        if app.should_quit {
            break;
        }
    }
    Ok(())
}
