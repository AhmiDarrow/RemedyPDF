//! The app's dialogs: questions, prompts, About and the shortcut list.

use super::{Handle, NAME, VERSION};
use remedy_ui::layout::{Align, Justify};
use remedy_ui::view::Space;
use remedy_ui::widgets::{self as w, DialogButton, Modal};
use remedy_ui::{El, Ui};
use std::cell::RefCell;
use std::path::PathBuf;
use std::rc::Rc;
use std::time::Duration;

const PROFILE: &str = "https://github.com/AhmiDarrow";
const REPOSITORY: &str = "https://github.com/AhmiDarrow/RemedyPDF";
const RELEASES: &str = "https://github.com/AhmiDarrow/RemedyPDF/releases";
const PATREON: &str = "https://www.patreon.com/cw/AhmiDarrow";
const MARK: &[u8] = include_bytes!("../../../resources/logo_ui.png");

pub fn problem(shell: &Handle, message: String) {
    w::dialog(
        &shell.ui,
        NAME,
        message,
        vec![DialogButton::new("OK", "primary", || {})],
    );
}

/// Save, Discard or Cancel. `then` runs after a save that worked, or after Discard.
pub fn unsaved(shell: &Handle, question: &str, then: impl Fn(&Handle) + Clone + 'static) {
    let (save, discard) = (Rc::downgrade(shell), Rc::downgrade(shell));
    let after = then.clone();
    w::dialog(
        &shell.ui,
        NAME,
        format!("You have unsaved changes.\n\n{question}"),
        vec![
            DialogButton::new("Save", "primary", move || {
                if let Some(shell) = save.upgrade() {
                    let after = after.clone();
                    shell.save_then(move |shell| after(shell));
                }
            }),
            DialogButton::new("Discard", "danger", move || {
                if let Some(shell) = discard.upgrade() {
                    shell.dirty.set(false);
                    then(&shell);
                }
            }),
            DialogButton::new("Cancel", "quiet", || {}),
        ],
    );
}

/// A line of text with OK and Cancel. `done` runs on OK or Enter.
fn ask(
    shell: &Handle,
    title: String,
    message: String,
    field: remedy_ui::view::TextField,
    done: impl Fn(&Handle, String) + 'static,
) {
    let ui = &shell.ui;
    let slot: Rc<RefCell<Option<Modal>>> = Rc::default();
    let submit: Rc<dyn Fn()> = {
        let (slot, weak, field) = (slot.clone(), Rc::downgrade(shell), field.clone());
        Rc::new(move || {
            // The one way to read a secret field; for other fields it is a copy of the text.
            let text = field.take_secret().expose().to_owned();
            let open = slot.borrow_mut().take();
            if let Some(modal) = open {
                modal.close();
                if let Some(shell) = weak.upgrade() {
                    done(&shell, text);
                }
            }
        })
    };
    let enter = submit.clone();
    let field = field.on_submit(move || enter());
    let cancel = slot.clone();
    let buttons = w::row(ui)
        .gap(Space::S2)
        .justify(Justify::End)
        .child(w::button(ui, "Cancel", move || {
            let open = cancel.borrow_mut().take();
            if let Some(modal) = open {
                modal.close();
            }
        }))
        .child(w::button(ui, "OK", move || submit()).variant("primary"));
    let content = w::column(ui)
        .gap(Space::S3)
        .child(w::heading(ui, 2, title.clone()))
        .child(w::text(ui, message))
        .child(field.el())
        .child(buttons);
    *slot.borrow_mut() = Some(w::modal(ui, title, content, true));
    let target = field.clone();
    ui.after(Duration::ZERO, move || {
        target.el().focus();
        target.select_all();
    });
}

pub fn prompt(
    shell: &Handle,
    title: String,
    label: &str,
    start: String,
    done: impl Fn(&Handle, String) + 'static,
) {
    let field = w::text_input(&shell.ui, label.to_owned());
    field.set_value(&start);
    ask(shell, title, label.to_owned(), field, done);
}

pub fn password(shell: &Handle, path: PathBuf, tries: u32) {
    let message = if tries == 0 {
        "This file is password-protected."
    } else {
        "Incorrect password — try again."
    };
    let field = w::secret_input(&shell.ui, "Password");
    ask(
        shell,
        NAME.into(),
        message.into(),
        field,
        move |shell, password| {
            shell.load(path.clone(), Some(password), tries + 1);
        },
    );
}

fn link(ui: &Ui, shell: &Handle, label: &str, url: &'static str) -> El {
    let app = shell.app.clone();
    w::link(ui, label.to_owned(), move || app.open_url(url, |_| {}))
}

fn mark(ui: &Ui) -> Option<El> {
    let mut picture = image::load_from_memory(MARK)
        .ok()?
        .thumbnail(280, 280)
        .into_rgba8();
    for p in picture.pixels_mut() {
        let a = u32::from(p.0[3]);
        for c in &mut p.0[..3] {
            *c = ((u32::from(*c) * a + 127) / 255) as u8;
        }
    }
    let (width, height) = picture.dimensions();
    let picture = remedy_ui::paint::Image::new(width, height, picture.into_raw().into());
    // The mark keeps its own shape.
    let shown = 140.0;
    let tall = shown * height as f32 / width.max(1) as f32;
    Some(
        w::image(ui, picture, "RemedyPDF logo")
            .width(shown)
            .height(tall),
    )
}

fn closing(shell: &Handle, title: &str, body: El) {
    let ui = &shell.ui;
    let slot: Rc<RefCell<Option<Modal>>> = Rc::default();
    let close = slot.clone();
    let content = w::column(ui).gap(Space::S3).child(body).child(
        w::row(ui).justify(Justify::End).child(
            w::button(ui, "Close", move || {
                let open = close.borrow_mut().take();
                if let Some(modal) = open {
                    modal.close();
                }
            })
            .variant("primary"),
        ),
    );
    *slot.borrow_mut() = Some(w::modal(ui, title, content, true));
}

pub fn about(shell: &Handle) {
    let ui = &shell.ui;
    let mut words = w::column(ui)
        .gap(Space::S2)
        .grow(1.0)
        .child(w::heading(ui, 2, format!("About {NAME}")))
        .child(w::text(ui, "Hi I'm Ahmi, hope this helps!"))
        .child(w::text(
            ui,
            "Fast multi-format document viewer and editor — PDF, EPUB, XPS, CBZ, and more. \
             Remedy themes, both-sides book mode, fine zoom, touch support. MIT licensed.",
        ))
        .child(w::text(ui, format!("Version {VERSION}")).variant("muted"))
        .child(w::text(ui, "by Ahmi Darrow").variant("muted"));
    words = words.child(
        w::wrap(ui)
            .gap(Space::S3)
            .child(link(ui, shell, "GitHub profile", PROFILE))
            .child(link(ui, shell, "Project repo", REPOSITORY))
            .child(link(ui, shell, "Releases", RELEASES))
            .child(link(ui, shell, "Patreon", PATREON)),
    );
    let state = shell.update;
    let check = Rc::downgrade(shell);
    words = words
        .child(w::text(ui, move || super::update::describe(&state.get())).variant("muted"))
        .child(
            w::row(ui).child(w::button(ui, "Check for updates", move || {
                if let Some(shell) = check.upgrade() {
                    super::update::check_now(&shell);
                }
            })),
        );
    let mut row = w::row(ui).gap(Space::S3).align(Align::Start);
    if let Some(mark) = mark(ui) {
        row = row.child(mark);
    }
    closing(shell, "About", row.child(words));
}

const SHORTCUTS: [(&str, &[&str]); 4] = [
    (
        "Navigation",
        &[
            "← / → — previous / next page (spreads in Book mode)",
            "PgUp / PgDn / Space — scroll, turning at the edge of the page",
            "Home / End — first / last",
            "Alt+← / Alt+→ — previous / next page",
            "Mouse back / forward buttons — previous / next page",
            "Mouse wheel or swipe — turns pages in fit view, scrolls inside zoomed pages",
            "Ctrl+G — go to page",
            "Ctrl+W — close document",
        ],
    ),
    (
        "Zoom",
        &[
            "Ctrl++ / Ctrl+- — 15% steps",
            "Ctrl+Scroll — 1% fine zoom at the pointer; add Shift for 15%",
            "Ctrl+Shift++ / Ctrl+Shift+- — 1% fine zoom",
            "Ctrl+0 — reset zoom",
        ],
    ),
    (
        "View",
        &[
            "Ctrl+B — Book mode (both sides)",
            "Ctrl+R / Ctrl+Shift+R — rotate view right / left",
            "Ctrl+1 / 2 / 3 — fit width / page / height",
            "F11 — full screen",
            "F5 — redraw the page",
            "Ctrl+Shift+T — cycle theme (9 themes)",
            "Ctrl+Shift+H / S / N — high contrast / sepia / night",
            "Ctrl+Shift+I — invert page colors",
            "Ctrl+Shift+↑ / ↓ — page brightness",
            "Ctrl+Alt+↑ / ↓ — page contrast",
            "Ctrl+Shift+0 — reset page appearance",
            "Ctrl+F — find",
        ],
    ),
    (
        "Edit",
        &[
            "Double-click a page (desktop) or hold it (touch) — add text there",
            "Ctrl+T — add text",
            "Ctrl+O / Ctrl+S — open / save",
        ],
    ),
];

pub fn shortcuts(shell: &Handle) {
    let ui = &shell.ui;
    let mut list = w::column(ui).gap(Space::S1);
    for (group, lines) in SHORTCUTS {
        list = list.child(w::heading(ui, 3, group));
        for line in lines {
            list = list.child(w::text(ui, *line));
        }
    }
    let height = (ui.window_size().height - 200.0).clamp(160.0, 520.0);
    closing(
        shell,
        "Keyboard Shortcuts",
        w::scroll(ui).height(height).child(list),
    );
}
