# PSO V2 VMU Editor (MVP)

Drag-and-drop editor for PSO Dreamcast V2 character VMU save files.

## Running

Double-click `run.command`, or from a terminal:
```
cd ~/PSOVMUEditor
python3 main.py
```

## Usage

1. Drag a VMU `.bin` file onto the window (or click it to open a file picker).
2. Enter the disc/account serial number when prompted (this is the decryption key
   for the save — if it's wrong you'll get a checksum-mismatch error and can retype
   it). This is an 8-character hex value, e.g. `12345678`; it's tied to your
   PSO disc/account, not something this project can supply.
3. **Character tab**: edit level/EXP/meseta/stats directly, or use "Sync EXP + stats
   to Level field" to auto-fill correct values from the real game's level-up table
   (preserves any Material-item stat bonuses already earned). "Unlock ALL quest
   flags" opens every area/difficulty.
4. **Bank / Inventory tabs**: select a slot, click "Add / Replace Item in Selected
   Slot" to open the item builder (choose a category, then a specific item, then
   any customizable fields like grind/attributes/mag stats/tech level).
5. Click **Save**. A `.bak` backup of the original file is made the first time you
   save; the app re-encrypts, verifies the round-trip, writes to disk, then
   re-reads the saved file fresh to confirm it's valid before reporting success.

## What's covered (curated item lists from the research session)

- Guns, Swords, Wands: all 8★+ weapons plus their S-rank category placeholders
- Armor, Shields, Units: all 9★+ items with legit max stats
- Mags: all 58 species (build any level/stat/synchro/IQ/color/photon-blast combo)
- Technique disks: all 19 techniques at any level
- Parts: the 46 real "special quest item" entries (enemy parts, hearts, kits, amps)

This is **not the full game item catalog** — see the "v2" phase note in project
history: a complete catalog needs the game's own text table (`unitxt`) decoded for
full accurate names, which is a separate, larger effort.

## Project layout

```
main.py                        GUI (tkinter + tkinterdnd2)
psovmu/crypto.py                PSOV2Encryption / ShuffleTables / encrypt/decrypt_fixed
psovmu/vmu.py                   VMU directory parsing, FAT chains, splice-and-save
psovmu/character.py             Character struct field access, level-table sync logic
psovmu/items.py                 Item byte encoders/decoders for every item type
psovmu/item_database.py         Curated item lists (names/stats/byte codes)
psovmu/data/level-table-v1-v2.json   Real per-class level-up stat curves
```

## License

MIT — see [LICENSE](LICENSE).
