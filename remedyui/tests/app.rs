//! The app driven as a person drives it: keys, buttons by name, and file dialogs.
//! `REMEDYPDF_SHOTS=<folder> cargo test --test app` also writes pictures of the window.

use remedy_ui::core::a11y::Role;
use remedy_ui::input::{Key, KeyEvent, Modifiers};
use remedy_ui::testing::TestApp;
use remedy_ui::{App, AppConfig, Window, WindowSpec};
use remedypdf::app::{self, Handle};
use remedypdf::pdf::PdfFile;
use remedypdf::secure;
use remedypdf::source::Tiles;
use std::cell::RefCell;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::time::Duration;

struct Driver {
    app: TestApp,
    shell: Handle,
    window: Window,
}

impl Driver {
    fn new() -> Driver {
        Driver::start(AppConfig::new("RemedyPDF test"))
    }

    /// Keeping the app's data in `data`, as one installed copy does from run to run.
    fn with_data(data: &Path) -> Driver {
        Driver::start(AppConfig::new("RemedyPDF test").data_dir(data))
    }

    fn start(config: AppConfig) -> Driver {
        let made: Rc<RefCell<Option<(Handle, Window)>>> = Rc::default();
        let out = made.clone();
        let mut app = TestApp::new(config, move |application: &App| {
            let handle = application.clone();
            application.open(
                WindowSpec::new("RemedyPDF").size(1100.0, 800.0),
                move |ui, window| {
                    let shell = app::build(&handle, ui, window, None);
                    *out.borrow_mut() = Some((shell, window.clone()));
                },
            );
        });
        app.frames(3);
        let (shell, window) = made.borrow_mut().take().expect("the window was built");
        Driver { app, shell, window }
    }

    /// Runs frames (background work included) until `done`.
    fn wait(&mut self, what: &str, done: impl Fn(&Driver) -> bool) {
        for _ in 0..1500 {
            self.app.frames(1);
            if done(self) {
                self.app.frames(2);
                return;
            }
            std::thread::sleep(Duration::from_millis(4));
        }
        panic!(
            "never happened: {what}; status is {:?}; screen: {:?}",
            self.shell.summary(),
            self.words()
        );
    }

    /// Every name and value a screen reader meets.
    fn words(&self) -> Vec<String> {
        let ui = self.app.ui().expect("a window");
        ui.reader_view()
            .into_iter()
            .filter_map(|n| n.name.or(n.value))
            .collect()
    }

    fn shows(&self, text: &str) -> bool {
        self.words().iter().any(|w| w.contains(text))
    }

    fn status(&self) -> String {
        self.shell.summary()
    }

    fn ctrl(&mut self, key: Key) {
        self.chord(
            Modifiers {
                ctrl: true,
                ..Modifiers::NONE
            },
            key,
        );
    }

    fn chord(&mut self, modifiers: Modifiers, key: Key) {
        let mut event = KeyEvent::press(key);
        event.modifiers = modifiers;
        self.app.key(event);
        self.app.frames(3);
    }

    fn key(&mut self, key: Key) {
        self.chord(Modifiers::NONE, key);
    }

    fn press(&mut self, name: &str) {
        assert!(
            self.app.press(Role::Button, name),
            "no button {name:?} in {:?}",
            self.words()
        );
        self.app.frames(3);
    }

    /// What the person will pick in the next file dialog.
    fn will_pick(&mut self, path: &Path) {
        self.app.host().answer_dialog(vec![path.to_path_buf()]);
    }

    fn open(&mut self, path: &Path, pages: usize) {
        self.will_pick(path);
        self.press("Open");
        let name = path.file_name().unwrap().to_string_lossy().into_owned();
        self.wait("the document opens", |d| {
            d.status().starts_with(&name) && d.status().contains(&format!("/{pages}  |"))
        });
    }

    fn shot(&mut self, name: &str) {
        let Some(folder) = std::env::var_os("REMEDYPDF_SHOTS") else {
            return;
        };
        // Give the page tiles time to arrive.
        for _ in 0..150 {
            self.app.frames(1);
            std::thread::sleep(Duration::from_millis(5));
        }
        type Picture = Rc<RefCell<Option<remedy_ui::paint::Image>>>;
        let taken: Picture = Rc::default();
        let out = taken.clone();
        self.window
            .snapshot(move |picture| *out.borrow_mut() = picture);
        self.app.frames(3);
        let picture = taken.borrow_mut().take().expect("a snapshot");
        let pixels =
            image::RgbaImage::from_raw(picture.width, picture.height, picture.pixels.to_vec())
                .unwrap();
        pixels
            .save(PathBuf::from(folder).join(format!("{name}.png")))
            .unwrap();
    }
}

/// A three-page PDF with a line of text on each page.
fn pdf() -> Vec<u8> {
    let mut out = String::from("%PDF-1.7\n1 0 obj <</Type/Catalog/Pages 2 0 R>> endobj\n");
    out += "2 0 obj <</Type/Pages/Kids[10 0 R 11 0 R 12 0 R]/Count 3>> endobj\n";
    out += "5 0 obj <</Type/Font/Subtype/Type1/BaseFont/Helvetica>> endobj\n";
    for (n, word) in ["Alpha", "Bravo", "Charlie"].iter().enumerate() {
        let content = format!("BT /F 36 Tf 72 640 Td ({word} page of the report) Tj ET");
        out += &format!(
            "{} 0 obj <</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents {} 0 R/Resources<</Font<</F 5 0 R>>>>>> endobj\n",
            10 + n,
            20 + n
        );
        out += &format!(
            "{} 0 obj <</Length {}>>\nstream\n{content}\nendstream endobj\n",
            20 + n,
            content.len()
        );
    }
    out += "trailer <</Size 30/Root 1 0 R>>\n%%EOF";
    out.into_bytes()
}

fn text_of(path: &Path, password: Option<&str>) -> String {
    let file = PdfFile::open(path, password).expect("the saved file opens");
    let runs = file.runs(0).expect("text on the first page").runs;
    runs.into_iter()
        .map(|r| r.text)
        .collect::<Vec<_>>()
        .join(" ")
}

#[test]
fn viewing_a_document() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join("Report.pdf");
    std::fs::write(&path, pdf()).unwrap();
    let mut d = Driver::new();
    assert!(
        d.shows("Open a PDF, EPUB, DOCX or image to begin"),
        "{:?}",
        d.words()
    );
    assert!(d.status().starts_with("Ready"));
    d.shot("empty");

    d.open(&path, 3);
    assert!(
        d.status()
            .contains("PDF  |  Page 1/3  |  Zoom 125%  |  Single"),
        "{}",
        d.status()
    );
    d.shot("open");

    d.key(Key::ArrowRight);
    assert!(d.status().contains("Page 2/3"), "{}", d.status());
    d.key(Key::ArrowLeft);
    assert!(d.status().contains("Page 1/3"), "{}", d.status());
    d.ctrl(Key::End);
    assert!(d.status().contains("Page 3/3"), "{}", d.status());
    d.press("◀ Prev");
    assert!(d.status().contains("Page 2/3"), "{}", d.status());
    d.press("Next ▶");
    d.ctrl(Key::Home);
    assert!(d.status().contains("Page 1/3"), "{}", d.status());

    // Go to a page by number.
    d.ctrl(Key::char('g'));
    assert!(d.shows("Page (1–3)"), "{:?}", d.words());
    d.ctrl(Key::char('a'));
    d.app.type_text("3");
    d.key(Key::Enter);
    assert!(d.status().contains("Page 3/3"), "{}", d.status());
    d.ctrl(Key::Home);

    // Zoom in coarse and fine steps, and back.
    d.ctrl(Key::char('='));
    assert!(d.status().contains("Zoom 140%"), "{}", d.status());
    d.chord(
        Modifiers {
            ctrl: true,
            shift: true,
            ..Modifiers::NONE
        },
        Key::char('='),
    );
    assert!(d.status().contains("Zoom 141%"), "{}", d.status());
    d.ctrl(Key::char('-'));
    assert!(d.status().contains("Zoom 126%"), "{}", d.status());
    d.ctrl(Key::char('0'));
    assert!(d.status().contains("Zoom 125%"), "{}", d.status());
    d.ctrl(Key::char('2'));
    assert!(
        !d.status().contains("Zoom 125%"),
        "fit page changes the zoom: {}",
        d.status()
    );

    // Book mode shows two pages.
    d.ctrl(Key::char('b'));
    d.wait("book mode", |d| {
        d.status().contains("Pages 1–2/3") && d.status().contains("Book")
    });
    d.shot("book");
    d.ctrl(Key::char('b'));
    d.wait("single pages", |d| d.status().contains("Single"));

    // Themes cycle in order and are named in the status line.
    d.chord(
        Modifiers {
            ctrl: true,
            shift: true,
            ..Modifiers::NONE
        },
        Key::char('t'),
    );
    assert!(d.status().ends_with("Dark"), "{}", d.status());
    d.ctrl(Key::char('2'));
    d.shot("dark");
    d.chord(
        Modifiers {
            ctrl: true,
            shift: true,
            ..Modifiers::NONE
        },
        Key::char('s'),
    );
    assert!(d.status().ends_with("Sepia (paper)"), "{}", d.status());
    d.chord(
        Modifiers {
            ctrl: true,
            shift: true,
            ..Modifiers::NONE
        },
        Key::char('i'),
    );
    assert!(d.status().contains("Invert page"), "{}", d.status());
    d.chord(
        Modifiers {
            ctrl: true,
            shift: true,
            ..Modifiers::NONE
        },
        Key::ArrowUp,
    );
    assert!(d.status().contains("B105/C100"), "{}", d.status());
    d.chord(
        Modifiers {
            ctrl: true,
            shift: true,
            ..Modifiers::NONE
        },
        Key::char('0'),
    );
    assert!(
        !d.status().contains("Invert") && !d.status().contains("B105"),
        "{}",
        d.status()
    );

    // Find.
    d.ctrl(Key::char('f'));
    d.app.type_text("bravo");
    d.key(Key::Enter);
    d.wait("a match", |d| d.shows("1 match") || d.shows("1 of 1"));
    d.shot("find");
    d.key(Key::Escape);
    assert!(!d.shows("Close find"), "{:?}", d.words());

    // Reader mode leaves only the page; Escape brings the rest back.
    assert!(
        d.app.press(Role::Button, "Reader") || d.app.press(Role::Switch, "Reader"),
        "{:?}",
        d.words()
    );
    d.wait("the chrome hides", |d| {
        !d.shows("Next ▶") && !d.shows("Fit W")
    });
    d.shot("reader");
    d.key(Key::Escape);
    d.wait("the chrome returns", |d| {
        d.shows("Next ▶") && d.shows("Fit W")
    });

    d.ctrl(Key::char('w'));
    assert!(d.status().starts_with("Ready"), "{}", d.status());
}

#[test]
fn editing_saving_and_not_losing_changes() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join("Draft.pdf");
    std::fs::write(&path, pdf()).unwrap();
    let mut d = Driver::new();
    d.open(&path, 3);

    d.ctrl(Key::char('t'));
    assert!(d.shows("Add text at (72, 72) on page 1"), "{:?}", d.words());
    d.shot("add-text");
    d.app.type_text("Written in the test");
    d.key(Key::Enter);
    assert!(d.status().contains("Draft.pdf •"), "{}", d.status());
    assert!(d.shell.has_changes());
    assert!(
        !text_of(&path, None).contains("Written"),
        "nothing is written before Save"
    );

    // Closing asks, and Cancel keeps everything.
    d.ctrl(Key::char('w'));
    assert!(d.shows("You have unsaved changes"), "{:?}", d.words());
    d.shot("unsaved");
    d.press("Cancel");
    assert!(d.shell.has_changes() && d.status().starts_with("Draft.pdf"));

    d.ctrl(Key::char('s'));
    assert!(!d.shell.has_changes(), "{}", d.status());
    assert!(text_of(&path, None).contains("Written in the test"));

    // A picture goes on the page through the file dialog.
    let picture = folder.path().join("dot.png");
    image::RgbImage::from_pixel(20, 20, image::Rgb([200, 0, 0]))
        .save(&picture)
        .unwrap();
    let before = std::fs::metadata(&path).unwrap().len();
    assert!(
        d.app.press(Role::MenuItem, "Edit") || d.app.press(Role::Button, "Edit"),
        "{:?}",
        d.words()
    );
    d.app.frames(3);
    d.will_pick(&picture);
    assert!(d.app.press(Role::MenuItem, "Add Image…"), "{:?}", d.words());
    d.app.frames(3);
    assert!(d.shell.has_changes(), "{:?}", d.words());
    d.ctrl(Key::char('s'));
    assert!(std::fs::metadata(&path).unwrap().len() > before);

    // Discard really discards.
    d.ctrl(Key::char('t'));
    d.app.type_text("Thrown away");
    d.key(Key::Enter);
    d.ctrl(Key::char('w'));
    d.press("Discard");
    assert!(d.status().starts_with("Ready"), "{}", d.status());
    assert!(!text_of(&path, None).contains("Thrown"));
}

#[test]
fn a_protected_file_asks_for_its_password_and_stays_protected() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join("Locked.pdf");
    let locked = secure::protect(&pdf(), "open sesame", lopdf::Permissions::all()).unwrap();
    std::fs::write(&path, locked).unwrap();
    PdfFile::open(&path, Some("open sesame"))
        .map(|_| ())
        .expect("the fixture unlocks");
    let mut d = Driver::new();
    d.will_pick(&path);
    d.press("Open");
    d.wait("the password prompt", |d| {
        d.shows("This file is password-protected.")
    });
    d.app.type_text("wrong");
    d.key(Key::Enter);
    d.wait("a second try", |d| d.shows("Incorrect password"));
    d.shot("password");
    d.app.type_text("open sesame");
    d.key(Key::Enter);
    d.wait("it opens", |d| d.status().starts_with("Locked.pdf"));
    d.ctrl(Key::char('t'));
    d.app.type_text("Still secret");
    d.key(Key::Enter);
    d.ctrl(Key::char('s'));
    assert!(PdfFile::open(&path, None).is_err(), "still protected");
    assert!(text_of(&path, Some("open sesame")).contains("Still secret"));
}

#[test]
fn other_formats_are_read_only_and_save_as_pdf() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join("notes.txt");
    std::fs::write(&path, "Plain notes\nsecond line\n").unwrap();
    let mut d = Driver::new();
    d.open(&path, 1);
    d.shot("text");
    d.ctrl(Key::char('t'));
    assert!(d.shows("This format is read-only"), "{:?}", d.words());
    d.press("OK");
    // Save on a text file asks where to put the PDF.
    let out = folder.path().join("notes-copy");
    d.will_pick(&out);
    d.ctrl(Key::char('s'));
    d.wait("the export", |d| d.status().starts_with("notes-copy.pdf"));
    assert!(out.with_extension("pdf").is_file());
    assert_eq!(
        std::fs::read_to_string(&path).unwrap(),
        "Plain notes\nsecond line\n",
        "the source is untouched"
    );

    // A file that cannot be read says so and keeps what is open.
    let broken = folder.path().join("broken.pdf");
    std::fs::write(&broken, "not a pdf").unwrap();
    d.will_pick(&broken);
    d.press("Open");
    d.wait("the error", |d| d.shows("Could not open broken.pdf"));
    d.press("OK");
    assert!(d.status().starts_with("notes-copy.pdf"), "{}", d.status());
}

#[test]
fn about_and_shortcuts() {
    let mut d = Driver::new();
    assert!(
        d.app.press(Role::MenuItem, "Help") || d.app.press(Role::Button, "Help"),
        "{:?}",
        d.words()
    );
    d.app.frames(3);
    assert!(d.app.press(Role::MenuItem, "About"), "{:?}", d.words());
    d.app.frames(3);
    assert!(d.shows("Hi I'm Ahmi, hope this helps!"), "{:?}", d.words());
    d.shot("about");
    assert!(d.app.press(Role::Link, "GitHub profile"));
    d.app.frames(3);
    assert_eq!(
        d.app.host().opened_urls(),
        ["https://github.com/AhmiDarrow"]
    );
    d.press("Close");
    assert!(!d.shows("Hi I'm Ahmi"));
    assert!(d.app.press(Role::MenuItem, "Help") || d.app.press(Role::Button, "Help"));
    d.app.frames(3);
    assert!(
        d.app.press(Role::MenuItem, "Keyboard Shortcuts"),
        "{:?}",
        d.words()
    );
    d.app.frames(3);
    assert!(d.shows("Ctrl+Scroll"), "{:?}", d.words());
}

#[test]
fn leaving_keeps_unsaved_changes_for_the_next_start() {
    let folder = tempfile::tempdir().unwrap();
    let data = folder.path().join("data");
    let path = folder.path().join("Leaving.pdf");
    std::fs::write(&path, pdf()).unwrap();
    {
        let mut d = Driver::with_data(&data);
        d.open(&path, 3);
        d.key(Key::ArrowRight);
        d.ctrl(Key::char('t'));
        d.app.type_text("Kept while away");
        d.key(Key::Enter);
        // What Android's leaving does.
        app::recovery::note(&d.shell, None);
    }
    assert!(
        !text_of(&path, None).contains("Kept"),
        "the file itself is untouched"
    );
    let mut d = Driver::with_data(&data);
    d.wait("the work comes back", |d| {
        d.status().starts_with("Leaving.pdf •") && d.status().contains("Page 2/3")
    });
    assert!(d.shell.has_changes());
    // Saving asks where, rather than writing the recovery copy.
    let out = folder.path().join("Saved.pdf");
    d.will_pick(&out);
    d.ctrl(Key::char('s'));
    assert!(!d.shell.has_changes(), "{}", d.status());
    let saved = PdfFile::open(&out, None).unwrap();
    let page_two = saved
        .runs(1)
        .unwrap()
        .runs
        .into_iter()
        .map(|r| r.text)
        .collect::<Vec<_>>()
        .join(" ");
    assert!(page_two.contains("Kept while away"), "{page_two}");
    // The note was used up: a third start opens empty.
    let d = Driver::with_data(&data);
    assert!(d.status().starts_with("Ready"), "{}", d.status());
}
