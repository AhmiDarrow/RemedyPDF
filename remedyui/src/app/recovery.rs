//! What to bring back on the next start: after an update installs, or after Android ends the
//! app. Unsaved edits are kept in a recovery copy beside the note, protected with the
//! document's password if it has one.

use super::Handle;
use crate::document::Document;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Serialize, Deserialize)]
pub struct Note {
    /// The document to open: the file itself, or the recovery copy holding unsaved edits.
    pub path: Option<PathBuf>,
    pub page: usize,
    /// `path` is a recovery copy with changes that are not saved yet.
    #[serde(default)]
    pub unsaved: bool,
    /// Set when an update left the note: the version it installed.
    #[serde(default)]
    pub updated: Option<String>,
}

fn note_file(data: &Path) -> PathBuf {
    data.join("resume.json")
}

/// The note left by the last run, read once.
pub fn take(data: &Path) -> Option<Note> {
    let file = note_file(data);
    let text = std::fs::read_to_string(&file).ok()?;
    // Read once, whatever it holds.
    let _ = std::fs::remove_file(&file);
    serde_json::from_str(&text).ok()
}

pub fn forget(data: &Path) {
    let _ = std::fs::remove_file(note_file(data));
}

/// Where the recovery copy of a document named like `path` goes. It keeps the name.
fn copy_of(data: &Path, path: &Path) -> PathBuf {
    let name = path
        .file_name()
        .map_or_else(|| "document.pdf".into(), |n| n.to_os_string());
    data.join("recovery").join(name)
}

/// Writes down what is open now. `updated` is the version an update is about to install.
pub fn note(shell: &Handle, updated: Option<&str>) {
    let Some(data) = shell.app.data_dir() else {
        return;
    };
    let open = shell.current();
    let mut note = Note {
        page: open
            .as_ref()
            .and_then(|o| o.view.current_page().get_untracked().ok())
            .unwrap_or(0),
        path: open.as_ref().map(|o| o.path.clone()),
        unsaved: false,
        updated: updated.map(str::to_owned),
    };
    if let Some(open) = open.filter(|_| shell.has_changes())
        && let Document::Pdf(file) = &*open.document
    {
        let copy = copy_of(&data, &open.path);
        // The copy may be the very file open now, after an earlier recovery.
        let written = copy
            .parent()
            .is_some_and(|d| std::fs::create_dir_all(d).is_ok())
            && file.save(&copy).is_ok();
        if written {
            note.path = Some(copy);
            note.unsaved = true;
        }
    }
    if note.path.is_none() && note.updated.is_none() {
        forget(&data);
        return;
    }
    if let Ok(text) = serde_json::to_string(&note) {
        // Without the note the app still starts; it only opens empty.
        let _ =
            std::fs::create_dir_all(&data).and_then(|()| std::fs::write(note_file(&data), text));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_note_is_read_once() {
        let folder = tempfile::tempdir().unwrap();
        std::fs::write(
            note_file(folder.path()),
            r#"{"path":"a.pdf","page":4,"updated":"2.0.1"}"#,
        )
        .unwrap();
        let note = take(folder.path()).unwrap();
        assert_eq!(
            (note.page, note.updated.as_deref(), note.unsaved),
            (4, Some("2.0.1"), false)
        );
        assert!(take(folder.path()).is_none());
    }
}
