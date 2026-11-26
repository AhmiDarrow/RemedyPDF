# Changelog

All notable changes to RemedyPDF are documented in this file.

## [2.0.0] - 2026-11-26

RemedyPDF is now a native app for Windows, Linux and Android.

- Rebuilt in Rust on RemedyUI, with PDFium for PDFs. No Python, and every part has a permissive licence.
- Linux is new. Android is now a real app (APK) instead of a source download.
- Updates install automatically by default, and only when signed with RemedyPDF's update key. The app never restarts over unsaved changes, and reopens your document.
- RemedyPDF 1.x on Windows updates to 2.0 from inside the app, into the same folder.

Known issue (Android): text that arrives in a very fast burst can lose letters.
