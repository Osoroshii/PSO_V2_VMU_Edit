# PSO VMU Editor -- Android

A touch UI for the same `psovmu` core logic the desktop app (`../main.py`) uses,
built with [Kivy](https://kivy.org) so it can be packaged as a real Android APK.
`psovmu/` in this directory is a symlink to `../psovmu` -- there's only one copy
of the crypto/character/item logic, shared by both UIs.

**Status**: folder picker + character editor. Remembers a VMU folder + serial
number, scans that folder for every `.bin` file with a real PSO character in
it, and shows "CharacterName (Class, LvNN)" instead of raw filenames. Tapping
one opens an editor for level/EXP/meseta/stats/quest-flags (mirroring the
desktop app's Character tab) with a working Save that round-trip-verifies and
backs up before writing, same as the desktop app. **Not ported yet: Bank/
Inventory item editing** -- that's the next milestone.

## Running on desktop (do this first)

Kivy apps are meant to be built and iterated on as a normal desktop app before
ever touching a device or emulator -- the exact same `main.py` runs on both.

```
cd android
python3.13 -m venv venv        # any Python 3.9+ works; use Homebrew's on macOS
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On first run, click **Choose VMU Folder** and pick the directory your emulator
keeps its VMU `.bin` files in (RetroArch/Flycast/etc. usually put them all in
one folder), then enter your disc/account serial number and click
**Save + Rescan**. Both are remembered for next time.

## Building an actual APK

Uses [Buildozer](https://buildozer.readthedocs.io) (`buildozer.spec` is already
set up in this directory). **Buildozer's Android target is unreliable on
macOS** -- the officially recommended, actually-reproducible way to build is
their Docker image, regardless of host OS:

```
docker run --rm -v "$PWD":/home/user/hostcwd kivy/buildozer android debug
```

The first build downloads the Android SDK/NDK (several GB) and will take a
while. The resulting APK lands in `bin/`. Without Docker, `pip install
buildozer` and `buildozer android debug` natively is possible on Linux and
*might* work on macOS with the Homebrew deps Buildozer's docs list
(`autoconf`, `automake`, `libtool`, `pkg-config`, `ccache`), but expect to hit
version-pinning issues Docker sidesteps entirely.

## Notes for whoever picks this up next

- `session.py`'s `CharacterSession` is the one place that loads/decrypts and
  re-encrypts/verifies/saves a character file -- ported directly from the
  desktop app's `App._load_path`/`_save` in `../main.py`. Both the folder
  scan's name/level preview (`vmu_scan.py`) and the real editor screen
  (`main.py`'s `EditorScreen`) load through it, so there's exactly one
  implementation of that flow to keep in sync with the desktop app if the
  underlying `psovmu` core ever changes.
- `storage.py` persists settings via Kivy's `App.user_data_dir`, which
  resolves correctly on every platform Kivy supports with no platform
  branching needed in this app's own code.
- `vmu_scan.py`'s folder scan wraps every VMU-parsing step in a broad
  `except Exception` -- unlike the desktop app (which only ever loads one
  user-picked, already-known-good file at a time), scanning an entire real
  folder means hitting blank/uninitialized VMUs and non-VMU `.bin` files
  (emulator BIOS/NVMEM dumps, etc.) that `psovmu/vmu.py` was never written to
  guard against. Confirmed by testing against a real emulator folder, not
  just synthetic data -- see `docs/REFERENCE.md` in the repo root if a similar
  "works on paper, breaks on real files" gap needs debugging again.
- The folder picker (`plyer.filechooser.choose_dir`) needs `pyobjus` installed
  on macOS specifically for its native NSOpenPanel backend -- it fails
  silently into a "Folder picker failed" popup without it. On a packaged
  Android build, plyer uses `pyjnius` + Android's Storage Access Framework
  instead (`requirements` in `buildozer.spec` already reflects this split);
  that path is untested until a real APK build happens.
