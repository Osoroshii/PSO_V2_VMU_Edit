# Contributing

## Setup

Clone the repo, then set up a virtual environment and install dependencies.

**macOS:**
```
git clone https://github.com/Osoroshii/PSO_V2_VMU_Edit.git
cd PSO_V2_VMU_Edit
/opt/homebrew/bin/python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python3 main.py
```
Use Homebrew's Python (not `/usr/bin/python3`, macOS's bundled system Python)
-- the system Python ships an old Tcl/Tk that renders the window blank.

**Windows:**
```
git clone https://github.com/Osoroshii/PSO_V2_VMU_Edit.git
cd PSO_V2_VMU_Edit
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python main.py
```

Or just double-click `run.command` (macOS) / `run.bat` (Windows) -- both set
up the venv automatically on first run.

## Project layout

```
main.py                        GUI (tkinter + tkinterdnd2)
psovmu/crypto.py                PSOV2Encryption / ShuffleTables / encrypt/decrypt_fixed
psovmu/vmu.py                   VMU directory parsing, FAT chains, splice-and-save
psovmu/character.py             Character struct field access, level-table sync logic
psovmu/items.py                 Item byte encoders/decoders for every item type
psovmu/item_database.py         Curated item lists, real item names, equip-requirement checks
psovmu/data/                    Bundled reference tables (level curve, item parameter table)
```

## Testing changes

There's a small pytest suite (`tests/`) covering the encryption round-trip,
every item category's encode/decode round-trip, and the level-sync math --
run it with:
```
pip install -r requirements-dev.txt
pytest tests/ -v
```
It runs in CI (`.github/workflows/ci.yml`) across macOS/Windows/Ubuntu on
every push and PR. It's deliberately synthetic (no real save data, no GUI/Tk
interaction) -- it catches regressions in the byte-level logic, but it can't
verify anything about how an item actually behaves in-game.

For that, and for any new item/encoding work:
1. Use a real VMU save file (or ask in an issue/discussion if you need a sample).
2. Load it, make an edit, and Save -- the app backs up the original to `.bak`
   the first time, re-encrypts, verifies the round-trip, and re-reads the
   saved file fresh before reporting success. If any of that fails, it'll
   tell you rather than silently writing a corrupt file.
3. Ideally, confirm the change actually shows up correctly in an emulator
   (Flycast) or on real hardware -- some encoding assumptions that look right
   on paper (or even match community reverse-engineering docs) have turned
   out to be wrong in practice. See the GOTCHA comments in `psovmu/items.py`
   and `psovmu/character.py` for examples already found this way -- and add a
   regression test alongside the fix when you find one.

## A note on item/format data

Byte formats and item lists here were reverse-engineered against real save
files, cross-referenced with [fuzziqersoftware/newserv](https://github.com/fuzziqersoftware/newserv)'s
parameter tables where possible. Where the two disagree, trust a real save
file over a theory -- and please open an issue/PR noting the discrepancy so
the assumption gets corrected for everyone, not just worked around locally.

## Submitting changes

1. Fork the repo and create a branch for your change.
2. Keep PRs focused -- one fix/feature per PR is easier to review than a
   bundle of unrelated changes.
3. Never commit real VMU save files, `.bak` backups, or your own `venv/` --
   the `.gitignore` already excludes these, but double-check `git status`
   before committing if you're working with real save data during testing.
4. Open a PR describing what changed and why (and how you tested it).
