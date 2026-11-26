//! Reading files out of zip packages (EPUB, DOCX, XPS), with a limit against bombs.

use crate::pdf::Error;
use std::io::{Cursor, Read};

/// A package that unpacks to more than this is refused.
const MAX_UNPACKED: u64 = 4 << 30;

pub struct Package {
    zip: zip::ZipArchive<Cursor<Vec<u8>>>,
    unpacked: u64,
}

impl Package {
    pub fn new(bytes: Vec<u8>) -> Result<Package, Error> {
        let zip =
            zip::ZipArchive::new(Cursor::new(bytes)).map_err(|e| Error::Other(e.to_string()))?;
        Ok(Package { zip, unpacked: 0 })
    }

    pub fn read(&mut self, name: &str) -> Option<Vec<u8>> {
        let left = MAX_UNPACKED.saturating_sub(self.unpacked);
        let entry = self.zip.by_name(name).ok()?;
        let mut data = Vec::new();
        entry.take(left + 1).read_to_end(&mut data).ok()?;
        self.unpacked += data.len() as u64;
        (self.unpacked <= MAX_UNPACKED).then_some(data)
    }

    /// Set once the package has gone over the limit.
    pub fn failure(&self) -> Option<Error> {
        (self.unpacked > MAX_UNPACKED)
            .then(|| Error::Other("the file unpacks to more than 4 GB".into()))
    }
}
