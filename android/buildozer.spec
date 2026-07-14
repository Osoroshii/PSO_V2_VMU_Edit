[app]
title = PSO VMU Editor
package.name = psovmuedit
package.domain = org.psovmuedit

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
# psovmu/ is a symlink to ../psovmu (the shared core logic with the desktop
# app) -- buildozer/python-for-android follows symlinks when copying source,
# so nothing extra is needed here to bundle it.
# venv/ (this repo's own dev virtualenv) must NOT be swept into the packaged
# app -- confirmed the hard way: without this exclusion, buildozer tries to
# copy venv/bin/python3, which is a symlink to the host's Homebrew Python
# binary, and crashes with FileNotFoundError once it's off the mounted volume
# (it's also just the wrong OS/arch entirely -- p4a builds its own Python).
source.exclude_dirs = venv,.buildozer,.buildozer-global,bin,__pycache__

icon.filename = %(source.dir)s/icon.png

version = 0.3.1

# plyer's Android filechooser backend needs pyjnius (pulled in automatically);
# do NOT add pyobjus here -- that's the macOS-only desktop-dev equivalent.
requirements = python3,kivy==2.3.1,plyer==2.1.0,pyjnius

# Retroid Pocket 5 (and gaming handhelds generally) are landscape-first
# hardware -- confirmed on a real device that the previous `portrait` setting
# caused Kivy/SDL2's window to be laid out with swapped width/height
# (content clipped at the right edge, e.g. "Choose VMU Fold|" and
# "Save + Resca|"), consistent with SDL2 sizing its surface for the panel's
# native landscape dimensions while the manifest fought it into portrait.
orientation = landscape
fullscreen = 0

# Android 13+ (API 33) replaced broad storage permissions with the
# per-file/tree Storage Access Framework picker plyer's filechooser already
# uses (ACTION_OPEN_DOCUMENT_TREE) -- no READ/WRITE_EXTERNAL_STORAGE needed.
android.permissions =
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
