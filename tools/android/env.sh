#!/usr/bin/env bash
# RemedyPDF Android env — source from bash/WSL/Linux CI
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-C:\Users\Administrator\scoop\apps\android-clt\current}"
export ANDROID_HOME="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"
export REMEDYPDF_MOBILE=1
echo "ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT"
