"""Curated item lists researched during the reverse-engineering session. Not the
full game catalog -- covers guns/swords/wands (8+ stars), armor/shields/units (9+
stars), all 58 mag species, all 19 techniques, and the 46 real "Parts" quest items.
See /Volumes/MacEMU/bios/dc/PSO Saves/ClaudeVMUWork/ for how these were derived.

Each entry: (display_name, stars_or_None, class_byte, variant_byte)
"""
import json
import os

GUNS = [
    ("VARISTA", 9, 0x06, 0x05), ("CUSTOM RAY ver.OO", 9, 0x06, 0x06), ("BRAVACE", 9, 0x06, 0x07),
    ("M&A60 VISE", 9, 0x08, 0x05), ("H&S25 JUSTICE", 9, 0x08, 0x06), ("L&K14 COMBAT", 9, 0x08, 0x07),
    ("CRUSH BULLET", 9, 0x09, 0x05), ("METEOR SMASH", 9, 0x09, 0x06), ("FINAL IMPACT", 9, 0x09, 0x07),
    ("VISK-235W", 9, 0x07, 0x05), ("WALS-MK2", 9, 0x07, 0x06), ("JUSTY-23ST", 9, 0x07, 0x07),
    ("SPREAD NEEDLE", 11, 0x12, 0x00), ("HOLY RAY", 11, 0x13, 0x00), ("INFERNO BAZOOKA", 11, 0x14, 0x00),
    ("FLAME VISIT", 11, 0x15, 0x00), ("C-BRINGER'S RIFLE", 12, 0x1b, 0x00), ("EGG BLASTER", 10, 0x1c, 0x00),
    ("HEAVEN PUNISHER", 12, 0x1e, 0x00), ("SUPPRESSED GUN", 9, 0x26, 0x00),
    ("HANDGUN:GULD", 12, 0x42, 0x00), ("HANDGUN:MILLA", 12, 0x43, 0x00), ("RED HANDGUN", 9, 0x44, 0x00),
    ("FROZEN SHOOTER", 11, 0x45, 0x00), ("ANTI ANDROID RIFLE", 11, 0x46, 0x00), ("TWIN PSYCHOGUN", 11, 0x49, 0x00),
    ("DRILL LAUNCHER", 11, 0x4a, 0x00), ("GULD MILLA", 12, 0x4b, 0x00), ("RED MECHGUN", 9, 0x4c, 0x00),
    ("BERLA CANNON", 12, 0x4d, 0x00), ("PANZER FAUST", 12, 0x4e, 0x00),
    ("YASMINKOV 3000R", 10, 0x65, 0x00), ("ANO RIFLE", 12, 0x66, 0x00), ("YASMINKOV 2000H", 10, 0x6a, 0x00),
    ("YASMINKOV 7000V", 11, 0x6b, 0x00), ("YASMINKOV 9200M", 10, 0x6c, 0x00), ("MASER BEAM", 12, 0x6d, 0x00),
]
GUN_SRANK = [(0x75, "S-RANK GUN"), (0x76, "S-RANK RIFLE"), (0x77, "S-RANK MECHGUN"),
             (0x78, "S-RANK SHOT"), (0x7e, "S-RANK BAZOOKA"), (0x7f, "S-RANK NEEDLE"),
             (0x83, "S-RANK PSYCHOGUN")]

SWORDS = [
    ("DB'S SABER", 9, 0x01, 0x05), ("KALADBOLG", 9, 0x01, 0x06), ("DURANDAL", 9, 0x01, 0x07),
    ("FLOWEN'S SWORD", 9, 0x02, 0x05), ("LAST SURVIVOR", 9, 0x02, 0x06), ("DRAGON SLAYER", 9, 0x02, 0x07),
    ("BLADE DANCE", 9, 0x03, 0x05), ("BLOODY ART", 9, 0x03, 0x06), ("CROSS SCAR", 9, 0x03, 0x07),
    ("BRIONAC", 9, 0x04, 0x05), ("VJAYA", 9, 0x04, 0x06), ("GAE BOLG", 9, 0x04, 0x07),
    ("SLICER OF ASSASSIN", 9, 0x05, 0x05), ("DISKA OF LIBERATOR", 9, 0x05, 0x06), ("DISKA OF BRAVEMAN", 9, 0x05, 0x07),
    ("PHOTON CLAW", 9, 0x0d, 0x00), ("SILENCE CLAW", 10, 0x0d, 0x01), ("NEI'S CLAW", 10, 0x0d, 0x02),
    ("DOUBLE SABER", 9, 0x0e, 0x00), ("STAG CUTLERY", 10, 0x0e, 0x01), ("TWIN BRAND", 11, 0x0e, 0x02),
    ("OROTIAGITO", 12, 0x10, 0x00), ("AGITO (AUW 1975)", 10, 0x10, 0x01), ("AGITO (AUW 1983)", 9, 0x10, 0x02),
    ("AGITO (AUW 2001)", 9, 0x10, 0x03), ("AGITO (AUW 1991)", 9, 0x10, 0x04), ("AGITO (AUW 1977)", 9, 0x10, 0x05),
    ("AGITO (AUW 1980)", 9, 0x10, 0x06),
    ("SOUL EATER", 10, 0x11, 0x00), ("SOUL BANISH", 11, 0x11, 0x01),
    ("AKIKO'S FRYING PAN", 10, 0x16, 0x00), ("S-BEAT'S BLADE", 11, 0x18, 0x00), ("P-ARMS'S BLADE", 11, 0x19, 0x00),
    ("DELSABER'S BUSTER", 11, 0x1a, 0x00), ("VICTOR AXE", 9, 0x20, 0x00), ("CHAIN SAWD", 11, 0x21, 0x00),
    ("STING TIP", 10, 0x23, 0x00), ("LAVIS CANNON", 12, 0x1f, 0x00), ("ANCIENT SABER", 10, 0x27, 0x00),
    ("HARISEN BATTLE FAN", 11, 0x28, 0x00), ("YAMIGARASU", 12, 0x29, 0x00), ("AKIKO'S WOK", 11, 0x2a, 0x00),
    ("TOY HAMMER", 11, 0x2b, 0x00), ("ELYSION", 11, 0x2c, 0x00), ("RED SABER", 9, 0x2d, 0x00),
    ("METEOR CUDGEL", 10, 0x2e, 0x00), ("MONKEY KING BAR", 12, 0x2f, 0x00), ("DOUBLE CANNON", 12, 0x30, 0x00),
    ("HUGE BATTLE FAN", 12, 0x31, 0x00), ("TSUMIKIRI J-SWORD", 12, 0x32, 0x00), ("SEALED J-SWORD", 10, 0x33, 0x00),
    ("RED SWORD", 9, 0x34, 0x00), ("CRAZY TUNE", 11, 0x35, 0x00), ("TWIN CHAKRAM", 10, 0x36, 0x00),
    ("WOK OF AKIKO'S SHOP", 11, 0x37, 0x00), ("LAVIS BLADE", 12, 0x38, 0x00), ("RED DAGGER", 9, 0x39, 0x00),
    ("MADAM'S PARASOL", 12, 0x3a, 0x00), ("MADAM'S UMBRELLA", 11, 0x3b, 0x00), ("IMPERIAL PICK", 10, 0x3c, 0x00),
    ("BERDYSH", 12, 0x3d, 0x00), ("RED PARTISAN", 9, 0x3e, 0x00), ("FLIGHT CUTTER", 12, 0x3f, 0x00),
    ("FLIGHT FAN", 11, 0x40, 0x00), ("RED SLICER", 9, 0x41, 0x00), ("TWIN BLAZE", 12, 0x5e, 0x00),
    ("DRAGON'S CLAW", 11, 0x60, 0x00), ("PANTHER'S CLAW", 11, 0x61, 0x00), ("S-RED'S BLADE", 12, 0x62, 0x00),
    ("PLANTAIN HUGE FAN", 12, 0x63, 0x00), ("CHAMELEON SCYTHE", 11, 0x64, 0x00), ("HEART OF POUMN", 12, 0x69, 0x00),
    ("FLOWER BOUQUET", 9, 0x6f, 0x00),
]
SWORD_SRANK = [(0x70, "SSABER"), (0x71, "SSWORD"), (0x72, "SBLADE"), (0x73, "SPARTISN"),
               (0x74, "SSLICER"), (0x7c, "STWIN"), (0x7d, "SCLAW"), (0x80, "SSCYTHE"),
               (0x81, "SHAMMER"), (0x86, "SHARISEN"), (0x87, "SJBLADE"), (0x88, "SJCUTTER")]

WANDS = [
    ("CLUB OF LACONIUM", 9, 0x0a, 0x04), ("MACE OF ADAMAN", 9, 0x0a, 0x05), ("CLUB OF ZUMIURAN", 9, 0x0a, 0x06),
    ("BATTLE VERGE", 9, 0x0b, 0x04), ("BRAVE HAMMER", 9, 0x0b, 0x05), ("ALIVE AQHU", 9, 0x0b, 0x06),
    ("FIRE SCEPTER:AGNI", 9, 0x0c, 0x04), ("ICE STAFF:DAGON", 9, 0x0c, 0x05), ("STORM WAND:INDRA", 9, 0x0c, 0x06),
    ("C-SORCERER'S CANE", 11, 0x17, 0x00), ("CADUCEUS", 11, 0x22, 0x00), ("MAGICAL PIECE", 11, 0x24, 0x00),
    ("TECHNICAL CROZIER", 10, 0x25, 0x00), ("PSYCHO WAND", 12, 0x1d, 0x00), ("SUMMIT MOON", 11, 0x4f, 0x00),
    ("WINDMILL", 12, 0x50, 0x00), ("EVIL CURST", 12, 0x51, 0x00), ("FLOWER CANE", 11, 0x52, 0x00),
    ("HILDEBEAR'S CANE", 10, 0x53, 0x00), ("HILDEBLUE'S CANE", 12, 0x54, 0x00), ("RABBIT WAND", 12, 0x55, 0x00),
    ("PLANTAIN LEAF", 10, 0x56, 0x00), ("DEMONIC FORK", 11, 0x57, 0x00), ("STIRKER OF CHAO", 12, 0x58, 0x00),
    ("BROOM", 10, 0x59, 0x00), ("PROPHETS OF MOTAV", 12, 0x5a, 0x00), ("THE SIGH OF A GOD", 11, 0x5b, 0x00),
    ("TWINKLE STAR", 11, 0x5c, 0x00), ("PLANTAIN FAN", 11, 0x5d, 0x00), ("MARINA'S BAG", 11, 0x5f, 0x00),
    ("BRANCH OF PAKUPAKU", 9, 0x68, 0x00), ("GAME MAGAZNE", 11, 0x6e, 0x00),
]
WAND_SRANK = [(0x79, "SCANE"), (0x7a, "SROD"), (0x7b, "SWAND"), (0x82, "SMOON"), (0x85, "SWINDMIL")]

# Armor: (name, stars, variant, max_dfp_bonus, max_evp_bonus)
ARMOR = [
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
    ("Divinity Barrier", 9, 0x11, 5, 5), ("Ultimate Shield", 10, 0x12, 5, 5), ("Spiritual Shield", 11, 0x13, 5, 5),
    ("Celestial Shield", 12, 0x14, 5, 5), ("INVISIBLE GUARD", 9, 0x15, 8, 8), ("SACRED GUARD", 11, 0x16, 8, 8),
    ("S-PARTS ver1.16", 10, 0x17, 8, 8), ("S-PARTS ver2.01", 11, 0x18, 7, 7), ("LIGHT RELIEF", 9, 0x19, 7, 7),
    ("SHIELD OF DELSABER", 12, 0x1a, 7, 7), ("FORCE WALL", 11, 0x1b, 10, 10), ("RANGER WALL", 11, 0x1c, 10, 10),
    ("HUNTER WALL", 11, 0x1d, 10, 10), ("ATTRIBUTE WALL", 11, 0x1e, 10, 10), ("SECRET GEAR", 11, 0x1f, 10, 10),
    ("COMBAT GEAR", 11, 0x20, 0, 0), ("PROTO REGENE GEAR", 10, 0x21, 7, 7), ("REGENERATE GEAR", 11, 0x22, 7, 7),
    ("REGENE GEAR ADV", 12, 0x23, 7, 7), ("FLOWEN'S SHIELD", 10, 0x24, 10, 10), ("CUSTOM BARRIER ver.OO", 10, 0x25, 10, 10),
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
    ("God/Power", 11, 0x03, 25, 2), ("God/Mind", 11, 0x07, 25, 3), ("God/Arm", 11, 0x0b, 15, 1),
    ("Elf/Legs", 9, 0x0e, 30, 2), ("God/Legs", 11, 0x0f, 40, 2), ("God/HP", 11, 0x13, 40, 2),
    ("God/TP", 11, 0x17, 20, 1), ("Metal/Body", 9, 0x1a, 30, 2), ("God/Body", 11, 0x1b, 40, 2),
    ("Hero/Ability", 9, 0x1f, 15, 1), ("God/Ability", 11, 0x20, 20, 1), ("Resist/Burning", 10, 0x23, 11, 1),
    ("Resist/Blizzard", 9, 0x26, 11, 1), ("Resist/Storm", 10, 0x29, 11, 1), ("Resist/Holy", 11, 0x2c, 11, 1),
    ("Resist/Devil", 10, 0x2f, 11, 1), ("Super/Resist", 9, 0x31, 7, 1), ("Perfect/Resist", 11, 0x32, 11, 1),
    ("HP/Revival", 11, 0x35, 8, 0), ("TP/Revival", 12, 0x38, 11, 0), ("PB/Generate", 9, 0x3a, 35, 0),
    ("PB/Create", 11, 0x3b, 23, 0), ("Devil/Technique", 10, 0x3d, 2, 0), ("God/Technique", 12, 0x3e, 3, 0),
    ("Devil/Battle", 9, 0x40, 10, 0), ("God/Battle", 11, 0x41, 20, 0),
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
    "PANZER'S TAIL", "DAVIL'S TAIL",
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
    flags = entry["UsabilityFlags"]
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
