# Installing PSO VMU Editor on an Android device

This walks through getting the app from source onto a real phone/tablet. If
you just want to run it on your computer while developing, see
[README.md](README.md) instead -- that's faster and doesn't need a device.

**Status**: confirmed installed and running on a real device (Retroid Pocket
5) -- the app launches, Python/Kivy/SDL2 initialize cleanly (no crash), and
the picker screen renders correctly (after fixing a real on-device layout bug
-- see README.md's "Notes for whoever picks this up next"). **Not yet
exercised end-to-end** with a real VMU folder/serial on-device -- the folder
picker opens Android's native Storage Access Framework UI, which needs a
human physically tapping through it (can't be driven via `adb`). If that or
anything past it behaves unexpectedly, see README.md for the most likely
trouble spots.

## 1. Build the APK

You need [Docker](https://www.docker.com/) installed (Buildozer's Android
build is unreliable natively on macOS -- Docker sidesteps that entirely,
regardless of what OS you're building on). From this `android/` directory,
**on Apple Silicon** (see "Build gotchas" for why the extra flags/mounts are
needed -- omitting them will fail partway through):

```
docker volume create buildozer-android-global     # one-time; persists the SDK/NDK across builds
docker volume create buildozer-android-keystore   # one-time; persists the debug signing key across builds

docker run --platform linux/amd64 --rm \
  -v "$PWD":/home/user/hostcwd \
  -v "$(cd .. && pwd)/psovmu":/home/user/psovmu \
  -v buildozer-android-global:/home/user/.buildozer \
  -v buildozer-android-keystore:/home/user/.android \
  kivy/buildozer android debug
```

On Intel Macs or Linux, `--platform linux/amd64` isn't needed but is
harmless to leave in. The first run downloads the Android SDK/NDK/Gradle
(several GB total) and compiles Python/OpenSSL/etc. from source for both
target architectures -- 20-30+ minutes. Thanks to the two named/bind cache
mounts above, later rebuilds after a code change only redo the fast "copy
app source + package APK" steps (a couple minutes). When it finishes, you'll
have an APK at `bin/psovmuedit-0.1.0-arm64-v8a_armeabi-v7a-debug.apk` (the
exact filename includes the version and architectures from
`buildozer.spec`).

### Build gotchas (why the command looks like that)

Hit all of these getting the first successful build, in order -- if a build
fails, check which of these it's hitting before assuming something new is
wrong:

1. **The container runs as root** and buildozer refuses to proceed without
   an interactive `y/n` confirmation. Piping `yes` into `docker run -i`
   answers it (and every Android SDK license prompt that follows).
2. **`psovmu/` is a symlink** (`android/psovmu -> ../psovmu`, shared with the
   desktop app) pointing *outside* whatever's mounted at `/home/user/hostcwd`
   if you only mount `android/`. Fix: mount the real `psovmu/` directory
   separately at `/home/user/psovmu` (matching where the relative symlink
   resolves to) -- as in the command above. Do **not** "fix" this by mounting
   the whole repo root instead; that drags in `.git`, which hits gotcha #4.
3. **Apple Silicon**: Android SDK build-tools binaries (`aidl`, `aapt2`, ...)
   are x86_64-only. A native arm64 container can't execute them at all.
   `--platform linux/amd64` forces an x86_64 container, which Docker Desktop
   transparently runs via Rosetta.
4. **`chown` fails on read-only files passed through a host bind mount** --
   a Docker Desktop / macOS virtiofs limitation, not a bug in this project.
   The container's entrypoint does `chown -R` over `/home/user/hostcwd` and
   `/home/user/.buildozer` on startup and aborts on the first failure; git
   objects (mode 444) and the SDK's own unpacked `.jar` files both trigger
   it. Fix: keep the SDK/NDK/Gradle cache in a **Docker named volume**
   (`buildozer-android-global` above), not a host directory -- named volumes
   live natively inside the Docker VM and aren't subject to this passthrough
   restriction. Don't put `.git` under the mounted `hostcwd` tree either
   (see gotcha #2).
5. **Buildozer's own state cache (`.buildozer/state.db`, a few hundred
   bytes -- not the multi-GB build artifacts) can go stale** if you ever
   swap out the global SDK/NDK cache without also resetting it: it
   remembers "verified the Android SDK/build-tools/platform are installed"
   from whatever global cache existed at the time, and later skips
   re-verifying against a *different* global cache, so `pythonforandroid`
   fails with `Available Android APIs are ()` even though nothing about your
   *code* is wrong. Fix: `rm .buildozer/state.db` (safe -- buildozer just
   redoes its lightweight checks, it doesn't touch the actual compiled
   libraries elsewhere under `.buildozer/`) and rebuild. Using the named
   volume from the start avoids ever hitting this.
6. **`android/venv/` (this repo's own dev virtualenv) must be excluded** from
   the packaged app -- `buildozer.spec`'s `source.exclude_dirs` already
   covers this, but if that ever regresses: without it, buildozer tries to
   copy `venv/bin/python3`, which is a symlink to the *host's* Homebrew
   Python binary, and crashes with `FileNotFoundError` once it's off the
   mounted volume (it's also the wrong OS/arch entirely -- p4a builds and
   bundles its own Python for the target device).
7. **A fresh debug signing key every build**, unless `/home/user/.android` is
   also persisted (the `buildozer-android-keystore` volume above). The
   generated Gradle build (`dists/psovmuedit/templates/build.tmpl.gradle`)
   only sets an explicit `signingConfig` for *release* builds -- debug builds
   fall through to the Android Gradle Plugin's own default, which
   auto-generates `~/.android/debug.keystore` the first time it's needed if
   one doesn't already exist. Since the container is `--rm` and (without this
   volume) nothing under `/home/user/.android` survives past that one run,
   every subsequent build minted a brand new keystore, so every install
   looked like a different, incompatible app to Android's package manager.
   Persisting `/home/user/.android` the same way `/home/user/.buildozer` is
   already persisted fixes it permanently -- see "Updating to a new version"
   below for what to do about an app already installed from before this fix.

## 2. Get the APK onto your device

Pick whichever is easiest for you:

**Option A -- USB + adb** (needs [platform-tools](https://developer.android.com/tools/releases/platform-tools) / `adb` installed on your computer -- `brew install android-platform-tools` on a Mac):
1. Enable Developer Options on the device: Settings -> About Phone (or
   About Device) -> tap "Build number" 7 times.
2. **Separately**, inside Developer Options, turn on **USB Debugging** --
   unlocking Developer Options does *not* also enable this; it's its own
   toggle one screen deeper. If the device shows up in Android File
   Transfer/Finder but `adb devices` lists nothing, this is almost always why.
3. Plug the device in via USB. Run `adb devices -l` -- if it lists nothing or
   `unauthorized`, check the device screen for an "Allow USB debugging?"
   popup and tap **Allow**.
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

Rebuild the APK (step 1) and reinstall with `adb install -r
bin/...-debug.apk` -- this should just work now that the debug signing key
persists across builds (the `buildozer-android-keystore` volume in step 1).

If you built an APK from *before* that volume was added, one uninstall is
still needed to move over: that older APK was signed with a keystore that
no longer exists (it lived only inside a since-removed container), so
Android sees the new one as a different, incompatible app.
`adb uninstall org.psovmuedit.psovmuedit && adb install bin/...-debug.apk`
(or, installing manually, long-press the app icon -> Uninstall, then install
the new APK). Every build after that reuses the same persisted keystore, so
you shouldn't need to do this again.

## Useful `adb` commands while testing on-device

```
adb devices -l                                            # confirm the device is connected+authorized
adb install -r bin/psovmuedit-*-debug.apk                 # install/update (see gotcha above)
adb shell am start -n org.psovmuedit.psovmuedit/org.kivy.android.PythonActivity   # launch without touching the screen
adb logcat -c && adb logcat -d | grep -i python           # clear, then read the app's own stdout/stderr (Kivy logs, tracebacks)
adb exec-out screencap -p > screenshot.png                # grab a screenshot of whatever's currently on screen
adb shell wm size; adb shell wm density                   # the device's real resolution/density, if a layout looks wrong
```
