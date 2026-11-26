//! RemedyPDF's desktop entry point.

#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

use remedypdf::app;
use std::path::PathBuf;

fn main() {
    // The first argument that names a document is opened.
    let first = std::env::args_os()
        .skip(1)
        .map(PathBuf::from)
        .find(|p| app::opens(p) && p.is_file());
    // For scripts and the release tests: look for an update at once.
    let update_now = std::env::args_os().any(|a| a == "--install-update");
    if let Err(e) = app::launch(first, update_now) {
        eprintln!("{e}");
        std::process::exit(1);
    }
}
