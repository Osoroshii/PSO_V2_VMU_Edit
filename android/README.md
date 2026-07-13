# PSO VMU Editor -- Android

A touch UI for the same `psovmu` core logic the desktop app (`../main.py`) uses,
built with [Kivy](https://kivy.org) so it can be packaged as a real Android APK.
`psovmu/` in this directory is a symlink to `../psovmu` -- there's only one copy
of the crypto/character/item logic, shared by both UIs.

**Status**: feature-complete parity with the desktop app, and the APK builds
successfully. Folder picker with persisted folder+serial and a name/class/
level preview; a character editor (level/EXP/meseta/stats/quest-flags); and
Bank/Inventory item editing for all 10 categories (Guns/Swords/Wands incl.
S-rank, Armor, Shields, Units, Mags, Technique Disks, Parts, Tools), including
the same equip-check warning and existing-item pre-fill the desktop app has.
Not yet done: installing it on a real device (plyer's Android folder-picker
backend is unverified until then -- see [INSTALL.md](INSTALL.md)).

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
