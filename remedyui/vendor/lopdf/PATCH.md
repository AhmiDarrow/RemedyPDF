lopdf 0.47.0 (MIT) with one patch, in `src/reader.rs` `parse_encryption_dictionary`:
an `/Encrypt` dictionary written directly in the trailer is accepted. Without it, password-protected
files saved by MuPDF (and so by RemedyPDF 1.x) are refused with `InvalidPassword`.
Remove this copy once a lopdf release has the fix. Examples, tests and benches are not copied.
