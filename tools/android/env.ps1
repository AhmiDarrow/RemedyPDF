# RemedyPDF Android env (dot-source before local experiments)
# Full APK builds: use GitHub Actions ubuntu job or WSL — not bare Windows.
$env:ANDROID_SDK_ROOT = if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { "C:\Users\Administrator\scoop\apps\android-clt\current" }
$env:ANDROID_HOME = $env:ANDROID_SDK_ROOT
$env:REMEDYPDF_MOBILE = "1"
Write-Host "ANDROID_SDK_ROOT=$($env:ANDROID_SDK_ROOT)"
Write-Host "Tip: real APK is built on CI (release.yml build-android job)."
