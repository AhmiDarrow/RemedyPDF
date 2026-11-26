//! The window: menus, toolbar, pages, find bar, navigator and status line.

mod dialogs;
pub mod look;
pub mod recovery;
pub mod update;

use crate::document::Document;
use crate::pdf::{self, Error};
use remedy_ui::core::Rect;
use remedy_ui::host::FileDialog;
use remedy_ui::input::{Buttons, Chord, Key, Modifiers, Platform, PointerPhase};
use remedy_ui::layout::Align;
use remedy_ui::nav::Commands;
use remedy_ui::pages::{
    Fit, PageHit, PageInput, PageMode, PageView, Rotation, Spread, ZoomStep, page_view,
};
use remedy_ui::reactive::{Persist, Signal};
use remedy_ui::update::{Release, UpdateState};
use remedy_ui::widgets::{self as w, MenuItem};
use remedy_ui::{App, CloseReason, El, Ui, Window};
use serde::{Deserialize, Serialize};
use std::cell::{Cell, RefCell};
use std::path::{Path, PathBuf};
use std::rc::Rc;

pub const NAME: &str = "RemedyPDF";
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

const COARSE: f32 = 0.15;
const FINE: f32 = 0.01;
const DEFAULT_ZOOM: f32 = if cfg!(target_os = "android") {
    1.0
} else {
    1.25
};
const ZOOM_RANGE: (f32, f32) = (0.1, 8.0);
const SCALES: [(&str, f32); 5] = [
    ("Compact (90%)", 0.9),
    ("Default (100%)", 1.0),
    ("Comfortable (115%)", 1.15),
    ("Large (130%)", 1.3),
    ("Extra large (150%)", 1.5),
];
const EXTENSIONS: [&str; 22] = [
    "pdf", "epub", "xps", "oxps", "cbz", "cbr", "fb2", "mobi", "svg", "docx", "html", "htm",
    "xhtml", "txt", "png", "jpg", "jpeg", "bmp", "gif", "tif", "tiff", "webp",
];

/// What is remembered between runs.
#[derive(Serialize, Deserialize)]
struct Prefs {
    theme: String,
    book: bool,
    scale: f32,
    #[serde(default = "yes")]
    auto_update: bool,
}

fn yes() -> bool {
    true
}

impl Default for Prefs {
    fn default() -> Self {
        let scale = if cfg!(target_os = "android") {
            1.15
        } else {
            1.0
        };
        Prefs {
            theme: "normal".into(),
            book: false,
            scale,
            auto_update: true,
        }
    }
}

fn prefs_key() -> Persist {
    Persist::new("prefs")
}

/// The open document.
#[derive(Clone)]
struct Open {
    document: Rc<Document>,
    view: PageView,
    /// Where it was opened from, or last saved to.
    path: PathBuf,
    /// Writing `path` changes the person's own file. Not so for a document opened on
    /// Android, which is the app's copy: saving that asks where to write.
    writable: bool,
}

pub struct Shell {
    app: App,
    window: Window,
    ui: Ui,
    open: RefCell<Option<Open>>,
    /// Bumped when `open` changes, for the text that reads it.
    changed: Signal<u64>,
    dirty: Signal<bool>,
    theme: Signal<String>,
    scale: Signal<f32>,
    book: Signal<bool>,
    filter: Signal<String>,
    brightness: Signal<f32>,
    contrast: Signal<f32>,
    reader: Signal<bool>,
    full: Signal<bool>,
    finding: Signal<bool>,
    busy: Signal<bool>,
    /// A passing message that takes the status line's place.
    message: Signal<Option<String>>,
    said: Cell<u64>,
    commands: Commands,
    update: Signal<UpdateState>,
    auto_update: Signal<bool>,
    update_failures: Cell<u32>,
    /// The newer release found, and its verified download once there is one.
    release: RefCell<Option<Release>>,
    downloaded: RefCell<Option<PathBuf>>,
    /// The page to show once the document being opened is up.
    resume_page: Cell<Option<usize>>,
    /// The document being opened holds unsaved changes brought back from a recovery copy.
    resume_unsaved: Cell<bool>,
    /// Where the pages go.
    stage: RefCell<Option<El>>,
    /// The find field, while the bar is up.
    find_field: RefCell<Option<remedy_ui::view::TextField>>,
}

pub type Handle = Rc<Shell>;

fn file_name(path: &Path) -> String {
    path.file_name()
        .map_or_else(|| "document".into(), |n| n.to_string_lossy().into_owned())
}

fn percent(v: f32) -> i32 {
    (v * 100.0).round() as i32
}

impl Shell {
    // ---- Small helpers ----

    fn view(&self) -> Option<PageView> {
        self.open.borrow().as_ref().map(|o| o.view.clone())
    }

    fn current(&self) -> Option<Open> {
        self.open.borrow().clone()
    }

    pub fn say(self: &Rc<Self>, message: impl Into<String>) {
        let n = self.said.get() + 1;
        self.said.set(n);
        self.message.set(Some(message.into()));
        let shell = Rc::downgrade(self);
        self.ui
            .after(std::time::Duration::from_millis(3000), move || {
                if let Some(shell) = shell.upgrade()
                    && shell.said.get() == n
                {
                    shell.message.set(None);
                }
            });
    }

    fn save_prefs(&self) {
        if let Some(store) = self.app.persist_store() {
            let prefs = Prefs {
                theme: self.theme.get_untracked().unwrap_or_default(),
                book: self.book.get_untracked().unwrap_or(false),
                scale: self.scale.get_untracked().unwrap_or(1.0),
                auto_update: self.auto_update.get_untracked().unwrap_or(true),
            };
            // A preference that cannot be written is only forgotten.
            let _ = store.save(&prefs_key(), &prefs);
        }
    }

    // ---- Opening and closing ----

    /// Runs `then` now, or after the person has saved or discarded unsaved changes.
    fn keeping_changes(self: &Rc<Self>, question: &str, then: impl Fn(&Handle) + Clone + 'static) {
        if !self.dirty.get_untracked().unwrap_or(false) {
            then(self);
            return;
        }
        dialogs::unsaved(self, question, then);
    }

    pub fn choose_file(self: &Rc<Self>) {
        let shell = self.clone();
        let mut dialog = FileDialog::default();
        dialog.title = "Open Document".into();
        let all = EXTENSIONS.iter().map(|e| (*e).to_owned()).collect();
        dialog.filters = vec![("Documents".into(), all)];
        for (name, list) in [
            ("PDF", &["pdf"][..]),
            ("EPUB", &["epub"]),
            ("XPS", &["xps", "oxps"]),
            ("Comic Book", &["cbz", "cbr"]),
            ("FictionBook", &["fb2"]),
            ("MOBI", &["mobi"]),
            ("SVG", &["svg"]),
            ("Word", &["docx"]),
            ("HTML", &["html", "htm", "xhtml"]),
            ("Text", &["txt"]),
            (
                "Images",
                &["png", "jpg", "jpeg", "bmp", "gif", "tif", "tiff", "webp"],
            ),
        ] {
            dialog
                .filters
                .push((name.into(), list.iter().map(|e| (*e).to_owned()).collect()));
        }
        self.app
            .file_dialog(Some(&self.window), dialog, move |paths| {
                if let Some(path) = paths.into_iter().next() {
                    shell.open_path(path);
                }
            });
    }

    pub fn open_path(self: &Rc<Self>, path: PathBuf) {
        self.keeping_changes("Save before opening another document?", move |shell| {
            shell.load(path.clone(), None, 0);
        });
    }

    /// Reads the file off the UI thread. A failure leaves the current document as it was.
    fn load(self: &Rc<Self>, path: PathBuf, password: Option<String>, tries: u32) {
        self.busy.set(true);
        let shell = self.clone();
        let from = path.clone();
        self.app.background(
            move || Document::open(&from, password.as_deref()),
            move |result| {
                shell.busy.set(false);
                match result {
                    Ok(document) => shell.show(document, path),
                    Err(Error::Password) if tries < 3 => dialogs::password(&shell, path, tries),
                    Err(e) => {
                        let why = match e {
                            Error::Password => "a password is required".to_owned(),
                            Error::Empty => "the document has no pages".to_owned(),
                            Error::Other(why) => why,
                        };
                        dialogs::problem(
                            &shell,
                            format!("Could not open {}:\n{why}", file_name(&path)),
                        );
                    }
                }
            },
        );
    }

    #[allow(
        clippy::field_reassign_with_default,
        reason = "PageInput is non-exhaustive: it cannot be written out"
    )]
    fn show(self: &Rc<Self>, document: Document, path: PathBuf) {
        let view = PageView::new(document.pages());
        view.set_page_mode(PageMode::Paged);
        view.set_zoom_range(ZOOM_RANGE.0, ZOOM_RANGE.1);
        view.set_zoom(DEFAULT_ZOOM, None);
        let mut input = PageInput::default();
        input.wheel_zoom = Some(ZoomStep::Add(FINE));
        input.wheel_zoom_shift = Some(ZoomStep::Add(COARSE));
        input.key_zoom = Some(ZoomStep::Add(COARSE));
        input.reset_zoom = DEFAULT_ZOOM;
        view.set_input(input);
        // The arrows turn pages, as in 1.x, and do not nudge the page sideways.
        use remedy_ui::pages::PageCommand as P;
        let plain = |key| Chord::new(Modifiers::NONE, key);
        view.rebind(P::ScrollLeft, Vec::new());
        view.rebind(P::ScrollRight, Vec::new());
        view.rebind(P::PreviousPage, vec![plain(Key::ArrowLeft)]);
        view.rebind(P::NextPage, vec![plain(Key::ArrowRight)]);
        // The window's commands own the zoom keys.
        view.rebind(P::ZoomIn, Vec::new());
        view.rebind(P::ZoomOut, Vec::new());
        view.rebind(P::ResetZoom, Vec::new());
        if self.book.get_untracked().unwrap_or(false) {
            view.set_spread(Spread::Two);
        }
        // Adding text: a double click, or on a touch screen a long press.
        let shell = Rc::downgrade(self);
        let edit = move |hit: PageHit| {
            if let (Some(shell), Some((page, at))) = (shell.upgrade(), hit.page) {
                shell.text_at(page, at.x, at.y);
            }
        };
        if cfg!(target_os = "android") {
            view.on_long_press(edit);
        } else {
            view.on_double_tap(edit);
        }
        // Reader mode and phones: a tap near either side turns the page.
        let shell = Rc::downgrade(self);
        view.on_tap(move |hit| {
            let Some(shell) = shell.upgrade() else { return };
            if !(cfg!(target_os = "android") || shell.reader.get_untracked().unwrap_or(false)) {
                return;
            }
            let width = shell
                .stage
                .borrow()
                .as_ref()
                .and_then(El::bounds)
                .map_or(0.0, |b| b.width());
            if width > 0.0 {
                let across = hit.at.x / width;
                if let Some(view) = shell.view() {
                    if across <= 0.3 {
                        view.previous_page();
                    } else if across >= 0.7 {
                        view.next_page();
                    }
                }
            }
        });
        let label = file_name(&path);
        if let Some(stage) = self.stage.borrow().as_ref() {
            stage.clear();
            let pages = page_view(&self.ui, &view, label);
            stage.clone().child(pages.clone());
            // Keys go to the pages: scrolling, copying, selecting.
            self.ui
                .after(std::time::Duration::ZERO, move || pages.focus());
        }
        if let Some(page) = self.resume_page.take() {
            view.go_to_page(page.min(view.page_count().saturating_sub(1)));
        }
        let writable = !cfg!(target_os = "android");
        *self.open.borrow_mut() = Some(Open {
            document: Rc::new(document),
            view,
            path,
            writable,
        });
        let unsaved = self.resume_unsaved.take();
        if unsaved && let Some(open) = self.open.borrow_mut().as_mut() {
            open.writable = false;
        }
        self.dirty.set(unsaved);
        self.finding.set(false);
        self.recolor();
        self.changed.update(|n| *n += 1);
    }

    pub fn close_document(self: &Rc<Self>) {
        if self.current().is_none() {
            return;
        }
        self.keeping_changes("Save before closing the document?", |shell| {
            *shell.open.borrow_mut() = None;
            shell.dirty.set(false);
            shell.finding.set(false);
            if let Some(stage) = shell.stage.borrow().as_ref() {
                stage.clear();
                stage.clone().child(empty(&shell.ui));
            }
            shell.changed.update(|n| *n += 1);
            shell.say("Document closed");
        });
    }

    // ---- Saving ----

    pub fn save(self: &Rc<Self>) {
        self.save_then(|_| {});
    }

    /// Saves, and runs `then` only if the file was written.
    fn save_then(self: &Rc<Self>, then: impl FnOnce(&Handle) + 'static) {
        match self.current() {
            None => self.say("No document open."),
            Some(open)
                if open.writable
                    && open
                        .path
                        .extension()
                        .is_some_and(|e| e.eq_ignore_ascii_case("pdf")) =>
            {
                self.write(open.path, then);
            }
            Some(_) => self.save_as_then(then),
        }
    }

    pub fn save_as(self: &Rc<Self>) {
        if self.current().is_none() {
            self.say("No document open.");
            return;
        }
        self.save_as_then(|_| {});
    }

    fn save_as_then(self: &Rc<Self>, then: impl FnOnce(&Handle) + 'static) {
        let Some(open) = self.current() else { return };
        let suggested = open.path.with_extension("pdf");
        let mut dialog = FileDialog::default();
        dialog.title = "Save As PDF".into();
        dialog.save = true;
        dialog.directory = suggested.parent().map(Path::to_path_buf);
        dialog.file_name = Some(file_name(&suggested));
        dialog.filters = vec![("PDF".into(), vec!["pdf".into()])];
        let shell = self.clone();
        self.app
            .file_dialog(Some(&self.window), dialog, move |paths| {
                if let Some(path) = paths.into_iter().next() {
                    // What is written is always a PDF, so it is named as one.
                    let named = path
                        .extension()
                        .is_some_and(|e| e.eq_ignore_ascii_case("pdf"));
                    let path = if named {
                        path
                    } else {
                        path.with_extension("pdf")
                    };
                    shell.write(path, then);
                }
            });
    }

    fn write(self: &Rc<Self>, path: PathBuf, then: impl FnOnce(&Handle) + 'static) {
        let Some(open) = self.current() else { return };
        let done = move |shell: &Handle, path: PathBuf, result: Result<(), Error>| match result {
            Ok(()) => {
                if let Some(open) = shell.open.borrow_mut().as_mut() {
                    open.path.clone_from(&path);
                    // Where a Save dialog (or the desktop) pointed: later saves go there.
                    open.writable = true;
                }
                shell.dirty.set(false);
                shell.changed.update(|n| *n += 1);
                shell.say(format!("Saved {}", path.display()));
                then(shell);
            }
            // The file on disk and the edits in memory are both as they were.
            Err(e) => dialogs::problem(
                shell,
                format!("Save failed: {e}\nYour changes are still open."),
            ),
        };
        match &*open.document {
            Document::Pdf(file) => {
                let result = file.save(&path);
                done(self, path, result);
            }
            Document::Fixed(pages) => {
                self.busy.set(true);
                let (pages, to) = (pages.clone(), path.clone());
                let shell = self.clone();
                self.app.background(
                    move || pdf::export(&*pages, &to),
                    move |result| {
                        shell.busy.set(false);
                        done(&shell, path, result);
                    },
                );
            }
        }
    }

    // ---- Editing ----

    /// The page edits go to, if the document can be edited.
    fn editable(self: &Rc<Self>) -> Option<(Open, usize)> {
        let Some(open) = self.current() else {
            self.say("Open a document first.");
            return None;
        };
        if !matches!(*open.document, Document::Pdf(_)) {
            dialogs::problem(
                self,
                "This format is read-only. Use Save As to make a PDF, then open it to edit.".into(),
            );
            return None;
        }
        let page = open.view.current_page().get_untracked().unwrap_or(0);
        Some((open, page))
    }

    pub fn add_text(self: &Rc<Self>) {
        if let Some((_, page)) = self.editable() {
            self.text_at(page, 72.0, 72.0);
        }
    }

    fn text_at(self: &Rc<Self>, page: usize, x: f32, y: f32) {
        if self.editable().is_none() {
            return;
        }
        let title = format!("Add text at ({x:.0}, {y:.0}) on page {}", page + 1);
        dialogs::prompt(
            self,
            title,
            "Text to insert",
            String::new(),
            move |shell, text| {
                if text.is_empty() {
                    return;
                }
                let Some(open) = shell.current() else { return };
                let Document::Pdf(file) = &*open.document else {
                    return;
                };
                let result = file.add_text(page, x, y, &text, 12.0, [0, 0, 0]);
                shell.edited(&open.view, page, result, "Text added (remember to Save)");
            },
        );
    }

    pub fn add_image(self: &Rc<Self>) {
        let Some((_, page)) = self.editable() else {
            return;
        };
        let mut dialog = FileDialog::default();
        dialog.title = "Insert Image".into();
        let kinds = ["png", "jpg", "jpeg", "bmp", "webp"]
            .iter()
            .map(|e| (*e).to_owned())
            .collect();
        dialog.filters = vec![("Images".into(), kinds)];
        let shell = self.clone();
        self.app
            .file_dialog(Some(&self.window), dialog, move |paths| {
                let (Some(picture), Some(open)) = (paths.into_iter().next(), shell.current())
                else {
                    return;
                };
                let Document::Pdf(file) = &*open.document else {
                    return;
                };
                let page_size = remedy_ui::pages::PageSource::page_size(&**file, page);
                let corner = |side: f32| (side - 72.0).clamp(73.0, 272.0);
                let area = Rect::new(
                    72.0,
                    72.0,
                    corner(page_size.width),
                    corner(page_size.height),
                );
                let result = file.add_image(page, area, &picture);
                shell.edited(&open.view, page, result, "Image added (remember to Save)");
            });
    }

    fn edited(
        self: &Rc<Self>,
        view: &PageView,
        page: usize,
        result: Result<(), Error>,
        good: &str,
    ) {
        match result {
            Ok(()) => {
                view.pages_changed(&[page]);
                self.dirty.set(true);
                self.say(good);
            }
            Err(e) => dialogs::problem(self, format!("Could not change the page: {e}")),
        }
    }

    // ---- View ----

    pub fn zoom_by(&self, delta: f32) {
        if let Some(view) = self.view() {
            let now = view.zoom().get_untracked().unwrap_or(DEFAULT_ZOOM);
            view.set_fit(Fit::Free);
            view.set_zoom((now + delta).clamp(ZOOM_RANGE.0, ZOOM_RANGE.1), None);
        }
    }

    pub fn reset_zoom(self: &Rc<Self>) {
        if let Some(view) = self.view() {
            view.set_fit(Fit::Free);
            view.set_zoom(DEFAULT_ZOOM, None);
            self.say(format!("Zoom reset to {}%", percent(DEFAULT_ZOOM)));
        }
    }

    pub fn fit(self: &Rc<Self>, fit: Fit, name: &str) {
        if let Some(view) = self.view() {
            view.fit_once(fit);
            self.say(format!("Fit {name}"));
        }
    }

    fn apply_book(self: &Rc<Self>, on: bool) {
        self.save_prefs();
        if let Some(view) = self.view() {
            view.set_spread(if on { Spread::Two } else { Spread::Single });
            if on {
                // Both pages of the spread in sight.
                view.fit_once(Fit::Page);
                self.say("Book mode (both sides)");
            }
        }
    }

    pub fn rotate(&self, quarters: i32) {
        if let Some(view) = self.view() {
            const TURNS: [Rotation; 4] = [
                Rotation::None,
                Rotation::Clockwise,
                Rotation::Half,
                Rotation::CounterClockwise,
            ];
            let at = TURNS
                .iter()
                .position(|r| *r == view.rotation())
                .unwrap_or(0) as i32;
            view.set_rotation(TURNS[(at + quarters).rem_euclid(4) as usize]);
        }
    }

    fn recolor(&self) {
        if let Some(view) = self.view() {
            view.set_page_filter(look::page_colors(
                &self.theme.get_untracked().unwrap_or_default(),
                &self.filter.get_untracked().unwrap_or_default(),
                self.brightness.get_untracked().unwrap_or(1.0),
                self.contrast.get_untracked().unwrap_or(1.0),
            ));
        }
    }

    fn restyle(&self) {
        let id = self.theme.get_untracked().unwrap_or_default();
        let theme = look::find(&id).theme(self.scale.get_untracked().unwrap_or(1.0));
        self.app.set_theme(theme);
    }

    pub fn set_theme(self: &Rc<Self>, id: &str) {
        let chosen = look::find(id);
        self.theme.set(chosen.id.to_owned());
        self.restyle();
        self.recolor();
        self.save_prefs();
        self.say(format!("Theme: {} (text + page colors)", chosen.label));
    }

    pub fn cycle_theme(self: &Rc<Self>) {
        let now = self.theme.get_untracked().unwrap_or_default();
        self.set_theme(look::next(&now).id);
    }

    pub fn set_scale(self: &Rc<Self>, scale: f32) {
        self.scale.set(scale);
        self.restyle();
        self.save_prefs();
        self.say(format!("UI scale {}%", percent(scale)));
    }

    pub fn set_filter(self: &Rc<Self>, id: &str) {
        self.filter.set(id.to_owned());
        self.recolor();
        self.say(format!("Page: {}", look::filter_label(id)));
    }

    pub fn toggle_invert(self: &Rc<Self>) {
        let on = self.filter.get_untracked().is_ok_and(|f| f == "invert");
        self.set_filter(if on { "none" } else { "invert" });
    }

    pub fn adjust(self: &Rc<Self>, which: Signal<f32>, name: &str, delta: f32) {
        let value = (which.get_untracked().unwrap_or(1.0) + delta).clamp(0.5, 1.5);
        which.set(value);
        self.recolor();
        self.say(format!("{name} {}%", percent(value)));
    }

    pub fn reset_appearance(self: &Rc<Self>) {
        self.filter.set("none".into());
        self.brightness.set(1.0);
        self.contrast.set(1.0);
        self.recolor();
        self.say("Page appearance reset");
    }

    pub fn set_full_screen(self: &Rc<Self>, on: bool) {
        self.full.set(on);
        self.window.set_fullscreen(on);
        if on {
            self.say("Full screen (Esc or F11 to exit)");
        }
    }

    fn apply_reader(self: &Rc<Self>, on: bool) {
        if on {
            self.finding.set(false);
        }
        self.full.set(false);
        self.window.set_fullscreen(on);
        if !on {
            self.say("Reader mode off");
        }
    }

    pub fn toggle_full_screen(self: &Rc<Self>) {
        if self.reader.get_untracked().unwrap_or(false) {
            self.reader.set(false);
        } else {
            self.set_full_screen(!self.full.get_untracked().unwrap_or(false));
        }
    }

    /// Escape: leaves whatever is on top.
    fn escape(self: &Rc<Self>) {
        if self.finding.get_untracked().unwrap_or(false) {
            self.finding.set(false);
            if let Some(view) = self.view() {
                view.find("");
                view.clear_selection();
            }
        } else if self.reader.get_untracked().unwrap_or(false) {
            self.reader.set(false);
        } else if self.full.get_untracked().unwrap_or(false) {
            self.set_full_screen(false);
        }
    }

    // ---- Going places ----

    pub fn go_to(&self, page: usize) {
        if let Some(view) = self.view() {
            view.go_to_page(page.min(view.page_count().saturating_sub(1)));
        }
    }

    pub fn previous(&self) {
        if let Some(view) = self.view() {
            view.previous_page();
        }
    }

    pub fn next(&self) {
        if let Some(view) = self.view() {
            view.next_page();
        }
    }

    pub fn last(&self) {
        self.go_to(usize::MAX);
    }

    pub fn ask_page(self: &Rc<Self>) {
        let Some(view) = self.view() else { return };
        let total = view.page_count();
        let now = view.current_page().get_untracked().unwrap_or(0) + 1;
        dialogs::prompt(
            self,
            "Go to Page".into(),
            &format!("Page (1–{total})"),
            now.to_string(),
            move |shell, text| match text.trim().parse::<usize>() {
                Ok(n) if (1..=total).contains(&n) => shell.go_to(n - 1),
                _ => shell.say(format!("There is no page {}", text.trim())),
            },
        );
    }

    pub fn find(self: &Rc<Self>) {
        if self.current().is_none() {
            return;
        }
        self.finding.set(true);
        let shell = Rc::downgrade(self);
        // The bar is built on the next frame.
        self.ui.after(std::time::Duration::ZERO, move || {
            let field = shell.upgrade().and_then(|s| s.find_field.borrow().clone());
            if let Some(field) = field {
                field.el().focus();
                field.select_all();
            }
        });
    }

    // ---- The status line ----

    /// What the status line says when no message is passing.
    pub fn summary(&self) -> String {
        self.changed.get();
        let theme = look::find(&self.theme.get()).label;
        let Some(open) = self.current() else {
            return "Ready — Open PDF, EPUB, XPS, CBZ…".into();
        };
        let total = open.view.page_count();
        let page = open.view.current_page().get() + 1;
        let book = self.book.get();
        let name = file_name(&open.path);
        let kind = open
            .path
            .extension()
            .map_or_else(|| "PDF".into(), |e| e.to_string_lossy().to_uppercase());
        let dirty = if self.dirty.get() { " •" } else { "" };
        let pages = match (book && page < total).then_some(page + 1) {
            Some(other) => format!("Pages {page}–{other}/{total}"),
            None => format!("Page {page}/{total}"),
        };
        let zoom = percent(open.view.zoom().get());
        let mode = if book { "Book" } else { "Single" };
        let mut line = format!("{name}{dirty}  |  {kind}  |  {pages}  |  Zoom {zoom}%  |  {mode}");
        let filter = self.filter.get();
        if filter != "none" {
            line += &format!("  |  {}", look::filter_label(&filter));
        }
        let (b, c) = (self.brightness.get(), self.contrast.get());
        if (b - 1.0).abs() > 0.01 || (c - 1.0).abs() > 0.01 {
            line += &format!("  |  B{}/C{}", percent(b), percent(c));
        }
        line + &format!("  |  {theme}")
    }

    fn title(&self) -> String {
        self.changed.get();
        match self.current() {
            Some(open) => {
                let dirty = if self.dirty.get() { " •" } else { "" };
                format!("{}{dirty} — {NAME}", file_name(&open.path))
            }
            None => format!("{NAME} {VERSION}"),
        }
    }

    pub fn has_changes(&self) -> bool {
        self.dirty.get_untracked().unwrap_or(false)
    }
}

// ---- Commands, menus and the toolbar ----

type Act = fn(&Handle);

/// Every command: id, label, shortcuts, and what it does.
const COMMANDS: &[(&str, &str, &[&str], Act)] = &[
    ("open", "Open…", &["Primary+O"], |s| s.choose_file()),
    ("save", "Save", &["Primary+S"], |s| s.save()),
    ("save-as", "Save As…", &[], |s| s.save_as()),
    ("close", "Close Document", &["Primary+W"], |s| {
        s.close_document()
    }),
    ("quit", "Quit", &["Primary+Q"], |s| s.app.quit()),
    ("add-text", "Add Text…", &["Primary+T"], |s| s.add_text()),
    ("add-image", "Add Image…", &[], |s| s.add_image()),
    ("find", "Find…", &["Primary+F"], |s| s.find()),
    ("zoom-in", "Zoom In", &["Primary+=", "Primary++"], |s| {
        s.zoom_by(COARSE)
    }),
    ("zoom-out", "Zoom Out", &["Primary+-"], |s| {
        s.zoom_by(-COARSE)
    }),
    (
        "fine-in",
        "Fine Zoom In (1%)",
        &["Primary+Shift+=", "Primary+Alt+="],
        |s| s.zoom_by(FINE),
    ),
    (
        "fine-out",
        "Fine Zoom Out (1%)",
        &["Primary+Shift+-", "Primary+Alt+-"],
        |s| s.zoom_by(-FINE),
    ),
    ("reset-zoom", "Reset Zoom", &["Primary+0"], |s| {
        s.reset_zoom()
    }),
    ("fit-width", "Fit Width", &["Primary+1"], |s| {
        s.fit(Fit::Width, "width")
    }),
    ("fit-page", "Fit Page", &["Primary+2"], |s| {
        s.fit(Fit::Page, "page")
    }),
    ("fit-height", "Fit Height", &["Primary+3"], |s| {
        s.fit(Fit::Height, "height")
    }),
    ("book", "Book Mode", &["Primary+B"], |s| {
        s.book.update(|on| *on = !*on)
    }),
    ("full-screen", "Full Screen", &["F11"], |s| {
        s.toggle_full_screen()
    }),
    ("rotate-right", "Rotate Right", &["Primary+R"], |s| {
        s.rotate(1)
    }),
    ("rotate-left", "Rotate Left", &["Primary+Shift+R"], |s| {
        s.rotate(-1)
    }),
    ("cycle-theme", "Cycle Theme", &["Primary+Shift+T"], |s| {
        s.cycle_theme()
    }),
    (
        "high-contrast",
        "High Contrast",
        &["Primary+Shift+H"],
        |s| s.set_theme("high_contrast"),
    ),
    ("sepia", "Sepia (paper)", &["Primary+Shift+S"], |s| {
        s.set_theme("sepia")
    }),
    ("night", "Night (OLED)", &["Primary+Shift+N"], |s| {
        s.set_theme("night")
    }),
    ("invert", "Invert Page", &["Primary+Shift+I"], |s| {
        s.toggle_invert()
    }),
    (
        "brighter",
        "Brighter page",
        &["Primary+Shift+ArrowUp"],
        |s| s.adjust(s.brightness, "Brightness", 0.05),
    ),
    ("dimmer", "Dimmer page", &["Primary+Shift+ArrowDown"], |s| {
        s.adjust(s.brightness, "Brightness", -0.05)
    }),
    (
        "more-contrast",
        "More contrast",
        &["Primary+Alt+ArrowUp"],
        |s| s.adjust(s.contrast, "Contrast", 0.05),
    ),
    (
        "less-contrast",
        "Less contrast",
        &["Primary+Alt+ArrowDown"],
        |s| s.adjust(s.contrast, "Contrast", -0.05),
    ),
    (
        "reset-appearance",
        "Reset page appearance",
        &["Primary+Shift+0"],
        |s| s.reset_appearance(),
    ),
    ("redraw", "Redraw Page", &["F5"], |s| {
        if let Some(view) = s.view() {
            view.document_changed();
        }
    }),
    // These keys work wherever the focus is. A text field, or the page view scrolling a
    // zoomed page, takes them first.
    (
        "previous",
        "Previous Page",
        &[
            "ArrowLeft",
            "PageUp",
            "Shift+Space",
            "Alt+ArrowLeft",
            "Primary+PageUp",
        ],
        |s| s.previous(),
    ),
    (
        "next",
        "Next Page",
        &[
            "ArrowRight",
            "PageDown",
            "Space",
            "Alt+ArrowRight",
            "Primary+PageDown",
        ],
        |s| s.next(),
    ),
    ("first", "First Page", &["Home", "Primary+Home"], |s| {
        s.go_to(0)
    }),
    ("last", "Last Page", &["End", "Primary+End"], |s| s.last()),
    ("go-to", "Go to Page…", &["Primary+G"], |s| s.ask_page()),
    // Leaves the find bar, reader mode or full screen.
    ("leave", "Leave", &["Escape"], |s| {
        s.escape();
    }),
    ("check-updates", "Check for Updates…", &[], |s| {
        update::check_now(s)
    }),
    ("about", "About", &[], |s| dialogs::about(s)),
    ("shortcuts", "Keyboard Shortcuts", &[], |s| {
        dialogs::shortcuts(s)
    }),
];

fn register(shell: &Handle) {
    let primary = if shell.ui.platform() == Platform::Apple {
        "Cmd"
    } else {
        "Ctrl"
    };
    for (id, label, keys, act) in COMMANDS {
        let chords = keys
            .iter()
            .filter_map(|k| k.replace("Primary", primary).parse::<Chord>().ok())
            .collect();
        let weak = Rc::downgrade(shell);
        let act = *act;
        shell.commands.add(id, *label, chords, None, move || {
            if let Some(shell) = weak.upgrade() {
                act(&shell);
            }
        });
    }
    // Holding the key keeps going.
    for id in [
        "zoom-in", "zoom-out", "fine-in", "fine-out", "previous", "next", "brighter", "dimmer",
    ] {
        shell.commands.set_repeats(id, true);
    }
}

fn menus(shell: &Handle) -> Vec<MenuItem> {
    let item = |id: &str| shell.commands.menu_item(id);
    let items = |ids: &[&str]| -> Vec<MenuItem> {
        ids.iter()
            .map(|id| {
                if id.is_empty() {
                    MenuItem::separator()
                } else {
                    item(id)
                }
            })
            .collect()
    };
    let themes = look::LOOKS
        .iter()
        .map(|l| {
            let (s, s2, id) = (shell.clone(), shell.clone(), l.id);
            MenuItem::radio(
                l.label,
                move || s.theme.get() == id,
                move || s2.set_theme(id),
            )
        })
        .collect();
    let mut appearance: Vec<MenuItem> = look::FILTERS
        .iter()
        .map(|(id, label)| {
            let (s, s2, id) = (shell.clone(), shell.clone(), *id);
            MenuItem::radio(
                *label,
                move || s.filter.get() == id,
                move || s2.set_filter(id),
            )
        })
        .collect();
    appearance.push(MenuItem::separator());
    appearance.extend(items(&[
        "brighter",
        "dimmer",
        "more-contrast",
        "less-contrast",
        "reset-appearance",
    ]));
    let scales = SCALES
        .iter()
        .map(|(label, scale)| {
            let (s, s2, scale) = (shell.clone(), shell.clone(), *scale);
            MenuItem::radio(
                *label,
                move || (s.scale.get() - scale).abs() < 0.001,
                move || s2.set_scale(scale),
            )
        })
        .collect();

    let (b, b2) = (shell.clone(), shell.clone());
    let (f, f2) = (shell.clone(), shell.clone());
    let mut view = items(&[
        "zoom-in",
        "zoom-out",
        "fine-in",
        "fine-out",
        "reset-zoom",
        "",
        "fit-width",
        "fit-page",
        "fit-height",
        "",
    ]);
    view.push(
        MenuItem::check("Book Mode", move || b.book.get(), move |on| b2.book.set(on))
            .shortcut("Ctrl+B"),
    );
    view.push(
        MenuItem::check(
            "Full Screen",
            move || f.full.get(),
            move |on| f2.set_full_screen(on),
        )
        .shortcut("F11"),
    );
    view.extend(items(&["", "rotate-right", "rotate-left", ""]));
    view.push(MenuItem::submenu("Visibility Theme", themes));
    view.extend(items(&[
        "cycle-theme",
        "high-contrast",
        "sepia",
        "night",
        "",
    ]));
    view.push(MenuItem::submenu("Page Appearance", appearance));
    view.extend(items(&["invert", ""]));
    view.push(MenuItem::submenu("UI Scale", scales));
    view.push(item("redraw"));

    let (a, a2) = (shell.clone(), shell.clone());
    let mut help = items(&["about", "check-updates"]);
    help.push(MenuItem::check(
        "Install Updates Automatically",
        move || a.auto_update.get(),
        move |on| {
            a2.auto_update.set(on);
            a2.save_prefs();
            // Turning it on takes the update already found.
            if on && matches!(a2.update.get_untracked(), Ok(UpdateState::Available(_))) {
                update::download(&a2);
            }
        },
    ));
    help.push(item("shortcuts"));

    vec![
        MenuItem::submenu(
            "File",
            items(&["open", "save", "save-as", "close", "", "quit"]),
        ),
        MenuItem::submenu("Edit", items(&["add-text", "add-image", "find"])),
        MenuItem::submenu("View", view),
        MenuItem::submenu("Go", items(&["previous", "next", "first", "last", "go-to"])),
        MenuItem::submenu("Help", help),
    ]
}

fn toolbar(shell: &Handle) -> El {
    let ui = &shell.ui;
    let button = |label: &str, tip: &str, act: Act| {
        let weak = Rc::downgrade(shell);
        let el = w::button(ui, label.to_owned(), move || {
            if let Some(shell) = weak.upgrade() {
                act(&shell);
            }
        })
        .variant("quiet");
        w::tooltip(&el, tip.to_owned());
        el
    };
    let zoom = shell.clone();
    let book_button = w::toggle_button(ui, "Book", shell.book);
    w::tooltip(&book_button, "Book mode — two pages side by side (Ctrl+B)");
    let reader_button = w::toggle_button(ui, "Reader", shell.reader);
    w::tooltip(
        &reader_button,
        "Reader mode — only the page; tap the edges to turn (Esc to leave)",
    );
    w::wrap(ui)
        .gap(remedy_ui::view::Space::S1)
        .padding(remedy_ui::view::Space::S1)
        .align(Align::Center)
        .child(button("Open", "Open document (Ctrl+O)", |s| {
            s.choose_file()
        }))
        .child(button("Save", "Save (Ctrl+S)", |s| s.save()))
        .child(w::divider(ui, true))
        .child(button(
            "Zoom −",
            "Zoom out 15% (Ctrl+-); Ctrl+wheel for 1%",
            |s| s.zoom_by(-COARSE),
        ))
        .child(
            w::text(ui, move || {
                zoom.changed.get();
                let now = zoom.view().map_or(DEFAULT_ZOOM, |v| v.zoom().get());
                format!("{}%", percent(now))
            })
            .data_text(),
        )
        .child(button(
            "Zoom +",
            "Zoom in 15% (Ctrl++); Ctrl+wheel for 1%",
            |s| s.zoom_by(COARSE),
        ))
        .child(button("Reset", "Reset zoom (Ctrl+0)", |s| s.reset_zoom()))
        .child(button("Fit W", "Fit width (Ctrl+1)", |s| {
            s.fit(Fit::Width, "width")
        }))
        .child(button("Fit", "Fit page (Ctrl+2)", |s| {
            s.fit(Fit::Page, "page")
        }))
        .child(w::divider(ui, true))
        .child(book_button)
        .child(button(
            "Theme",
            "Cycle visibility theme (Ctrl+Shift+T)",
            |s| s.cycle_theme(),
        ))
        .child(button("Find", "Find (Ctrl+F)", |s| s.find()))
        .child(reader_button)
}

fn find_bar(shell: &Handle) -> El {
    let ui = shell.ui.clone();
    let field = w::text_input(&ui, "Find in document").placeholder("Find in document…");
    let weak = Rc::downgrade(shell);
    let asked: Rc<RefCell<String>> = Rc::default();
    let source = field.clone();
    let field = field.on_submit(move || {
        let Some(view) = weak.upgrade().and_then(|s| s.view()) else {
            return;
        };
        let text = source.value().trim().to_owned();
        // Enter again goes to the next match.
        if *asked.borrow() == text {
            view.find_next();
        } else {
            asked.borrow_mut().clone_from(&text);
            view.find(&text);
        }
    });
    *shell.find_field.borrow_mut() = Some(field.clone());
    let step = |forward: bool| {
        let weak = Rc::downgrade(shell);
        move || {
            if let Some(view) = weak.upgrade().and_then(|s| s.view()) {
                if forward {
                    view.find_next();
                } else {
                    view.find_previous();
                }
            }
        }
    };
    let status = shell.clone();
    let close = Rc::downgrade(shell);
    w::row(&ui)
        .gap(remedy_ui::view::Space::S2)
        .padding(remedy_ui::view::Space::S2)
        .align(Align::Center)
        .child(field.el().grow(1.0))
        .child(w::icon_button(
            &ui,
            w::Icon::ChevronUp,
            "Previous match",
            step(false),
        ))
        .child(w::icon_button(
            &ui,
            w::Icon::ChevronDown,
            "Next match",
            step(true),
        ))
        .child(
            w::text(&ui, move || {
                status.changed.get();
                let Some(view) = status.view() else {
                    return String::new();
                };
                let found = view.search_status().get();
                match (found.query.is_empty(), found.matches, found.done) {
                    (true, ..) => String::new(),
                    (_, 0, false) => "Searching…".into(),
                    (_, 1, true) => "1 match".into(),
                    (_, n, _) => match found.current {
                        Some(at) => format!("{} of {n}", at + 1),
                        None => format!("{n} matches"),
                    },
                }
            })
            .width(96.0),
        )
        .child(w::icon_button(
            &ui,
            w::Icon::Close,
            "Close find (Esc)",
            move || {
                if let Some(shell) = close.upgrade() {
                    shell.escape();
                }
            },
        ))
}

fn navigator(shell: &Handle) -> El {
    let ui = &shell.ui;
    let field = w::text_input(ui, "Page number");
    let weak = Rc::downgrade(shell);
    let source = field.clone();
    let field = field.on_submit(move || {
        let Some(shell) = weak.upgrade() else { return };
        match source.value().trim().parse::<usize>() {
            Ok(n) if n >= 1 => shell.go_to(n - 1),
            _ => shell.say("Type a page number"),
        }
    });
    // The field follows the page shown.
    let (shown, writer) = (shell.clone(), field.clone());
    let input = field.el().width(72.0).bind(move || {
        shown.changed.get();
        let page = shown.view().map_or(1, |v| v.current_page().get() + 1);
        writer.set_value(&page.to_string());
    });
    let total = shell.clone();
    let button = |label: &str, act: Act| {
        let weak = Rc::downgrade(shell);
        w::button(ui, label.to_owned(), move || {
            if let Some(shell) = weak.upgrade() {
                act(&shell);
            }
        })
    };
    w::row(ui)
        .gap(remedy_ui::view::Space::S2)
        .padding(remedy_ui::view::Space::S1)
        .align(Align::Center)
        .justify(remedy_ui::layout::Justify::Center)
        .child(button("◀ Prev", |s| s.previous()))
        .child(w::text(ui, "Page"))
        .child(input)
        .child(w::text(ui, move || {
            total.changed.get();
            format!("/ {}", total.view().map_or(1, |v| v.page_count()))
        }))
        .child(button("Next ▶", |s| s.next()).variant("primary"))
}

fn empty(ui: &Ui) -> El {
    let how = if cfg!(target_os = "android") {
        "Hold"
    } else {
        "Double-click"
    };
    w::empty_state(
        ui,
        "Open a PDF, EPUB, DOCX or image to begin",
        format!("{how} a page to add text"),
    )
    .grow(1.0)
}

fn footer(shell: &Handle) -> El {
    let ui = &shell.ui;
    let status = shell.clone();
    let line = w::text(ui, move || {
        status.message.get().unwrap_or_else(|| status.summary())
    })
    .variant("muted");
    let busy = shell.busy;
    let working = remedy_ui::view::show(ui, move || busy.get(), {
        let ui = ui.clone();
        move || w::spinner(&ui, "Working…")
    });
    w::row(ui)
        .gap(remedy_ui::view::Space::S2)
        .padding(remedy_ui::view::Space::S1)
        .align(Align::Center)
        .child(working)
        .child(line)
}

/// Fills a window with the app. `first` is a file to open at once.
pub fn build(app: &App, ui: &Ui, window: &Window, first: Option<PathBuf>) -> Handle {
    let prefs: Prefs = app
        .persist_store()
        .and_then(|s| s.load(&prefs_key()).ok().flatten())
        .unwrap_or_default();
    let shell = Rc::new(Shell {
        app: app.clone(),
        window: window.clone(),
        ui: ui.clone(),
        open: RefCell::new(None),
        changed: Signal::new(0),
        dirty: Signal::new(false),
        theme: Signal::new(prefs.theme),
        scale: Signal::new(prefs.scale.clamp(0.85, 1.75)),
        book: Signal::new(prefs.book),
        filter: Signal::new("none".into()),
        brightness: Signal::new(1.0),
        contrast: Signal::new(1.0),
        reader: Signal::new(false),
        full: Signal::new(false),
        finding: Signal::new(false),
        busy: Signal::new(false),
        message: Signal::new(None),
        said: Cell::new(0),
        commands: Commands::new(),
        update: Signal::new(UpdateState::Idle),
        auto_update: Signal::new(prefs.auto_update),
        update_failures: Cell::new(0),
        release: RefCell::new(None),
        downloaded: RefCell::new(None),
        resume_page: Cell::new(None),
        resume_unsaved: Cell::new(false),
        stage: RefCell::new(None),
        find_field: RefCell::new(None),
    });
    register(&shell);
    shell.commands.attach(ui);
    shell.restyle();

    let reader = shell.reader;
    let chrome = move || !reader.get();
    let owner = shell.clone();
    let menu = remedy_ui::view::show(ui, chrome, {
        let (ui, shell) = (ui.clone(), Rc::downgrade(&shell));
        move || match shell.upgrade() {
            Some(shell) => w::menu_bar(&ui, menus(&shell)),
            None => w::row(&ui),
        }
    });
    let tools = remedy_ui::view::show(ui, chrome, {
        let (ui, shell) = (ui.clone(), Rc::downgrade(&shell));
        move || shell.upgrade().map_or_else(|| w::row(&ui), |s| toolbar(&s))
    });
    let banner = remedy_ui::view::show(ui, chrome, {
        let (ui, shell) = (ui.clone(), Rc::downgrade(&shell));
        move || {
            shell
                .upgrade()
                .map_or_else(|| w::row(&ui), |s| update::banner(&s, &ui))
        }
    });
    let finder = shell.clone();
    let finding = shell.finding;
    let find = remedy_ui::view::show(ui, move || finding.get(), move || find_bar(&finder));
    let stage = w::column(ui).grow(1.0).fill_width().child(empty(ui));
    *shell.stage.borrow_mut() = Some(stage.clone());
    // The mouse's side buttons turn pages.
    let weak = Rc::downgrade(&shell);
    let stage = stage.on_pointer(move |e| {
        let Some(shell) = weak.upgrade() else {
            return false;
        };
        if e.phase != PointerPhase::Down {
            return false;
        }
        if e.buttons.contains(Buttons::BACK) {
            shell.previous();
        } else if e.buttons.contains(Buttons::FORWARD) {
            shell.next();
        } else {
            return false;
        }
        true
    });
    let nav = remedy_ui::view::show(ui, chrome, {
        let (ui, shell) = (ui.clone(), Rc::downgrade(&shell));
        move || {
            shell
                .upgrade()
                .map_or_else(|| w::row(&ui), |s| navigator(&s))
        }
    });
    let footer = remedy_ui::view::show(ui, chrome, {
        let (ui, shell) = (ui.clone(), Rc::downgrade(&shell));
        move || shell.upgrade().map_or_else(|| w::row(&ui), |s| footer(&s))
    });

    let title = shell.clone();
    let root = w::column(ui)
        .grow(1.0)
        .fill_width()
        .child(menu)
        .child(tools)
        .child(banner)
        .child(find)
        .child(stage)
        .child(nav)
        .child(footer);
    // What was last applied to the window and the pages, for Book and Reader mode.
    let applied = Cell::new((shell.book.get_untracked().unwrap_or(false), false));
    let book = shell.book;
    let (dirty, busy) = (shell.dirty, shell.busy);
    let waiting = Rc::downgrade(&shell);
    let root = root.bind(move || {
        if !dirty.get() && !busy.get() {
            let weak = waiting.clone();
            if let Some(shell) = waiting.upgrade() {
                shell.ui.after(std::time::Duration::ZERO, move || {
                    if let Some(shell) = weak.upgrade() {
                        update::install_when_safe(&shell);
                    }
                });
            }
        }
    });
    ui.root().child(root.bind(move || {
        let now = (book.get(), reader.get());
        let was = applied.replace(now);
        if was != now {
            let weak = Rc::downgrade(&title);
            // After this update: applying changes more of the window.
            title.ui.after(std::time::Duration::ZERO, move || {
                let Some(shell) = weak.upgrade() else { return };
                if was.0 != now.0 {
                    shell.apply_book(now.0);
                }
                if was.1 != now.1 {
                    shell.apply_reader(now.1);
                }
            });
        }
        let text = title.title();
        title.window.set_title(text);
        // The window holds the app's state for as long as it is open.
        let _ = &owner;
    }));

    let weak = Rc::downgrade(&shell);
    window.on_close_request(move |reason| {
        let Some(shell) = weak.upgrade() else {
            return true;
        };
        if !shell.has_changes() {
            return true;
        }
        shell.keeping_changes("Save before quitting?", move |shell| {
            shell.dirty.set(false);
            match reason {
                CloseReason::Quit => shell.app.quit_now(),
                _ => shell.window.close(),
            }
        });
        false
    });

    let mut first = first;
    let mut recovered = false;
    if let Some(note) = app.data_dir().and_then(|data| recovery::take(&data)) {
        let updated = note
            .updated
            .as_deref()
            .is_some_and(|v| v.trim_start_matches('v') == VERSION);
        // A note an update left is only for the version it installed.
        if note.updated.is_none() || updated {
            if updated {
                shell.say(format!("Updated to v{VERSION}"));
            }
            if let Some(path) = note.path.filter(|p| p.is_file()) {
                shell.resume_page.set(Some(note.page));
                recovered = note.unsaved;
                shell.resume_unsaved.set(note.unsaved);
                first = Some(path);
            }
        }
    }
    // Phones end apps out of sight without a word; this is the last moment to keep things.
    if cfg!(target_os = "android") {
        let weak = Rc::downgrade(&shell);
        app.on_leaving(move || {
            if let Some(shell) = weak.upgrade() {
                recovery::note(&shell, None);
            }
        });
        let handle = app.clone();
        app.on_return(move || {
            if let Some(data) = handle.data_dir() {
                // Back without having been ended: the note is not needed.
                recovery::forget(&data);
            }
        });
    }
    if recovered {
        shell.say("Your unsaved changes were recovered. Save to keep them.");
    }
    if let Some(path) = first {
        shell.load(path, None, 0);
    }
    shell
}

/// Runs the app: `first` is a document to open, `update_now` looks for an update at once.
pub fn launch(first: Option<PathBuf>, update_now: bool) -> Result<(), String> {
    let config = remedy_ui::AppConfig::new(NAME).app_id("com.ahmidarrow.remedypdf");
    remedy_ui::run(config, move |app| {
        let spec = remedy_ui::WindowSpec::new(NAME)
            .size(1100.0, 800.0)
            .min_size(320.0, 480.0)
            .persist_geometry("main");
        let handle = app.clone();
        app.open(spec, move |ui, window| {
            let shell = build(&handle, ui, window, first);
            // Tests build the window without this, so they never reach the network.
            update::start(&shell, update_now);
        });
    })
    .map_err(|e| e.to_string())
}

/// True for a file the app opens, by its extension.
pub fn opens(path: &Path) -> bool {
    path.extension()
        .is_some_and(|e| EXTENSIONS.iter().any(|k| e.eq_ignore_ascii_case(k)))
}
