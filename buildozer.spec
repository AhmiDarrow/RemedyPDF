[app]
title = RemedyPDF
package.name = remedypdf
package.domain = com.ahmidarrow
source.dir = .
source.include_exts = py,png,jpg,jpeg,ico,json,txt,md,ttf,kv
source.include_patterns = src/*,resources/*,main_android.py,main.py
source.exclude_dirs = tests,build,dist,.git,.venv,venv,tools,.remedy-build,.buildozer,bin
version = 1.4.2
requirements = python3,pyjnius,android,pillow,pymupdf
orientation = all
fullscreen = 1
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = armeabi-v7a
android.release_artifact = apk
android.entrypoint = org.kivy.android.PythonActivity
p4a.branch = master
icon.filename = resources/icon.png
presplash.filename = resources/logo.png

[buildozer]
log_level = 2
warn_on_root = 0
