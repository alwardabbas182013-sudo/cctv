[app]
title = ChatterBox
package.name = chatterbox
package.domain = org.codexdude

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 0.1
requirements = python3,kivy,paho-mqtt

orientation = portrait
fullscreen = 0

# Android specifics
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
