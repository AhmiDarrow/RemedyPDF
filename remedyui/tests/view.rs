//! A real PDF in RemedyUI's page view: it renders, and the view's search finds its text.

use remedy_ui::pages::{PageSource, PageView, page_view};
use remedy_ui::testing::TestApp;
use remedy_ui::{App, AppConfig, WindowSpec};
use remedypdf::pdf::{Error, PdfFile};
use std::sync::Arc;
use std::time::Duration;

// No xref table: PDFium rebuilds it.
const PDF: &str = "%PDF-1.7
1 0 obj <</Type/Catalog/Pages 2 0 R>> endobj
2 0 obj <</Type/Pages/Kids[3 0 R]/Count 1>> endobj
3 0 obj <</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F 5 0 R>>>>>> endobj
4 0 obj <</Length 44>>
stream
BT /F 24 Tf 72 700 Td (Quarterly report) Tj ET
endstream endobj
5 0 obj <</Type/Font/Subtype/Type1/BaseFont/Helvetica>> endobj
trailer <</Size 6/Root 1 0 R>>
%%EOF";

#[test]
fn a_pdf_shows_in_the_page_view() {
    let file = Arc::new(PdfFile::from_bytes(PDF.as_bytes().to_vec(), None).unwrap());
    assert_eq!(file.page_count(), 1);
    assert!(!file.is_protected());

    let mut app = TestApp::new(AppConfig::new("Test").cpu_only(), |app: &App| {
        app.open(WindowSpec::new("Test").size(800.0, 600.0), |_, _| {});
    });
    let ui = app.ui().expect("the window is open");
    let view = PageView::new(file);
    ui.root().child(page_view(&ui, &view, "Report.pdf"));
    view.find("quarterly");
    for _ in 0..1000 {
        app.frames(1);
        if view.search_status().get().done && view.is_sharp() {
            break;
        }
        std::thread::sleep(Duration::from_millis(5));
    }
    assert_eq!(view.search_status().get().matches, 1);
    assert!(view.is_sharp(), "the tiles never finished");
    assert_eq!(view.page_error(0), None);
}

#[test]
fn a_file_that_is_not_a_pdf_is_an_error() {
    assert!(matches!(
        PdfFile::from_bytes(b"not a pdf".to_vec(), None),
        Err(Error::Other(_))
    ));
}
