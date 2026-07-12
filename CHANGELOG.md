# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Tools category** in the item builder: Monomate/Dimate/Trimate, Mono/Di/Trifluid,
  Sol/Moon/Star Atomizer, Antidote/Antiparalysis, Telepipe, Trap Vision, Scape
  Doll, Mono/Di/Trigrinder, all 8 Materials, and 6 Cell/Heart items -- these
  previously showed as "Unknown item" in the Bank/Inventory list with no way
  to add them. Stackable items (Mates, fluids, Atomizers, Scape Doll, etc.)
  get an Amount field; the bank-slot stack count (stored in a separate wrapper
  field, not in the item bytes themselves) is now set correctly too.

### Fixed
- The "Parts" category's names were misaligned with the wrong byte codes
  starting partway through -- e.g. "S-red's Arms" was wrongly mapped to
  0x0D/0x06 (really 0x0E/0x00) -- corrected against the client's own item
  text index (`names-v2.json` from fuzziqersoftware/newserv). All 46 entries
  re-verified to round-trip correctly.
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
