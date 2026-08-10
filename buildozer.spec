[app]
title = RemedyPDF
package.name = remedypdf
package.domain = com.ahmidarrow
source.dir = .
source.include_exts = py,png,jpg,jpeg,ico,json,txt,md,ttf,kv
source.include_patterns = src/*,resources/*
source.exclude_dirs = tests,build,dist,.git,.venv,venv,tools,.remedy-build
version = 1.4.0
requirements = python3,pyjnius,android,pillow,pymupdf
# sensor = auto-rotate: PDFs read much better in landscape on phones
orientation = sensor
# immersive: hide the Android status bar for distraction-free reading
fullscreen = 1
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a
android.release_artifact = apk
icon.filename = C:/Users/Administrator/RemedyPDF/resources/icon.png
presplash.filename = C:/Users/Administrator/RemedyPDF/resources/logo.png
# Entry: thin launcher that forces mobile mode then starts the app
android.entrypoint = org.kivy.android.PythonActivity
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 0
