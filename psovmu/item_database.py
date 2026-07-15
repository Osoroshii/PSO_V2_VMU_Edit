"""The full V2 item catalog: every real weapon/armor/shield/unit, all 58 mag
species, all 19 techniques, and the 46 real "Parts" quest items.

GUNS/SWORDS/WANDS/ARMOR/SHIELDS/UNITS were generated from this disc's own
ITEMPMT.PRS (extracted and PRS-decompressed straight from a real V2 GD-ROM
image, cross-checked byte-for-byte against fuzziqersoftware/newserv's
documented RootV2 struct offsets and against a real character's armor bank --
see /Volumes/MacEMU/bios/dc/PSO Saves/ClaudeVMUWork/ for the extraction
writeup) with names from newserv's names-v2.json (the client's own item text
index) and stats/star ratings from item-parameter-table-pc-v2.json. A handful
of items share an identical in-game display name (e.g. all 7 AGITO variants);
see item_labels()/weapon_labels() below for how the GUI disambiguates them.

Each entry: (display_name, stars_or_None, class_byte, variant_byte)
"""
import json
import os
from collections import Counter

GUNS = [
    ("Handgun", 0, 0x6, 0x0), ("Autogun", 1, 0x6, 0x1), ("Lockgun", 2, 0x6, 0x2),
    ("Railgun", 3, 0x6, 0x3), ("Raygun", 4, 0x6, 0x4), ("VARISTA", 9, 0x6, 0x5),
    ("CUSTOM RAY ver.OO", 9, 0x6, 0x6), ("BRAVACE", 9, 0x6, 0x7),
    ("Rifle", 1, 0x7, 0x0), ("Sniper", 2, 0x7, 0x1), ("Blaster", 3, 0x7, 0x2),
    ("Beam", 4, 0x7, 0x3), ("Laser", 5, 0x7, 0x4), ("VISK-235W", 9, 0x7, 0x5),
    ("WALS-MK2", 9, 0x7, 0x6), ("JUSTY-23ST", 9, 0x7, 0x7),
    ("Mechgun", 1, 0x8, 0x0), ("Assault", 2, 0x8, 0x1), ("Repeater", 3, 0x8, 0x2),
    ("Gatling", 4, 0x8, 0x3), ("Vulcan", 5, 0x8, 0x4), ("M&A60 VISE", 9, 0x8, 0x5),
    ("H&S25 JUSTICE", 9, 0x8, 0x6), ("L&K14 COMBAT", 9, 0x8, 0x7),
    ("Shot", 1, 0x9, 0x0), ("Spread", 2, 0x9, 0x1), ("Cannon", 3, 0x9, 0x2),
    ("Launcher", 4, 0x9, 0x3), ("Arms", 5, 0x9, 0x4), ("CRUSH BULLET", 9, 0x9, 0x5),
    ("METEOR SMASH", 9, 0x9, 0x6), ("FINAL IMPACT", 9, 0x9, 0x7),
    ("SPREAD NEEDLE", 11, 0x12, 0x0), ("HOLY RAY", 11, 0x13, 0x0), ("INFERNO BAZOOKA", 11, 0x14, 0x0),
    ("FLAME VISIT", 11, 0x15, 0x0), ("C-BRINGER'S RIFLE", 12, 0x1b, 0x0), ("EGG BLASTER", 10, 0x1c, 0x0),
    ("HEAVEN PUNISHER", 12, 0x1e, 0x0), ("SUPPRESSED GUN", 9, 0x26, 0x0),
    ("HANDGUN:GULD", 12, 0x42, 0x0), ("HANDGUN:MILLA", 12, 0x43, 0x0), ("RED HANDGUN", 9, 0x44, 0x0),
    ("FROZEN SHOOTER", 11, 0x45, 0x0), ("ANTI ANDROID RIFLE", 11, 0x46, 0x0), ("ROCKET PUNCH", 12, 0x47, 0x0),
    ("SAMBA MARACAS", 11, 0x48, 0x0), ("TWIN PSYCHOGUN", 11, 0x49, 0x0),
    ("DRILL LAUNCHER", 11, 0x4a, 0x0), ("GULD MILLA", 12, 0x4b, 0x0), ("RED MECHGUN", 9, 0x4c, 0x0),
    ("BERLA CANNON", 12, 0x4d, 0x0), ("PANZER FAUST", 12, 0x4e, 0x0),
    ("YASMINKOV 3000R", 10, 0x65, 0x0), ("ANO RIFLE", 12, 0x66, 0x0), ("BARANZ LAUNCHER", 12, 0x67, 0x0),
    ("YASMINKOV 2000H", 10, 0x6a, 0x0),
    ("YASMINKOV 7000V", 11, 0x6b, 0x0), ("YASMINKOV 9200M", 10, 0x6c, 0x0), ("MASER BEAM", 12, 0x6d, 0x0),
]
GUN_SRANK = [(0x75, "S-RANK GUN"), (0x76, "S-RANK RIFLE"), (0x77, "S-RANK MECHGUN"),
             (0x78, "S-RANK SHOT"), (0x7e, "S-RANK BAZOOKA"), (0x7f, "S-RANK NEEDLE"),
             (0x83, "S-RANK PSYCHOGUN")]

SWORDS = [
    ("Saber", 0, 0x1, 0x0), ("Brand", 1, 0x1, 0x1), ("Buster", 2, 0x1, 0x2), ("Pallasch", 3, 0x1, 0x3),
    ("Gladius", 4, 0x1, 0x4), ("DB'S SABER", 9, 0x1, 0x5), ("KALADBOLG", 9, 0x1, 0x6), ("DURANDAL", 9, 0x1, 0x7),
    ("Sword", 1, 0x2, 0x0), ("Gigush", 2, 0x2, 0x1), ("Breaker", 3, 0x2, 0x2), ("Claymore", 4, 0x2, 0x3),
    ("Calibur", 5, 0x2, 0x4), ("FLOWEN'S SWORD", 9, 0x2, 0x5), ("LAST SURVIVOR", 9, 0x2, 0x6), ("DRAGON SLAYER", 9, 0x2, 0x7),
    ("Dagger", 1, 0x3, 0x0), ("Knife", 2, 0x3, 0x1), ("Blade", 3, 0x3, 0x2), ("Edge", 4, 0x3, 0x3),
    ("Ripper", 5, 0x3, 0x4), ("BLADE DANCE", 9, 0x3, 0x5), ("BLOODY ART", 9, 0x3, 0x6), ("CROSS SCAR", 9, 0x3, 0x7),
    ("Partisan", 1, 0x4, 0x0), ("Halbert", 2, 0x4, 0x1), ("Glaive", 3, 0x4, 0x2), ("Berdys", 4, 0x4, 0x3),
    ("Gungnir", 5, 0x4, 0x4), ("BRIONAC", 9, 0x4, 0x5), ("VJAYA", 9, 0x4, 0x6), ("GAE BOLG", 9, 0x4, 0x7),
    ("Slicer", 1, 0x5, 0x0), ("Spinner", 2, 0x5, 0x1), ("Cutter", 3, 0x5, 0x2), ("Sawcer", 4, 0x5, 0x3),
    ("Diska", 5, 0x5, 0x4), ("SLICER OF ASSASSIN", 9, 0x5, 0x5), ("DISKA OF LIBERATOR", 9, 0x5, 0x6), ("DISKA OF BRAVEMAN", 9, 0x5, 0x7),
    ("PHOTON CLAW", 9, 0xd, 0x0), ("SILENCE CLAW", 10, 0xd, 0x1), ("NEI'S CLAW", 10, 0xd, 0x2),
    ("DOUBLE SABER", 9, 0xe, 0x0), ("STAG CUTLERY", 10, 0xe, 0x1), ("TWIN BRAND", 11, 0xe, 0x2),
    ("BRAVE KNUCKLE", 9, 0xf, 0x0), ("ANGRY FIST", 10, 0xf, 0x1), ("GOD HAND", 11, 0xf, 0x2), ("SONIC KNUCKLE", 10, 0xf, 0x3),
    ("OROTIAGITO", 12, 0x10, 0x0), ("AGITO", 10, 0x10, 0x1), ("AGITO", 9, 0x10, 0x2),
    ("AGITO", 9, 0x10, 0x3), ("AGITO", 9, 0x10, 0x4), ("AGITO", 9, 0x10, 0x5),
    ("AGITO", 9, 0x10, 0x6),
    ("SOUL EATER", 10, 0x11, 0x0), ("SOUL BANISH", 11, 0x11, 0x1),
    ("AKIKO'S FRYING PAN", 10, 0x16, 0x0), ("S-BEAT'S BLADE", 11, 0x18, 0x0), ("P-ARMS'S BLADE", 11, 0x19, 0x0),
    ("DELSABER'S BUSTER", 11, 0x1a, 0x0), ("LAVIS CANNON", 12, 0x1f, 0x0), ("VICTOR AXE", 9, 0x20, 0x0), ("CHAIN SAWD", 11, 0x21, 0x0),
    ("STING TIP", 10, 0x23, 0x0), ("ANCIENT SABER", 10, 0x27, 0x0),
    ("HARISEN BATTLE FAN", 11, 0x28, 0x0), ("YAMIGARASU", 12, 0x29, 0x0), ("AKIKO'S WOK", 11, 0x2a, 0x0),
    ("TOY HAMMER", 11, 0x2b, 0x0), ("ELYSION", 11, 0x2c, 0x0), ("RED SABER", 9, 0x2d, 0x0),
    ("METEOR CUDGEL", 10, 0x2e, 0x0), ("MONKEY KING BAR", 12, 0x2f, 0x0), ("DOUBLE CANNON", 12, 0x30, 0x0),
    ("HUGE BATTLE FAN", 12, 0x31, 0x0), ("TSUMIKIRI J-SWORD", 12, 0x32, 0x0), ("SEALED J-SWORD", 10, 0x33, 0x0),
    ("RED SWORD", 9, 0x34, 0x0), ("CRAZY TUNE", 11, 0x35, 0x0), ("TWIN CHAKRAM", 10, 0x36, 0x0),
    ("WOK OF AKIKO'S SHOP", 11, 0x37, 0x0), ("LAVIS BLADE", 12, 0x38, 0x0), ("RED DAGGER", 9, 0x39, 0x0),
    ("MADAM'S PARASOL", 12, 0x3a, 0x0), ("MADAM'S UMBRELLA", 11, 0x3b, 0x0), ("IMPERIAL PICK", 10, 0x3c, 0x0),
    ("BERDYSH", 12, 0x3d, 0x0), ("RED PARTISAN", 9, 0x3e, 0x0), ("FLIGHT CUTTER", 12, 0x3f, 0x0),
    ("FLIGHT FAN", 11, 0x40, 0x0), ("RED SLICER", 9, 0x41, 0x0), ("TWIN BLAZE", 12, 0x5e, 0x0),
    ("DRAGON'S CLAW", 11, 0x60, 0x0), ("PANTHER'S CLAW", 11, 0x61, 0x0), ("S-RED'S BLADE", 12, 0x62, 0x0),
    ("PLANTAIN HUGE FAN", 12, 0x63, 0x0), ("CHAMELEON SCYTHE", 11, 0x64, 0x0), ("HEART OF POUMN", 12, 0x69, 0x0),
    ("FLOWER BOUQUET", 9, 0x6f, 0x0),
]
SWORD_SRANK = [(0x70, "SSABER"), (0x71, "SSWORD"), (0x72, "SBLADE"), (0x73, "SPARTISN"),
               (0x74, "SSLICER"), (0x7c, "STWIN"), (0x7d, "SCLAW"), (0x80, "SSCYTHE"),
               (0x81, "SHAMMER"), (0x86, "SHARISEN"), (0x87, "SJBLADE"), (0x88, "SJCUTTER")]

WANDS = [
    ("Cane", 0, 0xa, 0x0), ("Stick", 1, 0xa, 0x1), ("Mace", 2, 0xa, 0x2), ("Club", 3, 0xa, 0x3),
    ("CLUB OF LACONIUM", 9, 0xa, 0x4), ("MACE OF ADAMAN", 9, 0xa, 0x5), ("CLUB OF ZUMIURAN", 9, 0xa, 0x6),
    ("Rod", 1, 0xb, 0x0), ("Pole", 2, 0xb, 0x1), ("Pillar", 3, 0xb, 0x2), ("Striker", 4, 0xb, 0x3),
    ("BATTLE VERGE", 9, 0xb, 0x4), ("BRAVE HAMMER", 9, 0xb, 0x5), ("ALIVE AQHU", 9, 0xb, 0x6),
    ("Wand", 1, 0xc, 0x0), ("Staff", 2, 0xc, 0x1), ("Baton", 3, 0xc, 0x2), ("Scepter", 4, 0xc, 0x3),
    ("FIRE SCEPTER:AGNI", 9, 0xc, 0x4), ("ICE STAFF:DAGON", 9, 0xc, 0x5), ("STORM WAND:INDRA", 9, 0xc, 0x6),
    ("C-SORCERER'S CANE", 11, 0x17, 0x0), ("PSYCHO WAND", 12, 0x1d, 0x0), ("CADUCEUS", 11, 0x22, 0x0), ("MAGICAL PIECE", 11, 0x24, 0x0),
    ("TECHNICAL CROZIER", 10, 0x25, 0x0), ("SUMMIT MOON", 11, 0x4f, 0x0),
    ("WINDMILL", 12, 0x50, 0x0), ("EVIL CURST", 12, 0x51, 0x0), ("FLOWER CANE", 11, 0x52, 0x0),
    ("HILDEBEAR'S CANE", 10, 0x53, 0x0), ("HILDEBLUE'S CANE", 12, 0x54, 0x0), ("RABBIT WAND", 12, 0x55, 0x0),
    ("PLANTAIN LEAF", 10, 0x56, 0x0), ("DEMONIC FORK", 11, 0x57, 0x0), ("STRIKER OF CHAO", 12, 0x58, 0x0),
    ("BROOM", 10, 0x59, 0x0), ("PROPHETS OF MOTAV", 12, 0x5a, 0x0), ("THE SIGH OF A GOD", 11, 0x5b, 0x0),
    ("TWINKLE STAR", 11, 0x5c, 0x0), ("PLANTAIN FAN", 11, 0x5d, 0x0), ("MARINA'S BAG", 11, 0x5f, 0x0),
    ("BRANCH OF PAKUPAKU", 9, 0x68, 0x0), ("GAME MAGAZNE", 11, 0x6e, 0x0),
]
WAND_SRANK = [(0x79, "SCANE"), (0x7a, "SROD"), (0x7b, "SWAND"), (0x82, "SMOON"), (0x85, "SWINDMIL")]

# Armor: (name, stars, variant, max_dfp_bonus, max_evp_bonus)
ARMOR = [
    ("Frame", 0, 0x0, 2, 2), ("Armor", 0, 0x1, 2, 2), ("Psy Armor", 1, 0x2, 3, 2), ("Giga Frame", 1, 0x3, 4, 2),
    ("Soul Frame", 2, 0x4, 4, 2), ("Cross Armor", 2, 0x5, 4, 2), ("Solid Frame", 3, 0x6, 4, 2), ("Brave Armor", 3, 0x7, 4, 2),
    ("Hyper Frame", 4, 0x8, 4, 2), ("Grand Armor", 4, 0x9, 4, 2), ("Shock Frame", 5, 0xa, 4, 2), ("King's Frame", 5, 0xb, 4, 2),
    ("Dragon Frame", 6, 0xc, 4, 2), ("Absorb Armor", 6, 0xd, 4, 2), ("Protect Frame", 7, 0xe, 4, 2), ("General Armor", 7, 0xf, 4, 2),
    ("Perfect Frame", 7, 0x10, 4, 2), ("Valiant Frame", 7, 0x11, 4, 2), ("Imperial Armor", 8, 0x12, 4, 2), ("Holiness Armor", 8, 0x13, 4, 2),
    ("Guardian Armor", 9, 0x14, 4, 2), ("Divinity Armor", 10, 0x15, 4, 2), ("Ultimate Frame", 11, 0x16, 4, 2),
    ("Celestial Armor", 12, 0x17, 10, 10), ("HUNTER FIELD", 10, 0x18, 8, 8), ("RANGER FIELD", 10, 0x19, 8, 8),
    ("FORCE FIELD", 10, 0x1a, 8, 8), ("REVIVAL GARMENT", 11, 0x1b, 5, 10), ("SPIRIT GARMENT", 12, 0x1c, 7, 5),
    ("STINK FRAME", 9, 0x1d, 85, 85), ("D-PARTS ver1.01", 10, 0x1e, 10, 7), ("D-PARTS ver2.10", 11, 0x1f, 10, 8),
    ("PARASITE WEAR:De Rol", 9, 0x20, 0, 5), ("PARASITE WEAR:Nelgal", 11, 0x21, 0, 10), ("PARASITE WEAR:Vajulla", 12, 0x22, 0, 5),
    ("SENSE PLATE", 10, 0x23, 8, 8), ("GRAVITON PLATE", 10, 0x24, 8, 0), ("ATTRIBUTE PLATE", 10, 0x25, 8, 8),
    ("FLOWEN'S FRAME", 11, 0x26, 10, 10), ("CUSTOM FRAME ver.OO", 11, 0x27, 10, 10), ("DB'S ARMOR", 12, 0x28, 10, 10),
    ("GUARD WAVE", 11, 0x29, 50, 20), ("DF FIELD", 11, 0x2a, 50, 20), ("LUMINOUS FIELD", 11, 0x2b, 50, 20),
    ("CHU CHU FEVER", 12, 0x2c, 50, 20), ("LOVE HEART", 11, 0x2d, 50, 20), ("FLAME GARMENT", 11, 0x2e, 50, 20),
    ("VIRUS ARMOR:Lafuteria", 12, 0x2f, 50, 20), ("BRIGHTNESS CIRCLE", 11, 0x30, 50, 20), ("AURA FIELD", 12, 0x31, 50, 20),
    ("ELECTRO FRAME", 11, 0x32, 50, 20), ("SACRED CLOTH", 11, 0x33, 50, 20), ("SMOKING PLATE", 10, 0x34, 50, 20),
]

# Shields: (name, stars, variant, max_dfp_bonus, max_evp_bonus)
SHIELDS = [
    ("Barrier", 0, 0x0, 5, 5), ("Shield", 0, 0x1, 5, 5), ("Core Shield", 1, 0x2, 5, 5), ("Giga Shield", 2, 0x3, 5, 5),
    ("Soul Barrier", 3, 0x4, 5, 5), ("Hard Shield", 3, 0x5, 5, 5), ("Brave Barrier", 4, 0x6, 5, 5), ("Solid Shield", 4, 0x7, 5, 5),
    ("Flame Barrier", 5, 0x8, 5, 5), ("Plasma Barrier", 5, 0x9, 5, 5), ("Freeze Barrier", 5, 0xa, 5, 5), ("Psychic Barrier", 6, 0xb, 5, 5),
    ("General Shield", 6, 0xc, 5, 5), ("Protect Barrier", 7, 0xd, 5, 5), ("Glorious Shield", 7, 0xe, 5, 5), ("Imperial Barrier", 8, 0xf, 5, 5),
    ("Guardian Shield", 8, 0x10, 5, 5),
    ("Divinity Barrier", 9, 0x11, 5, 5), ("Ultimate Shield", 10, 0x12, 5, 5), ("Spiritual Shield", 11, 0x13, 5, 5),
    ("Celestial Shield", 12, 0x14, 5, 5), ("INVISIBLE GUARD", 9, 0x15, 8, 8), ("SACRED GUARD", 11, 0x16, 8, 8),
    ("S-PARTS ver1.16", 10, 0x17, 8, 8), ("S-PARTS ver2.01", 11, 0x18, 7, 7), ("LIGHT RELIEF", 9, 0x19, 7, 7),
    ("SHIELD OF DELSABER", 12, 0x1a, 7, 7), ("FORCE WALL", 11, 0x1b, 10, 10), ("RANGER WALL", 11, 0x1c, 10, 10),
    ("HUNTER WALL", 11, 0x1d, 10, 10), ("ATTRIBUTE WALL", 11, 0x1e, 10, 10), ("SECRET GEAR", 11, 0x1f, 10, 10),
    ("COMBAT GEAR", 11, 0x20, 0, 0), ("PROTO REGENE GEAR", 10, 0x21, 7, 7), ("REGENERATE GEAR", 11, 0x22, 7, 7),
    ("REGENE GEAR ADV.", 12, 0x23, 7, 7), ("FLOWEN'S SHIELD", 10, 0x24, 10, 10), ("CUSTOM BARRIER ver.OO", 10, 0x25, 10, 10),
    ("DB'S SHIELD", 10, 0x26, 10, 10), ("RED RING", 12, 0x27, 85, 25), ("TRIPOLIC SHIELD", 10, 0x28, 50, 15),
    ("STANDSTILL SHIELD", 11, 0x29, 50, 15), ("SAFETY HEART", 11, 0x2a, 50, 15), ("KASAMI BRACER", 12, 0x2b, 50, 15),
    ("GODS SHIELD SUZAKU", 11, 0x2c, 50, 15), ("GODS SHIELD GENBU", 11, 0x2d, 50, 15), ("GODS SHIELD BYAKKO", 11, 0x2e, 50, 15),
    ("GODS SHIELD SEIRYU", 11, 0x2f, 50, 15), ("HANTER'S SHELL", 10, 0x30, 50, 15), ("RIKO'S GLASSES", 12, 0x31, 85, 25),
    ("RIKO'S EARRING", 12, 0x32, 85, 25), ("BLUE RING", 12, 0x33, 85, 25), ("YELLOW RING", 12, 0x34, 85, 25),
    ("SECURE FEET", 11, 0x35, 50, 15), ("PURPLE RING", 12, 0x36, 1, 1), ("GREEN RING", 12, 0x37, 1, 1),
    ("BLACK RING", 12, 0x38, 1, 1), ("WHITE RING", 12, 0x39, 1, 1),
]

# Units: (name, stars, variant, base_stat_amount, modifier_amount) -- legit max modifier is +2
UNITS = [
    ("Knight/Power", 2, 0x0, 5, 1), ("General/Power", 5, 0x1, 10, 1), ("Ogre/Power", 8, 0x2, 15, 1), ("God/Power", 11, 0x3, 25, 2),
    ("Priest/Mind", 2, 0x4, 5, 1), ("General/Mind", 5, 0x5, 10, 1), ("Angel/Mind", 8, 0x6, 15, 1), ("God/Mind", 11, 0x7, 25, 3),
    ("Marksman/Arm", 2, 0x8, 3, 1), ("General/Arm", 5, 0x9, 7, 1), ("Elf/Arm", 8, 0xa, 11, 1), ("God/Arm", 11, 0xb, 15, 1),
    ("Thief/Legs", 3, 0xc, 10, 2), ("General/Legs", 6, 0xd, 20, 2), ("Elf/Legs", 9, 0xe, 30, 2), ("God/Legs", 11, 0xf, 40, 2),
    ("Digger/HP", 2, 0x10, 10, 2), ("General/HP", 5, 0x11, 20, 2), ("Dragon/HP", 8, 0x12, 30, 2), ("God/HP", 11, 0x13, 40, 2),
    ("Magician/TP", 2, 0x14, 5, 1), ("General/TP", 5, 0x15, 10, 1), ("Angel/TP", 8, 0x16, 15, 1), ("God/TP", 11, 0x17, 20, 1),
    ("Warrior/Body", 3, 0x18, 10, 2), ("General/Body", 6, 0x19, 20, 2), ("Metal/Body", 9, 0x1a, 30, 2), ("God/Body", 11, 0x1b, 40, 2),
    ("Angel/Luck", 4, 0x1c, 5, 1), ("God/Luck", 8, 0x1d, 10, 1),
    ("Master/Ability", 5, 0x1e, 10, 1), ("Hero/Ability", 9, 0x1f, 15, 1), ("God/Ability", 11, 0x20, 20, 1),
    ("Resist/Fire", 2, 0x21, 3, 1), ("Resist/Flame", 6, 0x22, 7, 1), ("Resist/Burning", 10, 0x23, 11, 1),
    ("Resist/Cold", 2, 0x24, 3, 1), ("Resist/Freeze", 5, 0x25, 7, 1), ("Resist/Blizzard", 9, 0x26, 11, 1),
    ("Resist/Shock", 2, 0x27, 3, 1), ("Resist/Thunder", 6, 0x28, 7, 1), ("Resist/Storm", 10, 0x29, 11, 1),
    ("Resist/Light", 3, 0x2a, 3, 1), ("Resist/Saint", 7, 0x2b, 7, 1), ("Resist/Holy", 11, 0x2c, 11, 1),
    ("Resist/Dark", 4, 0x2d, 3, 1), ("Resist/Evil", 7, 0x2e, 7, 1), ("Resist/Devil", 10, 0x2f, 11, 1),
    ("All/Resist", 7, 0x30, 3, 1), ("Super/Resist", 9, 0x31, 7, 1), ("Perfect/Resist", 11, 0x32, 11, 1),
    ("HP/Restorate", 4, 0x33, 14, 0), ("HP/Generate", 7, 0x34, 11, 0), ("HP/Revival", 11, 0x35, 8, 0),
    ("TP/Restorate", 5, 0x36, 15, 0), ("TP/Generate", 8, 0x37, 13, 0), ("TP/Revival", 12, 0x38, 11, 0),
    ("PB/Amplifier", 5, 0x39, 40, 0), ("PB/Generate", 9, 0x3a, 35, 0), ("PB/Create", 11, 0x3b, 23, 0),
    ("Wizard/Technique", 8, 0x3c, 1, 0), ("Devil/Technique", 10, 0x3d, 2, 0), ("God/Technique", 12, 0x3e, 3, 0),
    ("General/Battle", 7, 0x3f, 5, 0), ("Devil/Battle", 9, 0x40, 10, 0), ("God/Battle", 11, 0x41, 20, 0),
    ("State/Maintenance", 6, 0x42, 0, 0), ("Trap/Search", 7, 0x43, 0, 0),
]

# Mag species names by ID (sourced from amon-x.github.io/psoitems v2.json, cross-checked
# against mag-metadata-table-v2.json for species count). Index = species_id.
MAG_SPECIES = [
    "Mag", "Varuna", "Mitra", "Surya", "Vayu", "Varaha", "Kama", "Ushasu", "Apsaras", "Kumara",
    "Kaitabha", "Tapas", "Bhirava", "Kalki", "Rudra", "Marutah", "Yaksa", "Sita", "Garuda", "Nandin",
    "Ashvinau", "Ribhava", "Soma", "Ila", "Durga", "Vritra", "Namuci", "Sumba", "Naga", "Pitri",
    "Kabanda", "Ravana", "Marica", "Soniti", "Preta", "Andhaka", "Bana", "Naraka", "Madhu", "Churel",
    "ROBOCHAO", "OPA-OPA", "PIAN", "CHAO", "CHU CHU", "KAPU KAPU", "ANGEL'S WING", "DEVIL'S WING",
    "ELENOR", "MARK3", "MASTER SYSTEM", "GENESIS", "SEGA SATURN", "DREAMCAST", "HAMBURGER",
    "PANZER'S TAIL", "DEVIL'S TAIL",
]
MAG_SPECIES_COUNT = len(MAG_SPECIES)

# Photon blast names, in on-disk index order (confirmed against a real maxed mag
# in the user's save -- see reference doc section 7). Index 0-5 only; the on-disk
# format allocates just 2 bits for the "left" PB slot (values 0-3), so Leilla(4)
# and Mylla & Youlla(5) cannot be assigned to the left slot without truncation.
PB_NAMES = ["Farlla", "Estlla", "Golla", "Pilla", "Leilla", "Mylla & Youlla"]

# Parts / special quest items: (name, data1_1, data1_2)
# Sourced from newserv's names-v2.json (the client's own item text index) --
# an earlier version of this list had names misaligned with the wrong byte
# codes starting partway through 0x0D (e.g. "S-red's Arms" was wrongly given
# 0x0D/0x06 -- its real code is 0x0E/0x00). Corrected against that source.
PARTS = [
    ("Sorcerer's Right Arm", 0x0D, 0x00), ("S-beat's Arms", 0x0D, 0x01), ("P-arm's Arms", 0x0D, 0x02),
    ("Delsaber's Right Arm", 0x0D, 0x03), ("C-bringer's Right Arm", 0x0D, 0x04), ("Delsabre's Left Arm", 0x0D, 0x05),
    ("Book of KATANA1", 0x0D, 0x06), ("Book of KATANA2", 0x0D, 0x07), ("Book of KATANA3", 0x0D, 0x08),
    ("S-red's Arms", 0x0E, 0x00), ("Dragon's Claw", 0x0E, 0x01), ("Hildebear's Head", 0x0E, 0x02),
    ("Hildeblue's Head", 0x0E, 0x03), ("Parts of Baranz", 0x0E, 0x04), ("Belra's Right Arm", 0x0E, 0x05),
    ("Joint Parts", 0x0E, 0x06), ("Weapons Bronze Badge", 0x0E, 0x07), ("Weapons Silver Badge", 0x0E, 0x08),
    ("Weapons Gold Badge", 0x0E, 0x09), ("Weapons Crystal Badge", 0x0E, 0x0A), ("Weapons Steel Badge", 0x0E, 0x0B),
    ("Weapons Aluminum Badge", 0x0E, 0x0C), ("Weapons Leather Badge", 0x0E, 0x0D), ("Weapons Bone Badge", 0x0E, 0x0E),
    ("Letter of appreciation", 0x0E, 0x0F), ("Autograph Album", 0x0E, 0x10), ("High-level Mag Cell, Eno", 0x0E, 0x11),
    ("High-level Mag Armor, Uru", 0x0E, 0x12), ("Special Gene Flou", 0x0E, 0x13), ("Sound Source FM", 0x0E, 0x14),
    ('Parts of "68000"', 0x0E, 0x15), ("SH2", 0x0E, 0x16), ("SH4", 0x0E, 0x17),
    ("Modem", 0x0E, 0x18), ("Power VR", 0x0E, 0x19), ("Glory in the past", 0x0E, 0x1A),
    ("Valentine's Chocolate", 0x0E, 0x1B), ("New Year's Card", 0x0E, 0x1C), ("Christmas Card", 0x0E, 0x1D),
    ("Birthday Card", 0x0E, 0x1E), ("Proof of Sonic Team", 0x0E, 0x1F), ("Special Event Ticket", 0x0E, 0x20),
    ("Flower Bouquet", 0x0E, 0x21), ("Cake", 0x0E, 0x22), ("Accessories", 0x0E, 0x23),
    ("Mr.Naka's Business Card", 0x0E, 0x24),
]

# Tools/consumables: (name, data1_1, data1_2, stackable). Also sourced from
# names-v2.json. `data1_2` (0x0300, the tech disk slot) is intentionally
# excluded -- tech disks are handled separately in build_tech_disk/decode_tech_disk.
TOOLS = [
    ("Monomate", 0x00, 0x00, True), ("Dimate", 0x00, 0x01, True), ("Trimate", 0x00, 0x02, True),
    ("Monofluid", 0x01, 0x00, True), ("Difluid", 0x01, 0x01, True), ("Trifluid", 0x01, 0x02, True),
    ("Sol Atomizer", 0x03, 0x00, True), ("Moon Atomizer", 0x04, 0x00, True), ("Star Atomizer", 0x05, 0x00, True),
    ("Antidote", 0x06, 0x00, True), ("Antiparalysis", 0x06, 0x01, True),
    ("Telepipe", 0x07, 0x00, True), ("Trap Vision", 0x08, 0x00, True), ("Scape Doll", 0x09, 0x00, True),
    ("Monogrinder", 0x0A, 0x00, False), ("Digrinder", 0x0A, 0x01, False), ("Trigrinder", 0x0A, 0x02, False),
    ("Power Material", 0x0B, 0x00, False), ("Mind Material", 0x0B, 0x01, False), ("Evade Material", 0x0B, 0x02, False),
    ("HP Material", 0x0B, 0x03, False), ("TP Material", 0x0B, 0x04, False), ("Def Material", 0x0B, 0x05, False),
    ("Hit Material", 0x0B, 0x06, False), ("Luck Material", 0x0B, 0x07, False),
    ("Cell of MAG 502", 0x0C, 0x00, False), ("Cell of MAG 213", 0x0C, 0x01, False),
    ("Parts of RoboChao", 0x0C, 0x02, False), ("Heart of Opa Opa", 0x0C, 0x03, False),
    ("Heart of Pian", 0x0C, 0x04, False), ("Heart of Chao", 0x0C, 0x05, False),
]

# Techniques: (name, tech_id)
TECHNIQUES = [
    ("Foie", 0), ("Gifoie", 1), ("Rafoie", 2), ("Barta", 3), ("Gibarta", 4), ("Rabarta", 5),
    ("Zonde", 6), ("Gizonde", 7), ("Razonde", 8), ("Resta", 9), ("Anti", 10), ("Reverser", 11),
    ("Shifta", 12), ("Deband", 13), ("Ryuker", 14), ("Megid", 15), ("Jellen", 16), ("Zalure", 17),
    ("Grants", 18),
]


# ---------------------------------------------------------------------------
# Reverse lookups: (class, variant) / variant / (d1, d2) -> real item name.
# Used to turn raw stored bytes back into human-readable descriptions.
# ---------------------------------------------------------------------------

def _weapon_lookup(*lists):
    lookup = {}
    for lst in lists:
        for name, stars, cls, variant in lst:
            lookup[(cls, variant)] = name
    return lookup


WEAPON_NAME_BY_CLASS_VARIANT = _weapon_lookup(GUNS, SWORDS, WANDS)
SRANK_BASE_NAME_BY_CLASS = {cls: name for cls, name in GUN_SRANK + SWORD_SRANK + WAND_SRANK}
ARMOR_NAME_BY_VARIANT = {variant: name for name, stars, variant, d, e in ARMOR}
SHIELD_NAME_BY_VARIANT = {variant: name for name, stars, variant, d, e in SHIELDS}
UNIT_NAME_BY_VARIANT = {variant: name for name, stars, variant, base, modamt in UNITS}
PART_NAME_BY_CODES = {(d1, d2): name for name, d1, d2 in PARTS}
TOOL_NAME_BY_CODES = {(d1, d2): name for name, d1, d2, stackable in TOOLS}
TOOL_STACKABLE_BY_CODES = {(d1, d2): stackable for name, d1, d2, stackable in TOOLS}


def weapon_category_for_class(cls):
    """Which of Guns/Swords/Wands a weapon class byte belongs to, incl. S-ranks."""
    if any(c == cls for _, _, c, _ in GUNS) or any(c == cls for c, _ in GUN_SRANK):
        return "Guns"
    if any(c == cls for _, _, c, _ in SWORDS) or any(c == cls for c, _ in SWORD_SRANK):
        return "Swords"
    if any(c == cls for _, _, c, _ in WANDS) or any(c == cls for c, _ in WAND_SRANK):
        return "Wands"
    return None


# ---------------------------------------------------------------------------
# Real equip-requirement/usability data from the actual client's item
# parameter table (item-parameter-table-pc-v2.json from fuzziqersoftware/
# newserv, reduced to just the fields needed here). Used to warn the user
# BEFORE they put an item on a character that the game will refuse to equip
# it for, rather than finding out only after testing in an emulator.
# ---------------------------------------------------------------------------

_PMT_PATH = os.path.join(os.path.dirname(__file__), "data", "item-parameter-table-pc-v2-reduced.json")
with open(_PMT_PATH) as _f:
    _PMT_RAW = json.load(_f)

# key format: usually 6 hex chars = data1[0](item category) + data1[1](kind/class)
# + data1[2](variant); mag entries (category 2) are only 4 chars (category+species,
# no third byte) since mags don't have a separate variant field in the PMT.
# Keyed on all 3 parts -- data1[1]/data1[2] alone collide across categories (e.g.
# weapon class 0x01 is a real Sword, but armor/shield/unit variant 0x01 also exists
# under category 0x01, and they are unrelated items).
PMT_BY_CATEGORY_CLASS_VARIANT = {}
for _key, _entry in _PMT_RAW.items():
    _category = int(_key[0:2], 16)
    _cls = int(_key[2:4], 16)
    _variant = int(_key[4:6], 16) if len(_key) >= 6 else 0
    PMT_BY_CATEGORY_CLASS_VARIANT[(_category, _cls, _variant)] = _entry

# Bits in usability_flags (ALL bits corresponding to the character's own
# attributes must be set in the item's flags for it to be equippable):
#   01=hunter 02=ranger 04=force 08=human 10=android 20=newman 40=male 80=female
USABILITY_BIT_NAMES = {0x01: "Hunter", 0x02: "Ranger", 0x04: "Force", 0x08: "Human",
                        0x10: "Android", 0x20: "Newman", 0x40: "Male", 0x80: "Female"}

# Per character class (index matches char_class byte / character.CLASS_NAMES):
# (job_bit, race_bit, gender_bit) -- standard PSO class/race/gender pairings.
CLASS_USABILITY_BITS = {
    0: 0x01 | 0x08 | 0x40,   # HUmar: Hunter, Human, Male
    1: 0x01 | 0x20 | 0x80,   # HUnewearl: Hunter, Newman, Female
    2: 0x01 | 0x10 | 0x40,   # HUcast: Hunter, Android, Male
    3: 0x02 | 0x08 | 0x40,   # RAmar: Ranger, Human, Male
    4: 0x02 | 0x10 | 0x40,   # RAcast: Ranger, Android, Male
    5: 0x02 | 0x10 | 0x80,   # RAcaseal: Ranger, Android, Female
    6: 0x04 | 0x08 | 0x80,   # FOmarl: Force, Human, Female
    7: 0x04 | 0x20 | 0x40,   # FOnewm: Force, Newman, Male
    8: 0x04 | 0x20 | 0x80,   # FOnewearl: Force, Newman, Female
}


def _disambiguate_labels(labels):
    """Append a [i/n] tag to any label that repeats in the list -- the full catalog
    has several items that share a display name (e.g. all 7 AGITO variants render
    with the identical string "AGITO" in the client's own text table), and callers
    resolve a chosen label back to a row via list.index(), which would otherwise
    always resolve to the first matching row and make the others unpickable."""
    counts = Counter(labels)
    seen = Counter()
    out = []
    for label in labels:
        if counts[label] > 1:
            seen[label] += 1
            out.append(f"{label} [{seen[label]}/{counts[label]}]")
        else:
            out.append(label)
    return out


def weapon_labels(rows):
    """Display labels for a GUNS/SWORDS/WANDS-shaped list, in the same order."""
    return _disambiguate_labels([f"{n} ({s}*)" for n, s, c, v in rows])


def item_labels(rows):
    """Display labels for an ARMOR/SHIELDS/UNITS-shaped list, in the same order."""
    return _disambiguate_labels([f"{n} ({s}*)" for n, s, v, *_rest in rows])


def usability_flags_text(flags):
    """Human-readable list of who can use an item, e.g. 'Ranger, Human/Android/Newman'."""
    if flags is None:
        return "unknown"
    jobs = [n for b, n in [(0x01, "Hunter"), (0x02, "Ranger"), (0x04, "Force")] if flags & b]
    races = [n for b, n in [(0x08, "Human"), (0x10, "Android"), (0x20, "Newman")] if flags & b]
    genders = [n for b, n in [(0x40, "Male"), (0x80, "Female")] if flags & b]
    parts = []
    if jobs:
        parts.append("/".join(jobs))
    if races:
        parts.append("/".join(races))
    if genders:
        parts.append("/".join(genders))
    return ", ".join(parts) if parts else "nobody (!!)"


def check_equip(char_class_idx, item_category, item_class, item_variant=0):
    """Returns (ok: bool, message: str) for whether the given character class can
    equip the item at (item_category, item_class, item_variant) -- item_category
    is data1[0] (0=weapon, 1=armor/shield/unit) -- based on the real item
    parameter table. message explains why not, or describes who CAN use it."""
    entry = PMT_BY_CATEGORY_CLASS_VARIANT.get((item_category, item_class, item_variant))
    if entry is None:
        return False, "Not a real V2 item (no entry in the client's item table) -- will not work in-game."
    flags = entry.get("UsabilityFlags")
    if flags is None:
        # Units have no class/race/gender restriction on-disk (the real UnitT
        # struct has no usability_flags field at all) -- usable by everyone.
        return True, "Usable by: everyone"
    char_bits = CLASS_USABILITY_BITS.get(char_class_idx)
    usable_text = usability_flags_text(flags)
    if char_bits is not None and (flags & char_bits) != char_bits:
        return False, f"NOT equippable by this character -- usable by: {usable_text} only."
    extra = []
    if entry.get("ATPRequired"):
        extra.append(f"requires ATP {entry['ATPRequired']}")
    if entry.get("ATARequired"):
        extra.append(f"requires ATA {entry['ATARequired']}")
    if entry.get("MSTRequired"):
        extra.append(f"requires MST {entry['MSTRequired']}")
    suffix = f" ({', '.join(extra)})" if extra else ""
    return True, f"Usable by: {usable_text}{suffix}"
