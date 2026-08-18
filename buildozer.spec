[app]
title = RemedyPDF
package.name = remedypdf
package.domain = com.ahmidarrow
source.dir = .
source.include_exts = py,png,jpg,jpeg,ico,json,txt,md,ttf,kv
source.include_patterns = src/*,resources/*,main_android.py,main.py
source.exclude_dirs = tests,build,dist,.git,.venv,venv,tools,.remedy-build,.buildozer,bin
version = 1.4.5
requirements = python3,kivy,pyjnius,android,pillow,pymupdf,certifi
orientation = all
fullscreen = 1
android.permissions = INTERNET
android.api = 34
android.minapi = 26
android.ndk = 25b
android.accept_sdk_license = True
android.archs = armeabi-v7a
android.release_artifact = apk
android.entrypoint = org.kivy.android.PythonActivity
p4a.branch = develop
icon.filename = resources/icon.png
presplash.filename = resources/logo.png

[buildozer]
log_level = 2
warn_on_root = 0
