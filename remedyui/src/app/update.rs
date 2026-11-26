//! Updates: a check shortly after start and every few hours (waiting
//! longer after failures), a verified download, and a silent install that reopens the app.
//! Installing needs no click unless the person turns that off. The app never
//! restarts over unsaved changes, and comes back to the document and page that were open.
//!
//! What is trusted: a download signed with RemedyPDF's update key. Nothing else is run.

use super::{Handle, NAME, VERSION};
#[cfg(not(target_os = "android"))]
use remedy_ui::update::Apply;
use remedy_ui::update::{self as up, BannerText, Feed, UpdateConfig, UpdateState};
use remedy_ui::{El, Ui};
use std::path::{Path, PathBuf};
use std::time::Duration;

/// The public half of the update key. Releases are signed with the private half.
const PUBLIC_KEY: &str = "RWQP16CopgDiweEH5NCelhNEwphYogZDHcb1rJX+ZbgGDfeO08S3KduI";
/// The newest release's list of downloads. RemedyPDF 1.x reads this file too.
const FEED: &str = "https://github.com/AhmiDarrow/RemedyPDF/releases/latest/download/latest.json";
pub const RELEASES: &str = "https://github.com/AhmiDarrow/RemedyPDF/releases";
const FIRST_CHECK: Duration = Duration::from_secs(20);
const EVERY: Duration = Duration::from_secs(4 * 3600);
/// Setup runs with no window, closes the app if it is still open, and reopens it.
#[cfg(windows)]
const INSTALLER_ARGS: [&str; 6] = [
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/CLOSEAPPLICATIONS",
    "/FORCECLOSEAPPLICATIONS",
    "/CURRENTUSER",
];

/// Another place to ask, for the release tests: https, or http on this machine. A download
/// from there must still be signed with the update key.
fn feed() -> String {
    // On Android, where an app has no environment of its own, a launch extra says the same
    // (`adb shell am start ... --es REMEDYPDF_UPDATE_FEED <url>`).
    #[cfg(target_os = "android")]
    let asked = remedy_ui::android::launch_extra("REMEDYPDF_UPDATE_FEED");
    #[cfg(not(target_os = "android"))]
    let asked = std::env::var("REMEDYPDF_UPDATE_FEED").ok();
    asked
        .filter(|f| !f.trim().is_empty())
        .unwrap_or_else(|| FEED.into())
}

/// `REMEDYPDF_NO_UPDATE=1` turns the automatic checks off.
fn checks_off() -> bool {
    std::env::var("REMEDYPDF_NO_UPDATE").is_ok_and(|v| {
        matches!(
            v.trim().to_lowercase().as_str(),
            "1" | "true" | "yes" | "on"
        )
    })
}

pub fn config() -> UpdateConfig {
    UpdateConfig::new(VERSION, Feed::Json(feed()), PUBLIC_KEY)
}

/// The wait before the next automatic check after `failures` failed ones in a row.
pub fn next_check(failures: u32) -> Duration {
    if failures == 0 {
        return EVERY;
    }
    Duration::from_secs(15 * 60)
        .saturating_mul(1u32 << (failures - 1).min(16))
        .min(EVERY)
}

// ---- Checking, downloading, installing ----

/// Starts the automatic checks. `now` (`--install-update`) also checks at once.
pub fn start(shell: &Handle, now: bool) {
    if now {
        check(shell, true);
    }
    schedule(shell, FIRST_CHECK);
}

fn schedule(shell: &Handle, after: Duration) {
    let weak = std::rc::Rc::downgrade(shell);
    shell.app.after(after, move || {
        let Some(shell) = weak.upgrade() else { return };
        if checks_off() {
            schedule(&shell, EVERY);
        } else {
            check(&shell, false);
        }
    });
}

fn busy(shell: &Handle) -> bool {
    matches!(
        shell.update.get_untracked(),
        Ok(UpdateState::Checking | UpdateState::Downloading(_) | UpdateState::Ready)
    )
}

/// The Help menu and About: the answer is always shown.
pub fn check_now(shell: &Handle) {
    check(shell, true);
}

fn check(shell: &Handle, by_hand: bool) {
    if busy(shell) {
        if !by_hand {
            schedule(shell, EVERY);
        }
        return;
    }
    // An automatic check says nothing until it finds something.
    if by_hand {
        shell.update.set(UpdateState::Checking);
    }
    let done = shell.clone();
    shell.app.background(
        || up::check(&config()),
        move |found| {
            let shell = done;
            let failures = match found {
                Ok(Some(release)) => {
                    *shell.release.borrow_mut() = Some(release.clone());
                    if shell.auto_update.get_untracked().unwrap_or(true) {
                        download(&shell);
                    } else {
                        shell.update.set(UpdateState::Available(release));
                    }
                    0
                }
                Ok(None) => {
                    shell.update.set(if by_hand {
                        UpdateState::UpToDate
                    } else {
                        UpdateState::Idle
                    });
                    if by_hand {
                        dismiss_later(&shell);
                    }
                    0
                }
                Err(e) => {
                    shell.update.set(if by_hand {
                        UpdateState::Failed(e.to_string())
                    } else {
                        UpdateState::Idle
                    });
                    shell.update_failures.get() + 1
                }
            };
            shell.update_failures.set(failures);
            if !by_hand {
                schedule(&shell, next_check(failures));
            }
        },
    );
}

fn dismiss_later(shell: &Handle) {
    let weak = std::rc::Rc::downgrade(shell);
    shell.ui.after(Duration::from_secs(6), move || {
        let Some(shell) = weak.upgrade() else { return };
        if matches!(shell.update.get_untracked(), Ok(UpdateState::UpToDate)) {
            shell.update.set(UpdateState::Idle);
        }
    });
}

/// Where a download goes.
#[cfg(not(target_os = "android"))]
fn download_folder() -> Option<PathBuf> {
    Some(std::env::temp_dir().join(format!("{NAME}-update")))
}

/// The app's cache: Android has no shared temporary folder an app may write.
#[cfg(target_os = "android")]
fn cache_folder() -> Option<PathBuf> {
    Some(remedy_ui::android::data_dir()?.parent()?.join("cache"))
}

#[cfg(target_os = "android")]
fn download_folder() -> Option<PathBuf> {
    Some(cache_folder()?.join(format!("{NAME}-update")))
}

/// Hands a verified APK to Android's installer, which asks the person to confirm. The APK
/// goes where RemedyUI's file provider serves it from.
#[cfg(target_os = "android")]
fn offer_apk(file: &Path) -> Result<remedy_ui::android::ApkInstall, String> {
    // A request number of the updater's own, apart from the ones sharing counts up from.
    const REQUEST: &str = "1000001";
    let name = "RemedyPDF.apk";
    let folder = cache_folder()
        .ok_or("there is no cache folder")?
        .join("remedy-share")
        .join(REQUEST)
        .join("0");
    std::fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    std::fs::copy(file, folder.join(name)).map_err(|e| e.to_string())?;
    remedy_ui::android::install_apk(REQUEST, 0, "application/vnd.android.package-archive", name)
}

/// Downloads and verifies the release found, then installs it as soon as nothing is unsaved.
pub fn download(shell: &Handle) {
    let Some(release) = shell.release.borrow().clone() else {
        return;
    };
    shell.update.set(UpdateState::Downloading(None));
    let state = shell.update;
    let waker = remedy_ui::reactive::waker().ok();
    let Some(folder) = download_folder() else {
        return fail(shell, "there is nowhere to download to");
    };
    let done = shell.clone();
    shell.app.background(
        move || {
            up::download(&config(), &release, &folder, |got, total| {
                if let (Some(waker), Some(total)) = (&waker, total.filter(|t| *t > 0)) {
                    let fraction = (got as f64 / total as f64) as f32;
                    let _ = waker.post(move || {
                        // Only while still downloading: a late report must not undo the end.
                        if matches!(state.get_untracked(), Ok(UpdateState::Downloading(_))) {
                            let _ = state.try_set(UpdateState::Downloading(Some(fraction)));
                        }
                    });
                }
            })
        },
        move |file| match file {
            Ok(file) => {
                *done.downloaded.borrow_mut() = Some(file);
                done.update.set(UpdateState::Ready);
                install_when_safe(&done);
            }
            Err(e) => fail(&done, &e.to_string()),
        },
    );
}

/// Installs a downloaded update unless that would lose or interrupt unsaved work. The app
/// calls this again when changes are saved or closed.
pub fn install_when_safe(shell: &Handle) {
    if !matches!(shell.update.get_untracked(), Ok(UpdateState::Ready))
        || shell.has_changes()
        || shell.busy.get_untracked().unwrap_or(false)
    {
        return;
    }
    let (Some(file), Some(release)) = (
        shell.downloaded.borrow_mut().take(),
        shell.release.borrow().clone(),
    ) else {
        return;
    };
    super::recovery::note(shell, Some(&release.version));
    install(shell, &file, &release);
}

#[cfg(not(target_os = "android"))]
fn install(shell: &Handle, file: &Path, _release: &up::Release) {
    #[cfg(windows)]
    let how = Apply::RunInstaller(INSTALLER_ARGS.iter().map(|a| (*a).to_owned()).collect());
    // Elsewhere the new program takes this one's place and starts as this one exits.
    #[cfg(not(windows))]
    let how = Apply::ReplaceExecutable;
    match up::apply(file, &how) {
        Ok(()) => shell.app.quit(),
        Err(e) => fail(shell, &e.to_string()),
    }
}

/// Android installs nothing without the person's yes, and ends the app itself once they give it.
#[cfg(target_os = "android")]
fn install(shell: &Handle, file: &Path, release: &up::Release) {
    match offer_apk(file) {
        // Android ends the app if the install goes ahead. If it is refused instead, nothing
        // tells the app, so the offer stays up.
        Ok(remedy_ui::android::ApkInstall::Started) => {
            shell.update.set(UpdateState::Available(release.clone()))
        }
        Ok(remedy_ui::android::ApkInstall::NeedPermission) => {
            shell.update.set(UpdateState::Available(release.clone()));
            shell.say("Allow installs from RemedyPDF, then press Install");
        }
        Err(e) => fail(shell, &e),
    }
}

/// Says what went wrong, and opens the download page so the update can be done by hand.
fn fail(shell: &Handle, detail: &str) {
    shell.update.set(UpdateState::Failed(format!(
        "The update could not finish ({detail}). The download page is opening so you can install it yourself."
    )));
    shell.app.open_url(RELEASES, |_| {});
}

/// The strip under the toolbar: what an update is doing.
pub fn banner(shell: &Handle, ui: &Ui) -> El {
    let mut words = BannerText::default();
    // Installing starts at once unless there are unsaved changes.
    words.ready = "Update downloaded. It installs when your changes are saved or closed.".into();
    words.restart = None;
    let weak = std::rc::Rc::downgrade(shell);
    up::update_banner_with(
        ui,
        shell.update,
        &words,
        move || {
            if let Some(shell) = weak.upgrade() {
                download(&shell);
            }
        },
        || {},
    )
}

/// One line for the About box.
pub fn describe(state: &UpdateState) -> String {
    match state {
        UpdateState::Checking => "Checking for updates…".into(),
        UpdateState::UpToDate => "You're up to date.".into(),
        UpdateState::Available(release) => format!("Version {} is available.", release.version),
        UpdateState::Downloading(Some(f)) => format!("Downloading update… {:.0}%", f * 100.0),
        UpdateState::Downloading(None) => "Downloading update…".into(),
        UpdateState::Ready => "Update downloaded.".into(),
        UpdateState::Failed(why) => why.clone(),
        _ => String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn failed_checks_back_off() {
        assert_eq!(next_check(0), Duration::from_secs(4 * 3600));
        assert_eq!(next_check(1), Duration::from_secs(15 * 60));
        assert_eq!(next_check(2), Duration::from_secs(30 * 60));
        assert_eq!(next_check(5), Duration::from_secs(4 * 3600));
        assert_eq!(next_check(40), Duration::from_secs(4 * 3600));
    }

    #[test]
    fn only_downloads_signed_with_the_update_key_are_trusted() {
        let mut release = up::Release::new("9.9.9", "https://example.com/RemedyPDF-setup.exe");
        release.signature = "not a signature".into();
        assert!(up::verify(&config(), &release, b"installer").is_err());
        assert!(matches!(config().trust, up::Trust::Minisign(ref key) if key == PUBLIC_KEY));
    }
}
