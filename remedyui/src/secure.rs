//! Password-protected PDFs. lopdf unlocks in memory, the editor (PDFium) only ever sees an
//! unlocked document, and lopdf locks it again before anything reaches disk. This is needed
//! because PDFium cannot write AES-256 encryption.

use lopdf::encryption::crypt_filters::{Aes256CryptFilter, CryptFilter};
use lopdf::{
    Document, EncryptionState, EncryptionVersion, LoadOptions, Object, Permissions, StringFormat,
};
use std::collections::BTreeMap;
use std::io::Write;
use std::path::Path;
use std::sync::Arc;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

/// A protected file, unlocked. `bytes` is plaintext: keep it in memory, never write it.
pub struct Unlocked {
    pub bytes: Vec<u8>,
    pub permissions: Permissions,
}

pub fn unlock(file: &[u8], password: &str) -> Result<Unlocked> {
    let mut doc = Document::load_mem_with_options(file, LoadOptions::with_password(password))?;
    let permissions = doc
        .encryption_state
        .take()
        .ok_or("the file is not encrypted")?
        .permissions();
    let mut bytes = Vec::new();
    doc.save_to(&mut bytes)?;
    Ok(Unlocked { bytes, permissions })
}

/// Encrypts with AES-256. Like the Python app, user and owner password are both `password`.
pub fn protect(plain: &[u8], password: &str, permissions: Permissions) -> Result<Vec<u8>> {
    let mut doc = Document::load_mem(plain)?;
    if doc.is_encrypted() || doc.was_encrypted() {
        return Err("expected an unlocked document".into());
    }
    // Encrypted files need a file identifier; documents made from scratch may have none.
    if doc.trailer.get(b"ID").is_err() {
        let mut id = [0u8; 16];
        getrandom::fill(&mut id).map_err(|e| e.to_string())?;
        let id = Object::String(id.to_vec(), StringFormat::Hexadecimal);
        doc.trailer.set(b"ID", Object::Array(vec![id.clone(), id]));
    }
    let mut key = [0u8; 32];
    getrandom::fill(&mut key).map_err(|e| e.to_string())?;
    let filter: Arc<dyn CryptFilter> = Arc::new(Aes256CryptFilter);
    let state = EncryptionState::try_from(EncryptionVersion::V5 {
        encrypt_metadata: true,
        crypt_filters: BTreeMap::from([(b"StdCF".to_vec(), filter)]),
        file_encryption_key: &key,
        stream_filter: b"StdCF".to_vec(),
        string_filter: b"StdCF".to_vec(),
        owner_password: password,
        user_password: password,
        permissions,
    })?;
    doc.version = "2.0".into();
    doc.encrypt(&state)?;
    let mut out = Vec::new();
    doc.save_to(&mut out)?;
    Ok(out)
}

/// Replaces `path` in one step; on failure the old file is left as it was.
#[cfg(not(target_os = "android"))]
pub fn write_atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    let dir = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let mut tmp = tempfile::NamedTempFile::new_in(dir)?;
    tmp.write_all(bytes)?;
    tmp.as_file().sync_all()?;
    tmp.persist(path)?;
    Ok(())
}

/// On Android the file picked in a Save dialog is the app's own file, which the system copies
/// into the person's document each time it is closed after writing. It is written in place:
/// a rename over it would not be noticed. The edits stay in memory if this fails.
#[cfg(target_os = "android")]
pub fn write_atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut file = std::fs::File::create(path)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    Ok(())
}
