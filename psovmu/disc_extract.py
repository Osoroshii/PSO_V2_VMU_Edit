"""Extract files out of a user's own PSO Dreamcast V2 disc image.

Supports a DiscJuggler `.cdi` rip (the common format for GD-ROM dumps) or a
plain ISO9660 image (`.iso`/`.gdi`'s data track already extracted). Only reads
the specific files a caller asks for -- never materializes the whole ~700MB
disc image on disk.

This is purely a reader for files already inside a disc image the user
supplies; it has no network access and produces no bundled game assets.
"""
import struct
import zlib

SECTOR = 2048

_CDI_V2 = 0x80000004
_CDI_V3 = 0x80000005
_CDI_V35 = 0x80000006
_TRACK_START_MARK = bytes([0, 0, 1, 0, 0, 0, 0xFF, 0xFF, 0xFF, 0xFF])


class DiscFormatError(Exception):
    pass


def _parse_cdi_tracks(f):
    """Return the CDI track descriptor for the last (highest-LBA) data track --
    the GD-ROM high-density data area, which is what holds the ISO9660
    filesystem for a Dreamcast disc. Port of the reverse-engineered `cdirip`
    track-table parser (see docs/REFERENCE.md section 10.1 for the details)."""
    f.seek(0, 2)
    length = f.tell()
    f.seek(length - 8)
    version, header_offset = struct.unpack("<II", f.read(8))
    if version not in (_CDI_V2, _CDI_V3, _CDI_V35):
        raise DiscFormatError(f"not a recognized .cdi file (version={hex(version)})")

    f.seek(length - header_offset if version == _CDI_V35 else header_offset)
    sessions = struct.unpack("<H", f.read(2))[0]

    tracks = []
    data_position = 0
    for _ in range(sessions):
        ntracks = struct.unpack("<H", f.read(2))[0]
        for _ in range(ntracks):
            temp = struct.unpack("<I", f.read(4))[0]
            if temp != 0:
                f.seek(8, 1)
            if f.read(10) != _TRACK_START_MARK or f.read(10) != _TRACK_START_MARK:
                raise DiscFormatError("bad track marker -- unexpected .cdi layout")
            f.seek(4, 1)
            fnlen = f.read(1)[0]
            f.seek(fnlen, 1)
            f.seek(11 + 4 + 4, 1)
            temp = struct.unpack("<I", f.read(4))[0]
            if temp == 0x80000000:
                f.seek(8, 1)
            f.seek(2, 1)
            pregap_length, tlength = struct.unpack("<II", f.read(8))
            f.seek(6, 1)
            mode = struct.unpack("<I", f.read(4))[0]
            f.seek(12, 1)
            start_lba, total_length = struct.unpack("<II", f.read(8))
            f.seek(16, 1)
            sector_size_value = struct.unpack("<I", f.read(4))[0]
            sector_size = {0: 2048, 1: 2336, 2: 2352}[sector_size_value]
            f.seek(29, 1)
            if version != _CDI_V2:
                f.seek(5, 1)
                temp = struct.unpack("<I", f.read(4))[0]
                if temp == 0xFFFFFFFF:
                    f.seek(78, 1)
            header_position = f.tell()
            tracks.append(dict(pregap_length=pregap_length, length=tlength, mode=mode,
                                start_lba=start_lba, total_length=total_length,
                                sector_size=sector_size, data_position=data_position))
            data_position += total_length * sector_size
            f.seek(header_position, 0)
        f.seek(4, 1)
        f.seek(8, 1)
        if version != _CDI_V2:
            f.seek(1, 1)
    return tracks


class _CDIReader:
    """Presents the data track of a .cdi as a flat, ISO9660-relative byte
    stream, translating on the fly -- no intermediate ISO file is written."""

    def __init__(self, path, mode="rb"):
        self._f = open(path, mode)
        tracks = _parse_cdi_tracks(self._f)
        data_tracks = [t for t in tracks if t["mode"] in (1, 2)]
        if not data_tracks:
            raise DiscFormatError("no data track found in this .cdi")
        self._track = max(data_tracks, key=lambda t: t["start_lba"])
        if self._track["sector_size"] != 2336:
            raise DiscFormatError(
                f"unsupported sector size {self._track['sector_size']} "
                "(only mode2/2336-byte-sector GD-ROM data tracks are supported)"
            )
        self.start_lba = self._track["start_lba"]
        self._base = self._track["data_position"] + self._track["pregap_length"] * 2336

    def read(self, iso_offset, length):
        out = bytearray()
        pos = iso_offset
        remaining = length
        while remaining > 0:
            sector_index = pos // SECTOR
            sector_off = pos % SECTOR
            take = min(remaining, SECTOR - sector_off)
            self._f.seek(self._base + sector_index * 2336 + 8 + sector_off)
            out += self._f.read(take)
            pos += take
            remaining -= take
        return bytes(out)

    def write(self, iso_offset, data):
        """In-place overwrite only -- does not support changing a file's length
        (that would require rewriting the FAT/directory extents, which this
        never does). The caller is responsible for writing to a COPY of the
        disc image, never the original."""
        pos = iso_offset
        remaining = len(data)
        src_off = 0
        while remaining > 0:
            sector_index = pos // SECTOR
            sector_off = pos % SECTOR
            take = min(remaining, SECTOR - sector_off)
            self._f.seek(self._base + sector_index * 2336 + 8 + sector_off)
            self._f.write(data[src_off:src_off + take])
            pos += take
            src_off += take
            remaining -= take

    def close(self):
        self._f.close()


class _ISOReader:
    """A plain ISO9660 image (already-extracted data track) -- identity mapping."""

    def __init__(self, path, mode="rb"):
        self._f = open(path, mode)
        self.start_lba = 0

    def read(self, iso_offset, length):
        self._f.seek(iso_offset)
        return self._f.read(length)

    def write(self, iso_offset, data):
        self._f.seek(iso_offset)
        self._f.write(data)

    def close(self):
        self._f.close()


def open_disc(path, writable=False):
    mode = "r+b" if writable else "rb"
    lower = path.lower()
    if lower.endswith(".cdi"):
        return _CDIReader(path, mode)
    return _ISOReader(path, mode)


def _read_dirrec(entry_bytes, lba_offset):
    length = entry_bytes[0]
    if length == 0:
        return None, 0
    ext_lba = struct.unpack_from("<I", entry_bytes, 2)[0] - lba_offset
    ext_size = struct.unpack_from("<I", entry_bytes, 10)[0]
    flags = entry_bytes[25]
    name_len = entry_bytes[32]
    name = entry_bytes[33:33 + name_len]
    return dict(lba=ext_lba, size=ext_size, is_dir=bool(flags & 0x02), name=name), length


def _decode_name(raw):
    name = raw.decode("ascii", errors="replace")
    if name in ("\x00", "\x01"):
        return name
    return name.split(";")[0] if ";" in name else name


def _walk(reader, lba, size, path, out):
    data = reader.read(lba * SECTOR, size)
    off = 0
    while off < len(data):
        entry, length = _read_dirrec(data[off:off + 256], reader.start_lba)
        if entry is None:
            off = ((off // SECTOR) + 1) * SECTOR
            continue
        name = _decode_name(entry["name"])
        if name not in ("\x00", "\x01"):
            full = path.rstrip("/") + "/" + name
            out.append((full, entry["lba"], entry["size"], entry["is_dir"]))
            if entry["is_dir"]:
                _walk(reader, entry["lba"], entry["size"], full, out)
        off += length


def list_files(reader):
    """Return [(path, lba, size, is_dir), ...] for the whole ISO9660 filesystem."""
    pvd = reader.read(16 * SECTOR, SECTOR)
    if pvd[1:6] != b"CD001":
        raise DiscFormatError("not a valid ISO9660 image (no CD001 PVD at sector 16)")
    root_lba = struct.unpack_from("<I", pvd, 156 + 2)[0] - reader.start_lba
    root_size = struct.unpack_from("<I", pvd, 156 + 10)[0]
    out = []
    _walk(reader, root_lba, root_size, "", out)
    return out


def read_file(reader, files, target_name):
    """Extract one file's raw bytes by name (case-insensitive, path or basename match)."""
    for full, lba, size, is_dir in files:
        if is_dir:
            continue
        base = full.rsplit("/", 1)[-1]
        if base.upper() == target_name.upper() or full.upper() == target_name.upper():
            return reader.read(lba * SECTOR, size)
    raise FileNotFoundError(target_name)


# ---- PRS decompression (Sega's LZ77 variant used throughout PSO's data files) ----

def prs_decompress(data):
    out = bytearray()
    pos, n, bits = 0, len(data), 0

    def get_u8():
        nonlocal pos
        b = data[pos]
        pos += 1
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
            if read_bit():
                out.append(get_u8())
                continue
            if read_bit():
                a = get_u8() | (get_u8() << 8)
                off = a >> 3
                if off == 0:
                    break
                offset = off - 0x2000
                count = a & 7
                count = count + 2 if count else get_u8() + 1
            else:
                count = (read_bit() << 1 | read_bit()) + 2
                offset = get_u8() - 0x100
            read_off = len(out) + offset
            if not (0 <= read_off < len(out)):
                raise ValueError("bad PRS backreference")
            for _ in range(count):
                out.append(out[read_off])
                read_off += 1
    except IndexError:
        pass
    return bytes(out)


# ---- AFS archive (a flat table of offset/size pairs) ----

def parse_afs(data):
    if data[0:4] != b"AFS\x00":
        raise DiscFormatError("not an AFS archive")
    count = struct.unpack_from("<I", data, 4)[0]
    return [struct.unpack_from("<II", data, 8 + i * 8) for i in range(count)]


# ---- PVM texture container (PRS-compressed; wraps one or more PVR textures) ----

import re
_PRINTABLE_RUN = re.compile(rb"[\x20-\x7e]{3,}")


def parse_pvm(dec):
    """Return (list_of_names, tex_data_start) for a decompressed PVM blob. See
    docs/REFERENCE.md's Mag-icon-extraction notes for why names are found by
    longest-printable-run rather than a fixed-offset field: the exact binary
    layout of each entry depends on a flags bitfield we don't decode, but the
    entry stride and the name text are both recoverable without it."""
    if dec[0:4] != b"PVMH":
        return None
    hlen = struct.unpack_from("<I", dec, 4)[0]
    count = struct.unpack_from("<H", dec, 10)[0]
    tex_data_start = 8 + hlen
    if count == 0:
        return [], tex_data_start
    entry_table = dec[12:tex_data_start]
    stride = len(entry_table) // count
    names = []
    for i in range(count):
        entry = entry_table[i * stride:(i + 1) * stride]
        runs = _PRINTABLE_RUN.findall(entry)
        names.append(max(runs, key=len).decode("ascii", errors="replace") if runs else "")
    return names, tex_data_start


# ---- PVR texture (the specific variant used for these icons: square, twiddled, ARGB4444) ----

def _detwiddle_xy(size):
    bits = size.bit_length() - 1
    xy = [None] * (size * size)
    for i in range(size * size):
        x = y = 0
        for b in range(bits):
            x |= ((i >> (2 * b)) & 1) << b
            y |= ((i >> (2 * b + 1)) & 1) << b
        xy[i] = (x, y)
    return xy


def decode_pvrt_twiddled(pvrt_chunk, treat_black_as_transparent=False):
    """Returns (width, height, rgba8_bytes). Handles the two square/twiddled/
    non-mipmapped pixel formats seen on this disc's item icons: ARGB4444
    (px_fmt=2, has real alpha -- used by the small 64x64 mag/mob icons) and
    RGB565 (px_fmt=1, opaque -- used by the larger 256x256 "floating item on
    a black backdrop" weapon renders, where `treat_black_as_transparent`
    recovers a usable alpha channel). Raises DiscFormatError for any other
    PVR variant (VQ/palette/mipmap/non-square) -- not needed for these icons
    and not implemented."""
    if pvrt_chunk[0:4] != b"PVRT":
        raise DiscFormatError("not a PVRT chunk")
    px_fmt, data_fmt = pvrt_chunk[8], pvrt_chunk[9]
    width, height = struct.unpack_from("<HH", pvrt_chunk, 12)
    if not (px_fmt in (1, 2) and data_fmt == 1 and width == height):
        raise DiscFormatError(
            f"unsupported PVR variant px_fmt={px_fmt} data_fmt={data_fmt} {width}x{height}"
        )
    pixels = struct.unpack_from(f"<{width*height}H", pvrt_chunk, 16)
    rgba = bytearray(width * height * 4)
    for i, (x, y) in enumerate(_detwiddle_xy(width)):
        px = pixels[i]
        if px_fmt == 2:
            a, r, g, b = (px >> 12) & 0xF, (px >> 8) & 0xF, (px >> 4) & 0xF, px & 0xF
            r, g, b, a = r * 17, g * 17, b * 17, a * 17
        else:
            r, g, b = (px >> 11) & 0x1F, (px >> 5) & 0x3F, px & 0x1F
            r, g, b = r * 255 // 31, g * 255 // 63, b * 255 // 31
            a = 0 if (treat_black_as_transparent and r == 0 and g == 0 and b == 0) else 255
        o = (y * width + x) * 4
        rgba[o:o + 4] = bytes((r, g, b, a))
    return width, height, bytes(rgba)


def write_png(path, width, height, rgba_bytes):
    def chunk(tag, payload):
        c = tag + payload
        return struct.pack(">I", len(payload)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw += rgba_bytes[y * stride:(y + 1) * stride]
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))
