pub mod app;
pub mod document;
pub mod pdf;
pub mod pictures;
pub mod reflow;
pub mod secure;
pub mod source;
pub mod svg;
pub mod xps;
pub mod zipped;

/// The APK loads the library and starts here.
#[cfg(target_os = "android")]
fn android_start() {
    if let Err(e) = app::launch(None, false) {
        remedy_ui::android::log(&format!("RemedyPDF: {e}"));
    }
}

#[cfg(target_os = "android")]
remedy_ui::android::main!(android_start);
