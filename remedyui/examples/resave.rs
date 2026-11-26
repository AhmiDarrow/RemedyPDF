//! Unlock and re-protect a PDF in place: `resave <file> <password>`. Used by tests/encryption.py.
use remedypdf::secure::{protect, unlock, write_atomic};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let [_, path, password] = &args[..] else {
        return Err("usage: resave <file> <password>".into());
    };
    let open = unlock(&std::fs::read(path)?, password)?;
    write_atomic(
        path.as_ref(),
        &protect(&open.bytes, password, open.permissions)?,
    )
}
