# PSO VMU Editor -- Android

A touch UI for the same `psovmu` core logic the desktop app (`../main.py`) uses,
built with [Kivy](https://kivy.org) so it can be packaged as a real Android APK.
`psovmu/` in this directory is a symlink to `../psovmu` -- there's only one copy
of the crypto/character/item logic, shared by both UIs.

**Status**: feature-complete parity with the desktop app, and installed and
running on a real device (Retroid Pocket 5). Folder picker with persisted
folder+serial and a name/class/level preview; a character editor (level/EXP/
meseta/stats/quest-flags); and Bank/Inventory item editing for all 10
categories (Guns/Swords/Wands incl. S-rank, Armor, Shields, Units, Mags,
Technique Disks, Parts, Tools), including the same equip-check warning and
existing-item pre-fill the desktop app has. `orientation = landscape` in
`buildozer.spec` (gaming handhelds are landscape-first hardware) and every
widget uses proportional `size_hint` rather than fixed pixel widths --
confirmed on-device that Kivy's Android density detection can silently fall
back to a bogus value (`density=0.0` instead of the real `2.25` on the
Retroid Pocket 5), which broke absolute-pixel layouts (buttons/labels clipped
off the right edge of the screen) but doesn't affect proportional ones.
Confirmed end-to-end on-device: picking a folder on the SD card via the SAF
picker, editing a character, saving, and verifying the result in-game.

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

## Running tests

`tests/` has a pytest suite covering both the non-Kivy glue code
(`session.py`, `vmu_scan.py`, `storage.py`, `fileio.py`'s desktop branch) and
the real screens (`main.py`'s `PickerScreen`/`EditorScreen`, `item_screens.py`'s
`ItemListScreen`/`ItemPickerScreen`) -- constructed and driven for real
(`conftest.py`'s `app_screen_manager` fixture wires them into a `ScreenManager`
exactly like `PSOVMUApp.build()` does), not mocked. Run the same way as the
repo root's `tests/` suite:

```
cd android
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Constructing any real Kivy widget lazily creates an actual SDL2 window/GL
context on first use, so this needs a real (or virtual, e.g. `xvfb-run` on
headless Linux) display -- see the `android-test` CI job in
`.github/workflows/ci.yml` for the Ubuntu-specific Xvfb setup. Where no
display is available at all (confirmed on GitHub's macOS-hosted runners --
they have no logged-in GUI session, and Kivy's SDL2 backend has no headless
fallback), `conftest.py` detects this up front (in an isolated subprocess --
see `_detect_kivy_window_support`'s docstring for why in-process detection
isn't safe) and the widget-dependent tests skip cleanly instead of erroring.

Only `fileio.py`'s Android/SAF branch is untested -- it needs `pyjnius` and a
real `Activity`, which only exist inside a packaged APK on an actual device,
not in a desktop test run.

## Building an actual APK

See [INSTALL.md](INSTALL.md) for the full build-and-install walkthrough for a
real device. Short version below.

Uses [Buildozer](https://buildozer.readthedocs.io) (`buildozer.spec` is already
set up in this directory). **Buildozer's Android target is unreliable on
macOS** -- the officially recommended, actually-reproducible way to build is
their Docker image, regardless of host OS. On Apple Silicon specifically, the
naive `docker run --rm -v "$PWD":/home/user/hostcwd kivy/buildozer android
debug` command from Buildozer's own docs does **not** work as-is -- see
[INSTALL.md](INSTALL.md)'s "Build gotchas" section for the working command
and why each extra flag/mount is there (confirmed by actually producing a
working APK, not just in theory). The resulting APK lands in `bin/`.

## Notes for whoever picks this up next

- **Never use fixed pixel `width=`/`height=` for a widget meant to share a row
  with a flexible sibling -- use proportional `size_hint` instead.** Confirmed
  the hard way on a real Retroid Pocket 5: Kivy's Android density detection
  reported `density=0.0` and `dpi=96.0` (both clearly wrong fallback values --
  the device's real density is 2.25 / 360dpi per `adb shell wm density`)
  instead of raising an error, and every fixed-pixel width in the app ended up
  visually clipped off the right edge of the screen as a result, even though
  `Window.size` itself was reported correctly. Proportional `size_hint`
  self-corrects regardless of whatever Kivy's density detection does on a
  given device, so it's the safer default for this app generally, not just a
  one-off fix. If new screens get added, follow `item_screens.py`'s `_row()`/
  `_label(text, width_hint=...)` pattern rather than reintroducing `width=N`.
- `item_screens.py` (`ItemListScreen` + `ItemPickerScreen`) is the Bank/
  Inventory equivalent of the desktop app's `_build_item_tab`/`AddItemDialog`
  in `../main.py` -- same category dispatch, same field layouts per category,
  same equip-check-then-confirm-anyway flow. `ItemPickerScreen._rebuild_body`
  resets the equip-check label before dispatching to the category builder --
  only weapon/armor/shield/unit builders set it themselves, so without the
  reset, switching from e.g. Guns to Mags left the old "Usable by: ..." text
  on screen for a category that has no equip check at all. Caught by an actual
  screenshot, not the headless widget-dispatch tests (which only asserted on
  data, not on what was left visually on screen) -- worth taking at least one
  real screenshot per new screen for exactly this reason.
- Comparing a Kivy widget's `.color` property against a plain tuple with `==`
  is unreliable (Kivy stores it as a list internally, and `[1,2] == (1,2)` is
  `False` in Python) -- `ItemPickerScreen` tracks equippability with an
  explicit `self._equip_ok` boolean instead of re-deriving it from the label's
  color, after that comparison silently always returned "not equippable"
  during testing.
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
