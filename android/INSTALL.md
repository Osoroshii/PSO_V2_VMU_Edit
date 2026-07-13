# Installing PSO VMU Editor on an Android device

This walks through getting the app from source onto a real phone/tablet. If
you just want to run it on your computer while developing, see
[README.md](README.md) instead -- that's faster and doesn't need a device.

**Heads up**: this app hasn't been installed on a real Android device yet --
everything up through the character/item editors has been tested on desktop
only. The build and install steps below are correct, but the app's actual
on-device behavior (especially the folder picker, which uses a different
native API on Android than on desktop) is unverified until someone runs
through this for the first time. If something behaves unexpectedly, that's
useful to know -- see [README.md](README.md)'s "Notes for whoever picks this
up next" for the most likely trouble spots.

## 1. Build the APK

You need [Docker](https://www.docker.com/) installed (Buildozer's Android
build is unreliable natively on macOS -- Docker sidesteps that entirely,
regardless of what OS you're building on). From this `android/` directory:

```
docker run --rm -v "$PWD":/home/user/hostcwd kivy/buildozer android debug
```

The first run downloads the Android SDK/NDK (several GB) and can take 20+
minutes. When it finishes, you'll have an APK at `bin/psovmuedit-0.1.0-arm64-v8a_armeabi-v7a-debug.apk`
(the exact filename includes the version and architectures from
`buildozer.spec`).

## 2. Get the APK onto your device

Pick whichever is easiest for you:

**Option A -- USB + adb** (needs [platform-tools](https://developer.android.com/tools/releases/platform-tools) / `adb` installed on your computer):
1. Enable Developer Options on the device: Settings -> About Phone -> tap
   "Build number" 7 times.
2. In Developer Options, turn on USB Debugging.
3. Plug the device in via USB, allow the "Allow USB debugging?" prompt on
   the phone.
4. From `android/`: `adb install bin/psovmuedit-*-debug.apk`

**Option B -- copy the file over**
1. Upload the APK somewhere you can reach from the phone (Google Drive,
   email it to yourself, AirDrop-equivalent, etc.) or copy it directly via a
   USB file transfer.
2. Open it on the device with a file manager app.

## 3. Allow installing this APK

Android blocks installing anything that didn't come from the Play Store by
default. When you tap the APK file (or run `adb install`), if you see a
prompt like "For your security, your phone is not allowed to install unknown
apps from this source":
1. Tap **Settings** on that prompt (or go to Settings -> Apps -> the app you
   used to open the file, e.g. Files or your browser -> **Install unknown
   apps** -> toggle it on for that app).
2. Go back and open the APK again.

## 4. Install and open

Tap through the install prompt, then open **PSO VMU Editor** from your app
drawer -- it should show the VMU-shaped icon.

## 5. First-run setup

1. Tap **Choose VMU Folder**. Android will show its own folder picker (not
   the app's own UI) -- navigate to wherever your emulator stores its VMU
   `.bin` files and select that folder, then confirm access when prompted.
   - If your emulator keeps its saves in a location Android's picker can't
     reach (some emulators use private app storage that isn't visible to
     other apps), copy the `.bin` files to a shared folder first -- e.g. your
     Downloads folder -- and point the picker there instead.
2. Enter your disc/account serial number (the same one the desktop app asks
   for) and tap **Save + Rescan**.
3. Real characters in that folder should appear by name/class/level. Tap one
   to edit it.

Both the folder and serial are remembered, so this is only needed once.

## Updating to a new version

Rebuild the APK (step 1) and reinstall the same way -- `adb install -r
bin/...-debug.apk` (the `-r` reinstalls over the existing app) or just open
the new APK file again if you're installing manually.
