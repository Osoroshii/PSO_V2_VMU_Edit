# PSO Dreamcast V2 VMU Save Editing — Reference Notes

Everything below was reverse-engineered and empirically validated (against real save
data) across several development sessions. Read this before starting new VMU/PSO save
work — it will save re-deriving all of this from scratch.

The serial number (round1 decryption key) and access key are tied to a specific
account/disc and aren't included here -- the app prompts for the serial when you load
a file, and remembers the last one used. If a VMU file doesn't decrypt (checksum
mismatch), the serial you entered doesn't match that file's account -- try again with
the correct one rather than assuming any particular value.

Several save files were used as "mule" characters for organizing specific item
categories during development/testing (mags, weapons, tech disks, etc., each isolated
in their own VMU slot) -- referenced by nickname in places below for continuity with
how they came up during development, not because the names matter.

---

## 1. Finding the right file inside a VMU image

A single `.bin` VMU image (always 131072 bytes = 256 blocks × 512 bytes) can contain
**multiple files** — a character save (`PSO______SYS`), a Guild Card list
(`PSO______2GC`), and PSO "download quest"/bank-transfer files (`PSO______004` etc.).

**Do not assume the character save starts at block 199** — that was true for some
files in this session but NOT all of them (one VMU had the character SYS file start at
block 169, with the Guild Card file at 199). **Always parse the actual VMU directory
first** to find the file named `PSO______SYS` and its real `start_block`.

```python
import struct

def bcd(b):
    return (b >> 4) * 10 + (b & 0xF)

def parse_timestamp(ts):
    year = bcd(ts[0])*100 + bcd(ts[1])
    month, day, hour, minute, second = bcd(ts[2]), bcd(ts[3]), bcd(ts[4]), bcd(ts[5]), bcd(ts[6])
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

def list_vmu_directory(path):
    with open(path, "rb") as f:
        data = f.read()
    BLOCK = 512
    ROOT_BLOCK = 255
    root = data[ROOT_BLOCK*BLOCK:(ROOT_BLOCK+1)*BLOCK]
    dir_loc = struct.unpack_from("<H", root, 0x4A)[0]
    dir_size = struct.unpack_from("<H", root, 0x4C)[0]
    entries = []
    for i in range(dir_size):
        block_num = dir_loc - i
        block = data[block_num*BLOCK:(block_num+1)*BLOCK]
        for e in range(0, BLOCK, 32):
            entry = block[e:e+32]
            file_type = entry[0]
            if file_type == 0x00:
                continue
            start_block = struct.unpack_from("<H", entry, 2)[0]
            filename = entry[4:16].decode("shift_jis", errors="replace").rstrip()
            size_blocks = struct.unpack_from("<H", entry, 0x18)[0]
            ts = parse_timestamp(entry[0x10:0x18])
            entries.append({"type": file_type, "name": filename, "start_block": start_block,
                             "size_blocks": size_blocks, "saved": ts})
    return entries

def get_fat_chain(data, start_block):
    BLOCK = 512
    fat = struct.unpack_from("<256H", data[254*BLOCK:255*BLOCK], 0)
    chain = []
    cur = start_block
    seen = set()
    while True:
        chain.append(cur)
        seen.add(cur)
        nxt = fat[cur]
        if nxt == 0xFFFA or nxt in seen or nxt >= 256:
            break
        cur = nxt
    return chain
```

Standard VMU layout: root block = 255, FAT = block 254 (usually), directory grows
downward from block 253 (usually 13 blocks). But **use the root block's own pointers**
(`0x46`=FAT loc, `0x4A`=dir loc, `0x4C`=dir size) rather than hardcoding 253/254 — this
session always saw those values but don't assume it's universal.

---

## 2. VMS file header (every character/data file starts with this, 0x80 + icon bytes)

```
offset 0x00-0x0F : short_desc (ASCII, 16 bytes) — e.g. "PSOV2/MAIN_DATA "
offset 0x10-0x2F : long_desc (ASCII, 32 bytes)
offset 0x30-0x3F : creator_id (16 bytes)
offset 0x40-0x41 : num_icons (u16 LE) — normally 1
offset 0x42-0x43 : animation_speed (u16 LE)
offset 0x44-0x45 : eyecatch_type (u16 LE)
offset 0x46-0x47 : crc (u16 LE)
offset 0x48-0x4B : data_size (u32 LE) — size of the ENCRYPTED payload that follows
offset 0x4C-0x5F : unused (0x14 bytes)
offset 0x60-0x7F : icon_palette (16 x u16 LE)
offset 0x80+     : icon bitmap data, num_icons * 0x200 bytes
after that       : the actual encrypted character/data payload, `data_size` bytes long
```

So: `char_file_offset = 0x80 + num_icons * 0x200`, and the encrypted blob is
`file_bytes[char_file_offset : char_file_offset + data_size]`.

For a `PSO______SYS` character file, `data_size` should be exactly `0x16FC` (5884) —
this is `sizeof(PSODCV2CharacterFile)`. If it's a different size, this may not be a V2
character file (could be V1, or something else) — the struct layout below won't apply
as-is.

---

## 3. PSO V2 encryption (round1 = serial number, round2 = embedded seed)

This is **not** simple XOR. It's a two-round scheme: round 1 uses `PSOV2Encryption`
(a Fibonacci-style stream cipher used both as a subtract-cipher AND to seed a byte
shuffle table) keyed by the account serial number; round 2 is a plain XOR stream keyed
by a seed embedded in the plaintext itself (the last 4 bytes of the struct). Below is
the complete, validated implementation (validated by re-encrypting and re-decrypting
real data and confirming byte-for-byte round trips, and by checksum matching on
untouched real save data before ever editing anything).

```python
import struct, zlib, random

class PSOV2Encryption:
    STREAM_LENGTH = 0x38
    def __init__(self, seed):
        self.stream = [0] * (self.STREAM_LENGTH + 1)
        self.end_offset = self.STREAM_LENGTH
        seed &= 0xFFFFFFFF
        a, b = 1, seed
        self.stream[0x37] = b
        vi = 0x15
        while vi <= 0x36 * 0x15:
            self.stream[vi % 0x37] = a
            c = (b - a) & 0xFFFFFFFF
            b = a
            a = c
            vi += 0x15
        for _ in range(5):
            self.update_stream()

    def update_stream(self):
        for z in range(1, 0x19):
            self.stream[z] = (self.stream[z] - self.stream[z + 0x1F]) & 0xFFFFFFFF
        for z in range(0x19, 0x38):
            self.stream[z] = (self.stream[z] - self.stream[z - 0x18]) & 0xFFFFFFFF
        self.offset = 1

    def next(self):
        if self.offset == self.end_offset:
            self.update_stream()
        v = self.stream[self.offset]
        self.offset += 1
        return v

    def encrypt_minus(self, data):  # subtract-cipher; self-inverse when reapplied with same seed
        n = len(data) // 4
        for x in range(n):
            val = struct.unpack_from("<I", data, x*4)[0]
            struct.pack_into("<I", data, x*4, (self.next() - val) & 0xFFFFFFFF)

    def encrypt_xor(self, data):  # plain xor stream; self-inverse
        n = len(data) // 4
        for x in range(n):
            val = struct.unpack_from("<I", data, x*4)[0]
            struct.pack_into("<I", data, x*4, val ^ self.next())


class ShuffleTables:
    def __init__(self, crypt):
        self.forward_table = list(range(0x100))
        self.reverse_table = [0] * 0x100
        r28 = 0xFF
        r31 = 0xFF
        while r28 >= 0:
            r3 = self.pseudorand(crypt, r28 + 1)
            t = self.forward_table[r3]
            self.forward_table[r3] = self.forward_table[r31]
            self.forward_table[r31] = t
            self.reverse_table[t] = r28
            r31 -= 1
            r28 -= 1

    @staticmethod
    def pseudorand(crypt, prev):
        return (((prev & 0xFFFF) * ((crypt.next() >> 16) & 0xFFFF)) >> 16) & 0xFFFF

    def shuffle(self, src, reverse):
        table = self.reverse_table if reverse else self.forward_table
        size = len(src)
        dest = bytearray(size)
        full = size & 0xFFFFFF00
        for bo in range(0, full, 0x100):
            for z in range(0x100):
                dest[bo + table[z]] = src[bo + z]
        rs = full
        rl = size & 0xFF
        dest[rs:rs+rl] = src[rs:rs+rl]
        return bytes(dest)


def encrypt_data_section(plain, round1_seed):
    buf = bytearray(plain)
    pad = (-len(buf)) % 4
    if pad:
        buf += b"\x00" * pad
    PSOV2Encryption(round1_seed).encrypt_minus(buf)
    shuf = ShuffleTables(PSOV2Encryption(round1_seed))
    return shuf.shuffle(bytes(buf), False)[:len(plain)]

def decrypt_data_section(data_section, round1_seed):
    shuf = ShuffleTables(PSOV2Encryption(round1_seed))
    dec = bytearray(shuf.shuffle(data_section, True))
    PSOV2Encryption(round1_seed).encrypt_minus(dec)
    return bytes(dec)

def decrypt_fixed(data_section, struct_size, round1_seed):
    """Decrypt a fixed-size struct (e.g. PSODCV2CharacterFile, 5884 bytes).
    Returns (plaintext, expected_checksum, actual_checksum) — ALWAYS check these match
    before trusting/using the plaintext, and before writing anything back."""
    dec = bytearray(decrypt_data_section(data_section, round1_seed)[:struct_size])
    round2_seed = struct.unpack_from("<I", dec, struct_size - 4)[0]
    portion = bytearray(dec[:struct_size - 4])
    PSOV2Encryption(round2_seed).encrypt_xor(portion)
    dec[:struct_size - 4] = portion
    checksum = struct.unpack_from("<I", dec, 0)[0]
    dec[0:4] = b"\x00" * 4
    actual = zlib.crc32(bytes(dec[:struct_size])) & 0xFFFFFFFF
    dec[0:4] = struct.pack("<I", checksum)
    return bytes(dec), checksum, actual

def encrypt_fixed(plaintext_struct, struct_size, round1_seed):
    """Inverse of decrypt_fixed. Picks a FRESH random round2_seed each call (this is
    normal/expected — the game does this too — don't try to reuse the old one)."""
    buf = bytearray(plaintext_struct)
    buf[0:4] = b"\x00" * 4
    r2seed = random.randrange(0, 0x100000000)
    struct.pack_into("<I", buf, struct_size - 4, r2seed)
    checksum = zlib.crc32(bytes(buf[:struct_size])) & 0xFFFFFFFF
    struct.pack_into("<I", buf, 0, checksum)
    portion = bytearray(buf[:struct_size - 4])
    PSOV2Encryption(r2seed).encrypt_xor(portion)
    buf[:struct_size - 4] = portion
    return encrypt_data_section(bytes(buf), round1_seed)
```

**MANDATORY verification pattern for every edit:**
```python
dec, exp_crc, act_crc = decrypt_fixed(data_section, data_size, SERIAL)
assert exp_crc == act_crc                     # verify BEFORE editing
modified = bytearray(dec)
# ... make your edits to `modified` ...
reenc = encrypt_fixed(bytes(modified), data_size, SERIAL)
check_dec, exp_crc2, act_crc2 = decrypt_fixed(reenc, data_size, SERIAL)
assert exp_crc2 == act_crc2                   # verify the re-encrypted blob decrypts validly
a = bytearray(check_dec); a[0:4] = b"\x00"*4; a[-4:] = b"\x00"*4
b = bytearray(modified);  b[0:4] = b"\x00"*4; b[-4:] = b"\x00"*4
assert bytes(a) == bytes(b)                   # content matches except checksum/round2_seed (expected to differ)
```
Then splice `reenc` back into `file_bytes` at the same offset, write the block chain
back into the VMU image, save the file, and **re-read it fresh from disk** as a final
independent check (don't just trust in-memory state).

---

## 4. `PSODCV2CharacterFile` struct layout (the decrypted 5884-byte payload)

All offsets below are **absolute within the decrypted payload** (i.e. relative to the
start of `dec`/`modified` in the code above).

```
0x0000            : checksum (u32) — zeroed before CRC, restored after
0x0004            : Character struct begins here ("char_base = 4")
```

Within `Character` (offsets shown as `char_base + N`):
```
+0x0000 (0x34C bytes) : PlayerInventory
    +0x0000           : num_items (u8)
    +0x0001           : hp_from_materials (u8)
    +0x0002           : tp_from_materials (u8)
    +0x0003           : language (u8)
    +0x0004           : items[30], each 0x1C bytes:
        +0x00 state (u8: 0=floor,1=inv-unequipped,2=inv-equipped,3=destroying)
        +0x01 unknown_a1 (u8)
        +0x02-3        extension bytes
        +0x04 flags (u32)
        +0x08 ItemData (12+4+4 = 20 bytes: data1[12], id(u32), data2[4]) — see section 6
+0x034C           : PlayerDispDataV123 (disp)
    +0x00 stats (PlayerStatsT, 0x24 bytes):
        +0x00 atp (u16) +0x02 mst (u16) +0x04 evp (u16) +0x06 hp (u16)
        +0x08 dfp (u16) +0x0A ata (u16) +0x0C lck (u16) +0x0E esp (u16)
        # GOTCHA (session 3, corrected): esp was INITIALLY guessed to be the
        # in-game "Photon Points" resource (partly because MaxStats.ESP is 100
        # for every class in level-table-v1-v2.json, and a real character's esp
        # read exactly 100). This guess was WRONG -- the user confirmed by
        # testing that the "Photon Points" spent in the online quest "Gorgon's
        # Shop" (used to modify weapons/armor) is tracked SERVER-SIDE by the
        # private server, not in the local VMU save at all: an exhaustive byte
        # search (exact-value match, both byte orders, 16/32-bit, across the
        # entire decrypted character struct including undocumented regions)
        # found no field that tracked the user's real point balance as it
        # changed (1000 -> 550 -> 350) across real play sessions. The GUI's
        # "Photon Points" field and character.py's get_esp/set_esp were removed
        # as a result. What `esp` actually represents in-game is still unknown
        # -- do not assume it's Photon Points or anything else without new
        # evidence.
        +0x10 attack_range (f32) +0x14 knockback_range (f32)
        +0x18 level (u32)   <-- STORED 0-INDEXED, see gotcha below
        +0x1C exp (u32)
        +0x20 meseta (u32)
    +0x24 visual (PlayerVisualConfigV123T, 0x50 bytes):
        +0x00 name (ASCII, 16 bytes, null-padded)
        +0x10 sh (PlayerVisualConfigSharedT, 0x40 bytes):
            +0x08 name_color (u32, ARGB)
            +0x20 section_id (u8)
            +0x21 char_class (u8)   — 0=HUmar 1=HUnewearl 2=HUcast 3=RAmar 4=RAcast
                                       5=RAcaseal 6=FOmarl 7=FOnewm 8=FOnewearl
            +0x22 validation_flags (u8)
            +0x23 version (u8)
            +0x28 costume,skin,face,head,hair,hair_r,hair_g,hair_b (8 x u16)
            +0x38 proportion_x, proportion_y (2 x f32)
    +0x74 config[0x48]
    +0xBC technique_levels_v1[0x14]
+0x041C           : validation_flags (u32)
+0x0420           : creation_timestamp (u32, unix epoch)
+0x0424           : signature (u32) — MUST equal 0xA205B064 for a valid V2 character;
                    check this after decrypting as a sanity/offset-correctness check
+0x0428           : play_time_seconds (u32)
+0x042C           : option_flags (u32)
+0x0430           : save_count (u32)
+0x0434           : ppp_username (ASCII, 0x1C bytes)
+0x0450           : ppp_password (ASCII, 0x10 bytes)
+0x0460 (0x200 b) : quest_flags — 4 difficulty tables x 0x80 bytes (1024 bits) each,
                    in order [Normal, Hard, Very Hard, Ultimate]. Each bit = one story/
                    quest completion flag (bit index = flag ID from newserv's
                    notes/quest-flags.txt, see section 7).
+0x0660 (0x5A8 b) : PlayerBank60 (bank)
    +0x00 num_items (u32)
    +0x04 meseta (u32)
    +0x08 items[60], each 0x18 bytes: ItemData(20) + amount(u16) + present(u16)
+0x0C08           : GuildCardDC guild_card
+0x0C88           : symbol_chats[12]
+0x10A8           : shortcuts[20]
+0x15A8           : v1_serial_number (ASCII 0x10)
+0x15B8           : v1_access_key (ASCII 0x10)
+0x15C8           : battle_records
+0x15E0           : challenge_records
+0x1680           : tech_menu_shortcut_entries
+0x16A8           : choice_search_config
+0x16D4           : v2_serial_number (ASCII 0x10) — matches the account serial as text
+0x16E4           : v2_access_key (ASCII 0x10)
```
Total `Character` size = 0x16F4, then at absolute payload offset `0x16F8`:
`round2_seed (u32)` — this is the very last 4 bytes of the 5884-byte struct.

### GOTCHA: level is stored 0-indexed
`stats.level` (payload offset `disp_base + 0x18`, i.e. `char_base + 0x034C + 0x18`)
is **displayed in-game as `stored_level + 1`**. Empirically confirmed: writing `200`
made the game show "Level 201"; writing `199` correctly showed "Level 200". **To set
a character to displayed level N, store N-1.**

### GOTCHA: PSO seems to re-derive level from EXP on its own, not trust the raw field
After writing `level=200, exp=<huge legit-for-level-200 value>` and having the user
load+play the character in Flycast, the save came back with `level=199, exp=0` — i.e.
the game/emulator processed the stored EXP against its own internal per-level
thresholds and cascaded through level-ups until the EXP was exhausted, landing exactly
where the EXP total was "spent" to. This means: **as long as EXP and level are set to
values that are mutually consistent per the real level table (section 5), the save is
"self-healing" and stable** — but if you set an inconsistent pair (e.g. level far ahead
of what the EXP would produce), expect the game itself to correct it on next load, not
necessarily in the direction you intended. Always compute EXP from the same table used
to derive the target level (don't just pick an arbitrary big number).

---

## 5. Level / EXP / stat cap system

Source of truth: `system/tables/level-table-v1-v2.json` in
`fuzziqersoftware/newserv` (GitHub). Structure:
```json
{
  "BaseStats": [ {ATP,MST,EVP,HP,DFP,ATA,LCK}, ... one per class index 0-8 ... ],
  "LevelDeltas": [ [ {ATP,MST,EVP,HP,DFP,ATA,LCK,EXP,TP}, ... 200 entries ... ], ... per class ... ],
  "MaxStats": [ {ATP,MST,EVP,HP,DFP,ATA,LCK,ESP,Level,EXP,Meseta,AttackRange,KnockbackRange}, ... per class ... ]
}
```
Class index order: `0=HUmar 1=HUnewearl 2=HUcast 3=RAmar 4=RAcast 5=RAcaseal
6=FOmarl 7=FOnewm 8=FOnewearl` (matches `char_class` byte in the save).

**Indexing convention that matches the game's actual stored (0-indexed) level:**
```python
cum_exp = 0
cum = dict(base_stats[class_idx])
by_displayed_level = {}
for i, d in enumerate(level_deltas[class_idx]):        # i = 0..199
    cum_exp += d['EXP']
    for k in ['ATP','MST','EVP','HP','DFP','ATA','LCK']:
        cum[k] += d[k]
    by_displayed_level[i+2] = (cum_exp, dict(cum))     # after i+1 deltas -> displayed level i+2
```
`by_displayed_level[200]` gives `(exp, stats)` for **displayed level 200** (i.e. you'd
store `level=199`). Verified: `exp = 3170948139` for level 200 on every class tested
so far (the EXP curve appears to be class-independent; only the per-class stat deltas
differ) — but don't assume this is universal without re-deriving if it matters.

### Stats are usually ALREADY at the class cap on a well-played character
Empirically, on every "played a lot" character encountered (Osoroshii, Kovalev), most
of ATP/MST/EVP/DFP/ATA/LCK were **already sitting exactly at `MaxStats[class]`** —
because those stats grow both from leveling AND from permanently consuming Material
items (Power/Mind/Evade/Def/Luck Material), and a heavily-played character has usually
already maxed the Material-boostable stats long before hitting max level. **When
"maxing" a character to level 200, do NOT blindly overwrite these stats to
`MaxStats` directly** — instead, preserve whatever Material bonus the player has
already earned:
```python
cur_exp, cur_table_stats = by_displayed_level[CURRENT_DISPLAYED_LEVEL]
tgt_exp, tgt_table_stats = by_displayed_level[TARGET_DISPLAYED_LEVEL]  # e.g. 200
for k in ["ATP","MST","EVP","DFP","ATA","LCK","HP"]:
    material_bonus = current_actual_stat[k] - cur_table_stats[k]
    proposed = tgt_table_stats[k] + material_bonus
    final[k] = min(proposed, max_stats[class_idx][k])   # clamp to absolute class cap
```
This correctly leaves already-capped stats unchanged (proposed value clamps right back
to the same cap) while growing HP (which usually isn't fully Material-maxed) using the
level-based table growth on top of whatever HP Materials were already consumed.

---

## 6. Quest / story flag unlocks (per-difficulty area gating)

Offset: `char_base + 0x0460`, 0x200 bytes = 4 tables (Normal/Hard/Very Hard/Ultimate)
of 0x80 bytes (1024 bits) each. Bit `i` in table `d`: `table[i//8] & (1 << (i%8))`.

Reference for what each bit ID means: `notes/quest-flags.txt` in
`fuzziqersoftware/newserv` on GitHub — has ~220 documented flag IDs (hex) with
descriptions, including the specific difficulty-unlock chain (Dragon defeated → Caves,
Vol Opt → Ruins, TBoss4Type2 → unlocks Hard if set in Normal, TBoss4Type3 → unlocks
Very Hard/Ultimate if set in Hard/Very Hard respectively, etc.) and government-quest
flags (`01F5`-`0235`, `02BD`-`02C4` for Ep4).

**To unlock everything (all areas/difficulties, all side quests) for a character:**
just set every bit in all 4 tables to 1 (`0xFF` for each of the 0x200 bytes). Verified
this doesn't break anything and doesn't visibly conflict with other state. If instead
you need a SPECIFIC unlock (e.g. "just unlock Hard mode"), look up the specific flag ID
in quest-flags.txt and set only that bit — don't nuke the whole table if the user wants
something targeted.

---

## 7. Bank / Inventory structure and item formats

Bank: `char_base + 0x0660`. `num_items` (u32) @ +0, `meseta` (u32) @ +4, then 60 slots
of 0x18 bytes each starting at +8: `ItemData(20 bytes) + amount(u16) + present(u16)`.
**Capacity: 60 items.**

Inventory: `char_base + 0x0000`. `num_items` (u8) @ +0, then 30 slots of 0x1C bytes
each starting at +4: `state(1)+unknown(1)+ext(2)+flags(4)+ItemData(20)`.
**Capacity: 30 items.** For a floor/bank item being placed in inventory: `state=1`
(in inventory, not equipped), `flags=0`.

If you need more than 60 total items for one character, split across bank (60) +
inventory (30) = 90 max. Ask the user before clearing an existing non-empty inventory.

### `ItemData` raw bytes: `data1[12]` + `id(u32)` + `data2[4]`
```
data1[0] = item class: 0=Weapon 1=Armor/Shield/Unit 2=Mag 3=Tool 4=Meseta
```

**IMPORTANT general gotcha**: newserv's `encode_for_version`/`decode_for_version`
functions implement compatibility bit-packing tricks for translating items between
client versions **over the network** (e.g. a V1 client talking to a V2-aware server).
Some of these tricks (e.g. the tech-disk "level > 14 gets moved into an overflow byte"
scheme, and probably the weapon-kind ID compaction for `data1[1] > 0x26`) turned out to
**NOT apply to the raw local VMU save file** the actual DC client reads/writes for its
own single-player bank/inventory — confirmed by empirical failure (tech disk level 30
displayed as level 15 in Flycast when the overflow scheme was used) and by success
once using the *direct* (uncompacted) encoding instead. **When something is described
as "V2-specific encoding" in newserv, be skeptical it applies to local save files —
prefer to validate against a real existing item in the actual save file being edited
before trusting a network-oriented encoding scheme.** The one case where a V2-specific
bit-packing scheme WAS confirmed necessary and correct against real save data: **Mags**
(see below) — that one is genuinely how mags are stored on-disk in V1/V2, not just a
network quirk.

#### Weapons (`data1[0]=0`)
```
data1[1] = weapon class/kind byte (mostly unique per named weapon at the "special/rare"
           tier — see WeaponKind field below for the true equip-menu category)
data1[2] = weapon variant (0x00 for unique named weapons; 0x05/06/07 etc. for the
           3 top tiers within a base family like Saber/Sword/.../Handgun/Rifle/...)
data1[3] = grind
data1[4] = special attack index + flags (0 = no special)
data1[5] = present color / flags
data1[6],[7]  = attribute 1: type (1-5), value (int8, e.g. 30 = 30%)
data1[8],[9]  = attribute 2: type, value
data1[10],[11]= attribute 3: type, value
```
Attribute type values: `1=Native 2=A.Beast 3=Machine 4=Dark 5=Hit`. `type=0` means "no
bonus in that slot". Validated against real existing items in the user's save.

**S-rank weapons** (`data1[1]` in range `(0x6F,0x89)` or `(0xA4,0xAA)` exclusive —
i.e. `0x70-0x88` or `0xA5-0xA9`): the attribute-pair bytes (`data1[6..11]`) are
REPURPOSED to store a custom 8-character name instead, and `data1[2]` becomes a
"special" index (list: `None,Jellen,Zalure,HP-Revival,TP-Revival,Burning,Tempest,
Blizzard,Arrest,Chaos,Hell,Spirit,Berserk,Demon's,Gush,Geist,King's`). Encoding
algorithm (this is `newserv`'s `ItemNameIndex.cc` logic, byte-for-byte):
```python
S_RANK_CHARS = "\0ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_"
def bswap16(v): return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)

def build_srank_name(name):  # name: up to 8 chars, A-Z (no space char available!)
    name = name.upper()[:8]
    idx = [S_RANK_CHARS.index(c) for c in name] + [0]*(8-len(name))
    w3 = 0x8000 | (idx[1] & 0x1F) | ((idx[0] & 0x1F) << 5)
    w4 = 0x8000 | (idx[4] & 0x1F) | ((idx[3] & 0x1F) << 5) | ((idx[2] & 0x1F) << 10)
    w5 = 0x8000 | (idx[7] & 0x1F) | ((idx[6] & 0x1F) << 5) | ((idx[5] & 0x1F) << 10)
    # write bswap16(w3) at data1[6:8], bswap16(w4) at data1[8:10], bswap16(w5) at data1[10:12]
```
**GOTCHA (confirmed by real in-game test, session 2): `data1[2]` as an S-rank
"special index" is WRONG and BREAKS the item.** `ItemNameIndex.cc` (newserv)
reads `data1[2]` as a special-attack index for S-rank weapons when building its
own text description, and the original version of this doc copied that
assumption. Empirical test sequence against a real character (RAcast "Kovalev",
`/Volumes/MacEMU/bios/dc/PSO Saves/vmu_save_C1.bin`), isolating one variable at
a time:
1. `data1=0076036300008046 9c00 8000` (class 0x76 S-RANK RIFLE, name="BFG",
   special_index=3/HP-Revival, grind=99) → showed `BFG` + garbage `?`
   characters in-game, could not equip.
2. `data1=007603000000000000000000` (same class+special_index=3, name field
   fully zeroed this time) → **STILL** showed `?` garbage and could not equip.
   This ruled out the name-encoding as the cause, since the name field was now
   byte-identical to a working item's blank pattern.
3. `data1=007600000000000000000000` (same class, special_index=0, name blank)
   → **worked correctly**, displayed the plain type name "RIFLE", equippable.

Conclusion: **`data1[2]` must be `0x00` for S-rank weapons — it is NOT a
per-instance special-attack index in practice.** The real client evidently
looks up `(data1[1], data1[2])` against its item table to identify/validate the
item (matching what `PMT_BY_CATEGORY_CLASS_VARIANT` in `item_database.py`
encodes); no PMT entry exists for e.g. `(0x76, 0x03)`, only `(0x76, 0x00)`, so a
nonzero `data1[2]` makes the client treat the whole item as an unrecognized
variant (hence the "?" name AND the equip block — both symptoms share this one
root cause). **Do not use `data1[2]` to encode an S-rank special attack.** How
S-rank weapons legitimately get a special attack in the real game (if not via
this byte) is still unknown — possibly `data1[4]` (the normal weapons' special
byte) works the same way for S-rank weapons; this was NOT yet tested. Until
tested and confirmed, treat S-rank specials as unsupported; `psovmu/items.py`'s
`build_srank_weapon` now hardcodes `special_index=0` regardless of caller input,
and the GUI's S-rank special dropdown is locked to "(none)".

**Follow-up test (confirmed working): the custom-name encoding itself was
NEVER broken.** With `data1[2]=0x00` fixed, a 4th test item
(`data1=0076000000008285ce8e85a5`, class 0x76, name="TESTNAME", special_index=0,
grind=0) displayed correctly in-game as **"TESTNAME RIFLE"** (custom name +
base type name shown together, matching `ItemNameIndex.cc`'s
`"(" + name + ")"` / non-hidden-type-name rendering path) and equipped without
issue. So: **the S_RANK_CHARS encoding algorithm in this doc is fully correct
and safe to use as originally written — the only actual bug was `data1[2]`
being (mis)used for a special-attack index.** `build_srank_weapon`'s name
parameter works correctly for any valid name; only `special_index` is
disabled/hardcoded to 0 pending a real special-attack mechanism (candidate:
`data1[4]`, untested).

A weapon can have EITHER a custom S-rank name OR percentage attributes, never both —
they share the same bytes. S-rank weapons have no grind bonus display and (per this
session) real legit modifier caps don't apply the same way as normal items.

#### Armor / Shields (`data1[0]=1, data1[1]=1` for armor, `=2` for shields)
```
data1[2] = item variant
data1[5] = unit slot count (0-4) — ONLY MEANINGFUL for Armor; shields structurally have
           the same byte position but slots aren't a real game mechanic for shields
           (setting it is harmless either way)
data1w[3] (bytes 6-7, signed 16-bit) = DEF bonus
data1w[4] (bytes 8-9, signed 16-bit) = EVP bonus (armor) — for shields this may double
           as EVP too; validated only for the bonus semantics, both fields exist
           identically in the byte layout for armor and shields
```
"Legit maxed" DEF/EVP bonus for a given armor/shield = that item's `dfpRange`/
`evpRange` value from the parameter table, used **directly** (not `range-1`) —
validated against a real already-maxed item in the user's save (GUARD WAVE showed
DEF bonus=50 exactly equal to its `dfpRange`=50).

#### Units (`data1[0]=1, data1[1]=3`)
```
data1[2] = item variant
data1w[3] (bytes 6-7, signed 16-bit) = modifier (+/- tier)
```
Display rule (from `ItemNameIndex.cc`): modifier 1-2 shows "+", modifier ≥3 shows "++",
-1/-2 shows "-", ≤-3 shows "--". **BUT the real legitimate in-game cap via normal
combining is exactly `modifier = ±2`** (confirmed via a real wiki example: Ogre/Power
15 ATP → 17 ATP for "++", a +2 swing) — do NOT set arbitrarily large modifier values
thinking "higher is better", that's not how the mechanic actually caps.
Actual effective stat bonus = `StatAmount + modifier * ModifierAmount`, where both
`StatAmount` and `ModifierAmount` are fixed per-unit-type values from the item
parameter table (`ModifierAmount` is 0 for many "utility" units like HP/Revival,
PB/Generate, God/Technique, God/Battle etc. — for those, the +/- modifier has **zero
effect** on the actual bonus, so leave modifier at 0 for those rather than cosmetically
tagging them "++" for no real benefit).

#### Mags (`data1[0]=2`)
The real on-disk V2 mag format IS the bit-packed one (unlike tech disks/weapon-kind,
this one is genuinely necessary — validated byte-for-byte against a real level-200 mag
already in the user's save). Full validated encode:
```python
def build_mag_item_bytes(species_id, def_l, pow_l, dex_l, mind_l, synchro, iq, color,
                          pb_center, pb_right, pb_left):
    # def_l+pow_l+dex_l+mind_l should sum to the mag's level (max legit total = 200)
    def_raw, pow_raw, dex_raw, mind_raw = def_l*100, pow_l*100, dex_l*100, mind_l*100
    has_center, has_right, has_left = pb_center is not None, pb_right is not None, pb_left is not None
    pb_nums = 0
    if has_center: pb_nums |= (pb_center & 0x07)
    if has_right:  pb_nums |= ((pb_right & 0x07) << 3)
    if has_left:   pb_nums |= ((pb_left & 0x03) << 6)
    def_w  = (def_raw  & 0x7FFE) | ((1 if has_right else 0) << 15) | (color & 1)
    pow_w  = (pow_raw  & 0x7FFE) | ((1 if has_left  else 0) << 15) | ((color >> 1) & 1)
    dex_w  = (dex_raw  & 0xFFFE) | ((color >> 2) & 1)
    mind_w = (mind_raw & 0xFFFE) | ((color >> 3) & 1)
    # data1[0]=0x02, data1[1]=species_id, data1[2]=200 (level byte), data1[3]=pb_nums
    # data1[4:6]=def_w, data1[6:8]=pow_w, data1[8:10]=dex_w, data1[10:12]=mind_w  (all LE u16)
    # data2[0:2] = iq (LE u16), data2[2:4] = synchro | (has_center<<15)  (LE u16)
```
Photon blast numbers 0-5 = Farlla, Estlla, Golla, Pilla, Leilla, Mylla&Youlla.
Mag species IDs 0-57 (58 total in V2) come from `system/tables/mag-metadata-table-v2.json`
and the `02XX` keys in `item-parameter-table-pc-v2.json` (DC v2 table is a symlink to
this one on GitHub — fetch the PC v2 file, not the DC v2 path directly, which returns a
redirect stub). Max legit mag level = 200 total (sum of all 4 stats /100), synchro cap
120, IQ cap 200.

#### Technique disks (`data1[0]=3, data1[1]=2`)
```
data1[2] = (displayed_level - 1)   <-- DIRECT encoding, NOT the network overflow trick
data1[3] = 0
data1[4] = technique ID (0-18)
```
Technique ID order (validated against real cost data in the parameter table):
`0=Foie 1=Gifoie 2=Rafoie 3=Barta 4=Gibarta 5=Rabarta 6=Zonde 7=Gizonde 8=Razonde
9=Resta 10=Anti 11=Reverser 12=Shifta 13=Deband 14=Ryuker 15=Megid 16=Jellen
17=Zalure 18=Grants`. Ryuker/Reverser have `MaxTechLevel=0` for every class in the
real parameter table — i.e. they aren't normally levelable by any class; a disk can
still be created at any level byte-wise but it may not function as expected level-wise
in actual gameplay.

### "Parts" (`data1[0]=3`, special quest items — badges/enemy parts category)

There is NO real "badge" item in vanilla PSO V2 (Bronze/Silver/Gold/Crystal Weapon
Badges etc. are Blue Burst/later-era additions, confirmed absent from the real
`item-parameter-table-pc-v2.json`). What the user meant by "badges and enemy parts" is
actually PSO V2's real internal **special quest item** category: every item in the
parameter table with `ItemFlags == 250` lives at keys `030D00`-`030D08` (9 items,
"enemy parts" proper — obtained from monsters, traded to Dr. Montague in an offline
quest to craft the corresponding enemy-derived weapon, e.g. `030D04` "C-bringer's Right
Arm" → the weapon `C-BRINGER'S RIFLE`) and `030E00`-`030E24` (37 more: hearts/stones/
"Kit of [console]" easter-egg items/technique amplifiers used in various side quests
like Central Dome Fire Swirl and Soul of Steel). **46 items total, confirmed real for
V2** by their presence in the real parameter table (cross-checked against a comprehensive
BB item-ID list at `https://raw.githubusercontent.com/waytim/psobb/master/bb_items.txt`
— NOTE that list is for Blue Burst and includes many later-era items not in V2, so
always cross-reference candidate hex codes against the real `item-parameter-table-
pc-v2.json` `Items` dict before trusting a BB-era name/ID pairing). Byte layout is
minimal: `data1[0]=0x03, data1[1]=<from key>, data1[2]=<from key>`, rest zero — no
grind/attributes/stack size fields appear to apply to this item subtype.
Exact display names for `030E1B`-`030E24` (9-10 technique-amplifier-looking entries)
weren't confidently sourced — the BB item list only had generic "AMP." placeholders
for those specific slots — but the item codes themselves are confirmed valid/real for
V2 regardless of the exact label; the game's own text lookup will render whatever the
correct in-game name is regardless of what label we used in our own notes.

**GOTCHA (session 4): the names above were WRONG for most of `030D06`-`030E24`.**
A much better source was found: `system/tables/names-v2.json` in
`fuzziqersoftware/newserv` — explicitly "a convenient reference for item codes",
keyed the same way as the parameter table (6-hex `data1[0..2]`) but with the
actual display name as the value, for EVERY item category including Tools
(`0300`-`0C05`) and Parts (`0D00`-`0E24`), not just weapons/armor/shields/units.
This is a better source than the BB item-ID list previously used for Parts names
(which caused the misalignment) — prefer `names-v2.json` over that BB list going
forward. It also contradicted this doc's earlier claim (based on the BB list +
`ItemFlags==250` filtering) that no real "badge" item exists in V2, by listing
`030E07`-`030E0E` as "Weapons Bronze/Silver/Gold/Crystal/Steel/Aluminum/Leather/
Bone Badge" — **CONFIRMED via real gameplay test (session 4)**: built a "Weapons
Bronze Badge" (`030E07`) with this tool and loaded it in Flycast — displayed with
its correct name and could be traded normally, behaving as a fully valid item.
The earlier `ItemFlags==250` heuristic was wrong (or measuring something other
than "is this a real obtainable V2 item"); trust `names-v2.json` over it.

**New "Tools" category added (session 4)**: `data1[0]=3`, plain 2-byte kind/variant
in `data1[1..2]`, rest zero except `data1[5]` = stack amount for STACKABLE items
only (Mates/Fluids/Atomizers/Antidote/Antiparalysis/Telepipe/Trap Vision/Scape
Doll) — Grinders/Materials/Cells are single-instance (data1[5] left at 0). Full
list of 31 items and their codes: see `psovmu/item_database.py`'s `TOOLS`. Found
via a real save file where 4 bank slots (3× Scape Doll `0309`, 1× Monogrinder
`030A`) were showing as "Unknown item" — this whole category had been overlooked
in earlier sessions, which only covered Tech Disks and Parts under `data1[0]=3`.
**Bank-slot gotcha**: bank items store their stack count in the wrapper's own
`amount` field (`ItemData(20) + amount(u16) + present(u16)`, per section 7 above),
NOT in `data1[5]` — `data1[5]` is only meaningful for INVENTORY tool items, which
have no such wrapper. Confirmed via a real save: a bank-stored Scape Doll had
`data1[5]=0x00` but the wrapper `amount=1` (matching there being exactly one
usable doll in that slot) — displaying `data1[5]` directly for a bank item would
have wrongly shown "x0".

---

## 8. Star ratings and the real item parameter tables

Real weapon/armor/shield/unit/mag data (names, stats, star ratings) — do NOT guess
these from item names. Sources used this session, in order of how they were used:

1. **`fuzziqersoftware/newserv`** GitHub repo — the single best source for structs,
   encryption, and raw parameter tables:
   - `src/SaveFileFormats.hh/.cc`, `src/PlayerSubordinates.hh`, `src/PlayerInventory.hh`,
     `src/ItemData.hh/.cc`, `src/ItemParameterTable.hh/.cc`, `src/LevelTable.hh`,
     `src/PSOEncryption.hh/.cc`, `src/ItemNameIndex.cc` — all fetched via
     `https://raw.githubusercontent.com/fuzziqersoftware/newserv/master/<path>`
   - `system/tables/level-table-v1-v2.json` — level-up stat curves per class
   - `system/tables/item-parameter-table-pc-v2.json` — the REAL item stat table
     (`Items` dict keyed by 6-hex-digit `data1[0..2]`, plus `StarValues`/
     `StarValueBaseIndex` for star ratings: `stars = StarValues[item.ID - StarValueBaseIndex]`)
     — NOTE this file is JSONC (has `//` comments) and uses `0xNN` hex literals, neither
     of which `json.loads` handles; strip comments (respecting string literals) and
     regex-replace `0x[0-9A-Fa-f]+` with its decimal value before parsing.
     Also note: `item-parameter-table-dc-v2.json` on GitHub is literally just a text
     file containing the string `item-parameter-table-pc-v2.json` (a "symlink" that
     GitHub's raw server returns as plain text, not an actual redirect) — fetch the
     PC v2 file directly, don't be confused by a 31-byte response.
   - `system/tables/mag-metadata-table-v2.json` — mag species animation data (58 species)
   - `notes/quest-flags.txt` — quest/story flag ID reference

2. **`https://amon-x.github.io/psoitems/data/v2.json`** — a pre-parsed, ready-to-use
   JSON with `name`, `stars`, `index` (=item ID), and full stat fields for every
   weapon/armor/shield/unit/mag, sourced by that site from the real client PMT data via
   WASM parsing. Much less effort than parsing the raw PMT JSON by hand for
   name/star/stat lookups. Cross-reference `index` (=ID) against the newserv PMT's
   `Items` dict to get the actual `data1[1]/[2]` bytes for constructing items.
   (The site's HTML page itself blocks non-browser User-Agents — fetch with
   `curl -A "Mozilla/5.0 ..."`, not WebFetch, or fetch `data/v2.json` directly which
   doesn't have that restriction.)

3. **The real `WeaponKind` field** in the newserv PMT (`Items[key]['WeaponKind']`) is
   the authoritative weapon category (1=Saber 2=Sword 3=Dagger 4=Partisan 5=Slicer
   6=Handgun 7=Rifle 8=Mechgun 9=Shot 10=Cane 11=Rod 12=Wand 13=Claw
   14=DoubleSaber/Twin, 0=Knuckle/unarmed) — **use this, not the item's flavor name**,
   to classify "which category does this weapon belong to." Many named unique/rare
   weapons with silly flavor names (AKIKO'S FRYING PAN, TOY HAMMER, HARISEN BATTLE FAN,
   S-RANK SCYTHE/HAMMER/HARISEN) turn out to mechanically be Saber/Partisan/Slicer-kind
   under the hood — the flavor name lies, `WeaponKind` doesn't.

---

## 9. General workflow checklist for a new VMU save-editing request

1. Read the VMU directory (section 1) — find the actual `PSO______SYS` file and its
   real start block. Don't assume block 199 or reuse a block number from a different
   VMU file.
2. Decrypt with `decrypt_fixed`, verify checksum matches, before touching anything.
3. Read `char_class` (offset `disp_base+0x24+0x10+0x21`) before doing any level/stat
   math — different characters in this account are different classes (RAmar, RAcast
   seen so far), and the level table numbers differ significantly per class.
4. For "max out this character" style requests: compute EXP/stats from the real level
   table (section 5), preserving Material bonuses rather than blindly setting to
   MaxStats. Remember stored level = displayed level - 1.
5. For item requests (mags/weapons/armor/shields/units/tech disks): get the real item
   list + stats from source #2 above (section 8), cross-reference against the newserv
   PMT for exact byte codes, and use the validated encoders in section 7.
6. Before writing ANY new item-encoding scheme for the first time, look for an existing
   real item of that same type already in the target save file (or a sibling save on
   the same account) and decode it with your candidate formula — if it doesn't produce
   sane values, the formula (or byte offsets) is wrong. This caught real bugs this
   session (tech disk level encoding).
7. Always do the full round-trip verification (section 3) before writing to disk.
8. Write the modified blocks back into the full 256-block VMU image (don't just write
   the extracted file_bytes — you must splice back into the block-chain positions in
   the original 131072-byte image) and save.
9. Re-read the file FRESH from disk afterward and decode again as a final independent
   check — don't trust in-memory state from the write step.
10. If the user reports something displaying wrong in-game after you were sure the
    math was right (e.g. the tech-disk level-30-shows-as-15 bug, or the
    level-200-shows-as-201 bug), that's a real signal to re-derive the encoding rather
    than assume the emulator/game is being flaky — both those bugs turned out to be
    genuine encoding mistakes on the save-editing side.

---

## 10. Extracting the full item catalog straight from a real GD-ROM image

This session replaced the hand-curated "8-star+ weapons / 9-star+ armor" lists in
`psovmu/item_database.py` with the complete V2 catalog (every weapon/armor/shield/unit,
206 weapons total including a whole missing Knuckle category, 53 armors, 58 shields,
68 units) by extracting and parsing the actual disc's own `ITEMPMT.PRS`, then
cross-referencing it against community sources for names. Full pipeline, in case a
future session needs to pull something else off a PSO disc image (a different table,
a different version, etc.):

### 10.1 DiscJuggler `.cdi` → raw ISO9660 image

A `.cdi` (DiscJuggler) GD-ROM rip stores session/track **metadata near the END of the
file**, while the actual raw sector data for every track is laid out sequentially
starting from **absolute file offset 0** — track data comes first in the file, its
descriptor comes much later. Parsing algorithm (ported from `cdirip` by DeXT/Lawrence
Williams, `github.com/jozip/cdirip`, `cdi.c`/`cdirip.c`):

1. Read the last 8 bytes of the file: `[version:u32][header_offset:u32]`. Version
   `0x80000006` = DiscJuggler v3.5+ (what this session's `Ragol_PSO_USv2.cdi` was) —
   for that version, the session/track table lives at `file_length - header_offset`;
   for v2/v3 it's just `header_offset` (absolute).
2. At that position: `sessions:u16`, then per session `tracks:u16`, then per track a
   variable-length descriptor (filename, pregap, length, mode, sector_size, etc. — see
   the full field list in `CDI_read_track` in the fetched `cdi.c`/`cdirip.c`, or ask a
   fresh session to re-fetch from that repo).
3. **Track data position is NOT derivable from the descriptor itself** — it's a
   running total: track 1's data starts at file offset 0; each subsequent track's data
   starts at `previous_track_data_offset + previous_track.total_length * sector_size`.
   This tripped up the first attempt (assumed the position right after reading a
   track's descriptor was that track's data — it's actually the position of the *next
   track's descriptor*, since all descriptors are bunched together near the end).
4. This PSO V2 disc had 2 sessions: session 0 (1 audio track, low-density CD area,
   mode=0/Audio/2352-byte sectors, ignorable) and session 1 (1 data track, the GD-ROM
   high-density area — `mode=2`/`sector_size=2336`, `pregap=150`, `length=346440`
   sectors, `start_lba=11702`). To extract as a plain ISO: skip `pregap * sector_size`
   bytes, then for each of `length` sectors read `sector_size` bytes and keep only
   `sector[8:8+2048]` (mode2/2336 sectors have an 8-byte subheader before the 2048
   bytes of real data; discard the trailing ~280 bytes of EDC/ECC per sector too).
5. **Gotcha**: LBA values *stored inside* the resulting ISO9660 filesystem (root
   directory extent, path table location, every directory record's extent) are
   **absolute physical CD sector numbers** (`track.start_lba` + a track-relative
   offset), NOT relative to byte 0 of the extracted image — even though the ISO9660
   PVD (Primary Volume Descriptor) itself sits at the *conventional* relative sector
   16. Subtract `track.start_lba` (11702 for this disc) from every LBA field read out
   of the filesystem before using it to index into the extracted image. Validated by
   finding "CD001" at the conventional sector 16 (confirming overall byte alignment),
   then confirming the root directory only had real content once this offset was
   subtracted from its extent field.
6. `pycdlib` (pip) choked on this disc's path table (a real parsing bug in that
   library for this specific format quirk, not a mistake in the extraction) — wrote a
   ~60-line minimal ISO9660 directory-record walker instead (root dir extent from PVD
   offset `156`, then recursively parse 34-byte directory records: `length`,
   `extent_lba` @ offset 2 (u32 LE), `size` @ offset 10, `flags` @ offset 25 (bit
   0x02 = directory), `name_len` @ offset 32, name follows). Don't burn time on
   `pycdlib` for a DC disc again without checking this note first.
7. `PSO/TEXTENGLISH.PR2`/`.PR3` (the DC equivalent of "unitxt") turned out to use a
   **different, still-undetermined compression** — NOT the standard PRS algorithm
   below (confirmed: that decoder works perfectly on `ITEMPMT.PRS` from the same disc,
   but fails within the first few dozen bytes on `TEXTENGLISH.PR2` at every tried byte
   offset). Cracking it would need disassembling the game executable. Not pursued
   this session — item names instead come from newserv's `names-v2.json` (see 10.3).

### 10.2 PRS decompression (works for `ITEMPMT.PRS`, NOT for `TEXTENGLISH.PR2`/`.PR3`)

Ported byte-for-byte from `fuzziqersoftware/newserv`'s `src/Compression.cc`
(`prs_decompress_with_meta`). LZ77 with an interleaved control-bit + data-byte stream,
read from the SAME byte sequence (control bits refill from the next unread byte when
exhausted — there's no separate "control stream" region in the file).

```python
def prs_decompress(data: bytes) -> bytes:
    out = bytearray()
    pos = 0
    n = len(data)
    bits = 0

    def get_u8():
        nonlocal pos
        b = data[pos]; pos += 1
        return b

    def read_bit():
        nonlocal bits
        if not (bits & 0x100):
            bits = 0xFF00 | get_u8()
        ret = bits & 1
        bits >>= 1
        return ret

    try:
        while pos < n:
            if read_bit():                      # control 1 = literal byte
                out.append(get_u8())
            else:
                if read_bit():                   # control 01 = long backreference
                    a = get_u8(); a |= get_u8() << 8
                    off = a >> 3
                    if off == 0:
                        break                     # all-zero offset = stop opcode
                    offset = off - 0x2000          # 13-bit signed, always negative
                    count = a & 7
                    count = count + 2 if count else get_u8() + 1  # extended backref
                else:                             # control 00 = short backreference
                    count = read_bit() << 1
                    count = (count | read_bit()) + 2
                    offset = get_u8() - 0x100      # 8-bit signed, always negative
                read_off = len(out) + offset
                for _ in range(count):             # byte-at-a-time copy (supports
                    out.append(out[read_off])       # overlapping/self-referential runs)
                    read_off += 1
    except IndexError:
        pass  # ran off the end mid-opcode -- treat as a truncated/unterminated stream
    return bytes(out)
```

Validated: `ITEMPMT.PRS` (8776 bytes) → 24928 bytes, decoded structure matched
newserv's documented `RootV2` struct offsets exactly (see 10.3), and decoded armor
stats matched known real PSO armor progression (Frame id=354 dfp=5→Ultimate Frame
dfp climbing to 25, req_level climbing 0→15 in step).

### 10.3 `ITEMPMT.PRS` structure (decompressed payload)

Root struct (`RootV2` in newserv's `ItemParameterTable.cc`) is `0x44` bytes, found by
searching the decompressed buffer for the byte sequence matching the *expected*
`armor_table` field value (`0x5A5C`, hardcoded in newserv's source comments for the
V2 version specifically) — landed at decompressed-file offset `24428` for this disc
(near the very end of the 24928-byte payload; all the actual item data sits *before*
the root header, mirroring the outer `.cdi` file's own "data first, metadata last"
layout). All 17 fields (`entry_count`, `weapon_table`, `armor_table`, `unit_table`,
`tool_table`, `mag_table`, plus 11 more auxiliary tables) matched newserv's documented
V2 offsets exactly, confirming both the PRS decode and the struct layout.

Each `*_table` root field points to an `ArrayRefT` (`{count: u32, offset: u32}`, 8
bytes) — for `armor_table` there are **two** consecutive `ArrayRefT`s at that location
(index 0 = Armor, `count=53`; index 1 = Shield, `count=58` — both counts matched this
session's independently-generated community-sourced catalog exactly). `weapon_table`
points to an array of **one `ArrayRefT` per weapon class byte** (`data1[1]`, e.g. index
6 = Handgun), each giving the `count`/`offset` of that class's variant array.
`unit_table`/`tool_table`/`mag_table` are single `ArrayRefT`s (`count=68`/`3`/`57` for
this disc). Item entry structs (`WeaponV1V2`=0x18 bytes, `ArmorOrShieldV1V2`=0x18,
`UnitV1V2`=0x0C, `MagV2`=0x14, `ToolV1V2`=0x10 — exact field layouts in newserv's
`ItemParameterTable.cc`, search for `V1V2`) do **not** store `data1[1]`/`data1[2]`
as explicit fields — those are implied by the entry's position in the nested
array structure, same as the community JSON's key scheme (`data1[0]data1[1]data1[2]`
as 6 hex chars).

Didn't fully hand-decode the nested weapon array (137 classes × several variants each,
plus S-rank special-casing) since newserv's own pre-parsed
`item-parameter-table-pc-v2.json` already does this correctly and its counts/values
were cross-validated against this disc's raw armor data — no reason to duplicate that
work byte-for-byte. If a future session needs to re-derive it from scratch anyway
(e.g. to catch a case where the community JSON might be wrong), the struct offsets
above are the starting point.

### 10.4 Building the full catalog from community sources, cross-checked against the disc

Sources (same ones already used for the curated lists, see section 8 above):
- `system/tables/item-parameter-table-pc-v2.json` (fuzziqersoftware/newserv) — real
  stats, `StarValues`/`StarValueBaseIndex` for star ratings (`stars =
  StarValues[entry["ID"] - StarValueBaseIndex]`), keyed by 6-hex `data1[0..2]`.
- `system/tables/names-v2.json` (same repo) — real display names, same key scheme.
- Weapon category (Guns/Swords/Wands tab in the GUI) comes from the PMT's
  `WeaponKind` field: `{1,2,3,4,5,13,14,0}` (Saber/Sword/Dagger/Partisan/Slicer/
  Claw/DoubleSaber/Knuckle) → Swords tab; `{6,7,8,9}` (Handgun/Rifle/Mechgun/Shot) →
  Guns tab; `{10,11,12}` (Cane/Rod/Wand) → Wands tab.
- S-rank weapon classes (`data1[1]` in `0x70-0x88` or `0xA5-0xA9`) are excluded from
  the generated lists — they're handled separately by the existing `GUN_SRANK`/
  `SWORD_SRANK`/`WAND_SRANK` name-encoding logic (see section 7), which was already
  validated against real gameplay in an earlier session and shouldn't be touched.
- Of 570 total PMT entries, only 5 had no name in `names-v2.json` — all shared
  `ID=353` (or `ID=78` for weapon class/variant `00/00`, i.e. bare fists), a
  consistent "empty/invalid slot" sentinel used across every category. Safe to skip.

**Gotcha: duplicate display names.** The client's own text table gives several
distinct items the *exact same* display string — most notably all 7 AGITO variants
(`data1[1]=0x10`, variants 1-6, plus OROTIAGITO at variant 0) are simply named
"AGITO" with no distinguishing suffix in the real game text (the old curated list's
"AGITO (AUW 1975)" etc. suffixes were a community/wiki convention, not in-game text).
Any UI that resolves a user's dropdown selection back to a specific item via
`display_list.index(chosen_string)` will silently and permanently only let the user
pick the FIRST of several identically-labeled entries — this was a real bug introduced
by moving from the (all-unique-named) curated subset to the full catalog, caught by
building the item list, diffing against `Counter`, and specifically probing whether
every AGITO variant round-tripped to a distinct `(class, variant)` pair through the
actual GUI dialog code (not just at the data-list level) before calling it done. Fixed
generically in `item_database.py` via `weapon_labels()`/`item_labels()`, which append
a `" [i/n]"` disambiguator to any repeated label — `main.py`'s six weapon/armor/unit
label-list call sites all now go through those two functions (and cache the result on
the dialog instance) instead of rebuilding an ad-hoc `f"{n} ({s}*)"` list inline,
which is what made the collision unresolvable in the first place.

**Unrelated pre-existing bug found (and fixed) while touching this code**: the
bundled `data/item-parameter-table-pc-v2-reduced.json`'s Unit entries have
`"UsabilityFlags": null` for every unit (units genuinely have no such field in the
real on-disk struct — confirmed in 10.3 above — so there's nothing to reduce down to;
whoever generated that file defaulted the missing field to `null` rather than
omitting it). `check_equip()` did `entry["UsabilityFlags"] & char_bits` unconditionally,
which crashed with a `TypeError` on `None & int` — meaning the Unit tab's "who can use
this" label has been crashing since it was added, for every unit, in every session
before this one (no test exercised it — the existing pytest suite is data-round-trip
only, not GUI interaction). Fixed by treating `None` as "usable by everyone" instead
of indexing into it. If future PMT-driven equip-checks add new item categories, check
whether their reduced-JSON entries have real data before trusting a bare `entry[key]`.

**Verification approach used**: rather than trust "the data list is correct" as the
finish line, wrote a headless Tk smoke test that instantiates the actual
`AddItemDialog` (no visible window, `root.withdraw()`), cycles through all 10
categories, and for the collision-prone ones (weapons generally, AGITO specifically)
drives the real `_resolve_weapon_class_variant`/`_confirm_*` code paths end-to-end
and asserts every differently-labeled item resolves to a distinct `(class, variant)`.
This is what caught the label-collision bug above — the underlying Python list of
tuples looked completely fine in isolation; the bug only showed up in how the GUI
maps a display string back to a row.
