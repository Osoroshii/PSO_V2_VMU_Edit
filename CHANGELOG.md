# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.3.1] - 2026-07-14

### Added
- **Section ID editing** (desktop Character tab and Android editor screen):
  previously read-only in both UIs. Section ID determines which drop tables
  the game consults for a character, so this lets a player switch to hunt
  items their original Section ID couldn't find. Confirmed safe via real
  gameplay before wiring up either GUI: changed a real character's Section
  ID (Skyly -> Bluefull) via `character.set_section_id`, no crash, and the
  new value survived an in-game save + reload -- unlike the level/EXP field,
  the client does not silently re-derive or correct this one.

## [0.3.0] - 2026-07-14

### Added
- **Full V2 item catalog** for Guns/Swords/Wands/Armor/Shields/Units, replacing the
  previous hand-curated "8-star+/9-star+" subsets -- 60 guns, 102 swords (including
  a whole Knuckle category that was previously missing entirely: BRAVE KNUCKLE/ANGRY
  FIST/GOD HAND/SONIC KNUCKLE), 44 wands, 53 armors, 58 shields, and 68 units, every
  one down to the plain 0-star basics (Saber, Handgun, Frame, Barrier, Knight/Power,
  etc.). Built by extracting this disc's own `ITEMPMT.PRS` straight out of a real GD-ROM
  `.cdi` image (new CDI-parsing + PRS-decompression code, not shipped as part of the
  app -- see `docs/REFERENCE.md` section 10 for the full pipeline) and cross-checking
  its structure/counts against newserv's `item-parameter-table-pc-v2.json` and
  `names-v2.json` before generating the lists from the latter two. Also found and
  fixed several small inaccuracies in the old curated names ("STIRKER OF CHAO" ->
  "STRIKER OF CHAO", "REGENE GEAR ADV" -> "REGENE GEAR ADV.") and found 3 real V2
  weapons the curated list had missed (ROCKET PUNCH, SAMBA MARACAS, BARANZ LAUNCHER).
- `item_database.weapon_labels()`/`item_labels()`: shared label-list helpers that
  disambiguate items sharing an identical in-game display name (e.g. all 7 AGITO
  variants render as plain "AGITO" in the client's own text table) with a `[i/n]`
  suffix. `main.py`'s six weapon/armor/unit dropdown call sites now go through these
  instead of rebuilding an ad-hoc label list inline, which would otherwise make every
  same-named item after the first permanently unselectable (`list.index()` on a
  colliding label always resolves to the first match).
- `tests/` pytest suite (25 tests): encryption round-trip, encode/decode
  round-trip for every item category (including all 46 Parts and 31 Tools
  entries), and level-sync math (with and without preserved Material bonus).
  Synthetic data only, no real save files bundled. `requirements-dev.txt`
  added for `pytest`.
- GitHub Actions CI (`.github/workflows/ci.yml`): runs on every push/PR across
  macOS, Windows, and Ubuntu, on Python 3.11 and 3.13.
- `android/tests/` pytest suite (42 tests): started with `session.py`,
  `vmu_scan.py`, `storage.py`, and `fileio.py`'s desktop branch (pure-Python
  glue modules, no Kivy widgets), then extended to the real screens --
  `main.py`'s `PickerScreen`/`EditorScreen` and `item_screens.py`'s
  `ItemListScreen`/`ItemPickerScreen` -- constructed and driven for real via a
  new `app_screen_manager` fixture (a `ScreenManager` wired up exactly like
  `PSOVMUApp.build()`), not mocked. Includes a regression test for the stale
  equip-check-label bug documented in `android/README.md`'s "Notes for whoever
  picks this up next" (switching category left the previous category's
  "Usable by: ..." text on screen) and a smoke test building/decoding one
  item from every one of the 10 item categories. Synthetic VMU images
  only, built with a new `android/tests/vmu_helpers.py`. Added a matching
  `android-test` CI job (Ubuntu + macOS, Python 3.11/3.13; Ubuntu runs it
  under `xvfb-run` since constructing a real Kivy widget lazily opens an
  SDL2 window). No Windows: Kivy's freshly-downloaded DLLs reliably hang the
  whole job for its full CI timeout on GitHub's Windows-hosted runners,
  confirmed via job logs to happen before pytest even starts collecting test
  files (three different fixes attempted and ruled out before concluding
  this belonged at the workflow level, not in the test code -- see the
  comment in `.github/workflows/ci.yml`). GitHub's macOS-hosted runners have
  no display at all and no headless fallback; `conftest.py`'s
  `_detect_kivy_window_support` skips the widget-dependent tests there
  instead of erroring -- a real macOS (or Windows) developer machine still
  runs them for real, since neither failure mode was observed outside CI.

### Fixed
- The Docker/Buildozer APK build (`android/INSTALL.md`) minted a fresh debug
  signing key on every `docker run`, since nothing under `~/.android` (where
  the Android Gradle Plugin auto-generates `debug.keystore` -- the generated
  `build.tmpl.gradle` only sets an explicit `signingConfig` for release
  builds, so debug builds always fell through to that default) was persisted
  across the container's `--rm` lifecycle. Every rebuild-and-reinstall
  therefore failed with `INSTALL_FAILED_UPDATE_INCOMPATIBLE` unless you
  `adb uninstall`ed first. Added a second named volume
  (`buildozer-android-keystore`) at `/root/.android` -- despite the image's
  own convention of `/home/user/...` paths for everything else, the container
  actually runs as root, so `~` there is `/root`; confirmed by running the
  build twice and diffing `debug.keystore`'s checksum between runs.
- `PickerScreen.rescan()` (`android/main.py`) had no error handling around
  scanning the saved VMU folder, unlike the folder-picker button. `rescan()`
  runs unconditionally every time this screen is shown (including on app
  launch, if a folder+serial were already saved), so a folder whose access
  went stale between sessions -- a revoked SAF permission grant, a removed SD
  card, a deleted folder -- would crash the app on next open instead of
  showing an error. Now degrades to a status message.
- `item_database.check_equip()` crashed with a `TypeError` on every Unit item --
  the bundled reduced PMT data has `"UsabilityFlags": null` for units (they have no
  such field in the real on-disk struct at all), and the code indexed into it
  unconditionally. This meant the Unit tab's "who can use this" equip-check label
  has been crashing since it was added, in every prior release. Now treats a missing
  usability flag as "usable by everyone."
- `build_srank_weapon`'s `special_index` hardcoding (confirmed broken via real
  gameplay, see v0.2.0's release notes) only lived at the GUI call site -- any
  other caller could have silently reintroduced a broken item. Now enforced inside
  the function itself regardless of what's passed.

## [0.2.0] - 2026-07-12

### Added
- **Tools category** in the item builder: Monomate/Dimate/Trimate, Mono/Di/Trifluid,
  Sol/Moon/Star Atomizer, Antidote/Antiparalysis, Telepipe, Trap Vision, Scape
  Doll, Mono/Di/Trigrinder, all 8 Materials, and 6 Cell/Heart items -- these
  previously showed as "Unknown item" in the Bank/Inventory list with no way
  to add them. Stackable items (Mates, fluids, Atomizers, Scape Doll, etc.)
  get an Amount field; the bank-slot stack count (stored in a separate wrapper
  field, not in the item bytes themselves) is now set correctly too.
- `docs/REFERENCE.md`: the deeper technical writeup (encryption derivation,
  full character/item struct offsets, and gotchas found during
  reverse-engineering), previously only existed outside the repo.

### Fixed
- The "Parts" category's names were misaligned with the wrong byte codes
  starting partway through -- e.g. "S-red's Arms" was wrongly mapped to
  0x0D/0x06 (really 0x0E/0x00) -- corrected against the client's own item
  text index (`names-v2.json` from fuzziqersoftware/newserv). All 46 entries
  re-verified to round-trip correctly. Also confirmed via real gameplay that
  the "Weapons ___ Badge" items in this category are real/valid V2 items,
  resolving an open question the correction raised.
- The Save button (and the item-tab action buttons above it) could render as
  a blank, unlabeled gray sliver -- the Save bar was packed *after* a
  `fill="both", expand=True` notebook, which greedily claimed space and
  squeezed the bar down whenever the window wasn't tall enough. Fixed by
  reserving the Save bar's space first (`side="bottom"`) before the notebook
  fills the remainder, and by increasing the default window size so
  everything fits without cramping.

## [0.1.0] - 2026-07-12

Initial release.

### Added
- Drag-and-drop (or click-to-open) loading of PSO Dreamcast V2 VMU `.bin` save
  files, with automatic VMU directory/FAT parsing to locate the character
  file (no hardcoded block assumptions).
- Serial number entry for decryption, with the last-used serial remembered
  across sessions (`~/.psovmu_editor_config.json`) and pre-filled/selected
  next time.
- **Character tab**: edit level, EXP, meseta, and stats directly; "Sync EXP +
  stats to Level" auto-fills correct values from the real per-class level-up
  table while preserving any Material-item stat bonuses already earned;
  "Unlock ALL quest flags" opens every area/difficulty.
- **Bank/Inventory tabs**: human-readable item descriptions resolved from
  real item names (not raw hex class/variant codes) for weapons, armor,
  shields, units, mags, tech disks, and quest parts.
- **Item builder** covering:
  - Guns/Swords/Wands (8★+) including S-rank weapons with custom names
  - Armor/Shields/Units (9★+) with legit max stat bonuses
  - Mags: all species (real names), stat levels, synchro, IQ, color, and all
    3 photon blast slots (Center/Right/Left, with the on-disk 2-bit Left-slot
    limit respected)
  - Technique disks (all 19 techniques, any level)
  - Quest "Parts" items (46 real enemy-part/kit/amplifier entries)
- **Edit existing items**: re-opening the item builder on a filled slot
  pre-fills every field from that item's current values, instead of only
  supporting build-from-scratch.
- **Equip-compatibility checking**: before adding a weapon/armor/shield/unit,
  the dialog shows whether the loaded character can actually equip it
  (job/race/gender requirements and stat requirements from the real item
  parameter table), with a confirmation prompt if not.
- Save writes back to the original file: makes a `.bak` backup on first save,
  re-encrypts, verifies the round-trip, writes to disk, then re-reads the
  saved file fresh to confirm it's valid before reporting success.
- Cross-platform launchers: `run.command` (macOS) and `run.bat` (Windows),
  both setting up a venv with `tkinterdnd2` on first run.

### Fixed
- Several macOS/Tk-specific dialog bugs: blank window rendering (root cause:
  the macOS system Python's outdated bundled Tcl/Tk), dialogs opening without
  keyboard focus, and a button click silently failing due to a stale widget
  reference left over from switching item categories.
- S-rank weapon "special attack" byte (`data1[2]`) was being used incorrectly
  (based on an unverified assumption from third-party docs) and made items
  show a garbled name and become unequippable in-game; it's now hardcoded to
  0 until the real mechanism is found. Custom S-rank names themselves were
  confirmed correct and unaffected.

### Known limitations
- Item lists are curated (8★+/9★+ items, one list per category) rather than
  the full in-game item catalog -- a complete catalog would need the game's
  own text table (`unitxt`) decoded.
- S-rank weapon "special attack" is disabled pending further research (see
  Fixed, above).
