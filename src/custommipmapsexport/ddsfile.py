"""
DDS File library.

================

This library can be used to parse and save DDS
(`DirectDraw Surface <https://en.wikipedia.org/wiki/DirectDraw_Surface>`)
files.

The initial version was written by::

    Alexey Borzenkov (snaury@gmail.com)

All the initial work credits go to him! Thank you :)

This version uses structs instead of ctypes.

DDS Format
----------

::

    [DDS ][SurfaceDesc][Data]

    [SurfaceDesc]:: (everything is uint32)
        Size
        Flags
        Height
        Width
        PitchOrLinearSize
        Depth
        MipmapCount
        Reserved1 * 11
        [PixelFormat]::
            Size
            Flags
            FourCC
            RGBBitCount
            RBitMask
            GBitMask
            BBitMask
            ABitMask
        [Caps]::
            Caps1
            Caps2
            Reserved1 * 2
        Reserverd2

"""

from struct import calcsize, pack, unpack

from custommipmapsexport.logger import logger

# DDSURFACEDESC2 dwFlags
DDSD_CAPS = 0x00000001
DDSD_HEIGHT = 0x00000002
DDSD_WIDTH = 0x00000004
DDSD_PITCH = 0x00000008
DDSD_PIXELFORMAT = 0x00001000
DDSD_MIPMAPCOUNT = 0x00020000
DDSD_LINEARSIZE = 0x00080000
DDSD_DEPTH = 0x00800000

# DDPIXELFORMAT dwFlags
DDPF_ALPHAPIXELS = 0x00000001
DDPF_FOURCC = 0x00000004
DDPF_RGB = 0x00000040
DDPF_LUMINANCE = 0x00020000

# DDSCAPS2 dwCaps1
DDSCAPS_COMPLEX = 0x00000008
DDSCAPS_TEXTURE = 0x00001000
DDSCAPS_MIPMAP = 0x00400000

# DDSCAPS2 dwCaps2
DDSCAPS2_CUBEMAP = 0x00000200
DDSCAPS2_CUBEMAP_POSITIVEX = 0x00000400
DDSCAPS2_CUBEMAP_NEGATIVEX = 0x00000800
DDSCAPS2_CUBEMAP_POSITIVEY = 0x00001000
DDSCAPS2_CUBEMAP_NEGATIVEY = 0x00002000
DDSCAPS2_CUBEMAP_POSITIVEZ = 0x00004000
DDSCAPS2_CUBEMAP_NEGATIVEZ = 0x00008000
DDSCAPS2_VOLUME = 0x00200000

# Common FOURCC codes
DDS_DXTN = 0x00545844
DDS_DXT1 = 0x31545844
DDS_DXT2 = 0x32545844
DDS_DXT3 = 0x33545844
DDS_DXT4 = 0x34545844
DDS_DXT5 = 0x35545844


def dxt_to_str(dxt):
    """Convert a DXT format to a string."""
    if dxt == DDS_DXT1:
        return "s3tc_dxt1"
    elif dxt == DDS_DXT2:
        return "s3tc_dxt2"
    elif dxt == DDS_DXT3:
        return "s3tc_dxt3"
    elif dxt == DDS_DXT4:
        return "s3tc_dxt4"
    elif dxt == DDS_DXT5:
        return "s3tc_dxt5"
    elif dxt == 0:
        return "rgba"
    elif dxt == 1:
        return "alpha"
    elif dxt == 2:  # noqa: PLR2004
        return "luminance"
    elif dxt == 3:  # noqa: PLR2004
        return "luminance_alpha"


def str_to_dxt(dxt):
    """Convert a string to a DXT format."""
    if dxt == "s3tc_dxt1":
        return DDS_DXT1
    if dxt == "s3tc_dxt2":
        return DDS_DXT2
    if dxt == "s3tc_dxt3":
        return DDS_DXT3
    if dxt == "s3tc_dxt4":
        return DDS_DXT4
    if dxt == "s3tc_dxt5":
        return DDS_DXT5
    if dxt == "rgba":
        return 0
    if dxt == "alpha":
        return 1
    if dxt == "luminance":
        return 2
    if dxt == "luminance_alpha":
        return 3


def align_value(val, b):
    """Align the value to the nearest multiple of b."""
    return val + (-val % b)


def check_flags(val, fl):
    """Check if the flags are set in the value."""
    return (val & fl) == fl


def dxt_size(w, h, dxt):
    """Calculate the size of a DXT compressed image."""
    w = max(1, w // 4)
    h = max(1, h // 4)
    if dxt == DDS_DXT1:
        return w * h * 8
    elif dxt in (DDS_DXT2, DDS_DXT3, DDS_DXT4, DDS_DXT5):
        return w * h * 16
    return -1


class QueryDict(dict):  # type: ignore[type-arg]
    """A dictionary that allows for attribute-style access."""

    def __getattr__(self, attr):
        try:
            return self.__getitem__(attr)
        except KeyError:
            try:
                return super().__getattr__(attr)  # type: ignore[misc]
            except AttributeError:
                raise KeyError(attr) from None

    def __setattr__(self, attr, value):
        self.__setitem__(attr, value)


class DDSError(Exception):
    """Exception raised for errors in the DDS file format."""

    pass


class DDSFile:
    """DDS file class."""

    fields = (
        ("size", 0),
        ("flags", 1),
        ("height", 2),
        ("width", 3),
        ("pitchOrLinearSize", 4),
        ("depth", 5),
        ("mipmapCount", 6),
        ("pf_size", 18),
        ("pf_flags", 19),
        ("pf_fourcc", 20),
        ("pf_rgbBitCount", 21),
        ("pf_rBitMask", 22),
        ("pf_gBitMask", 23),
        ("pf_bBitMask", 24),
        ("pf_aBitMask", 25),
        ("caps1", 26),
        ("caps2", 27),
    )

    def __init__(self, filename=None):
        super().__init__()
        self._dxt = 0
        self._fmt = None
        self.meta = meta = QueryDict()
        self.count = 0
        self.images = []
        self.images_size = []
        for field, _ in DDSFile.fields:
            meta[field] = 0
        if filename:
            self.load(filename)
        else:
            self.filename = None

    def load(self, filename):
        self.filename = filename
        with open(filename, "rb") as fd:
            data = fd.read()

        # ensure magic
        if data[:4] != b"DDS ":
            msg = "Invalid magic header"
            raise DDSError(msg)

        # read header
        fmt = "I" * 31
        fmt_size = calcsize(fmt)
        pf_size = calcsize("I" * 8)
        header, data = data[4 : 4 + fmt_size], data[4 + fmt_size :]
        if len(header) != fmt_size:
            msg = "Truncated header in"
            raise DDSError(msg)

        # depack
        unpacked_header = unpack(fmt, header)
        meta = self.meta
        for name, index in DDSFile.fields:
            meta[name] = unpacked_header[index]

        # check header validity
        if meta.size != fmt_size:
            msg = f"Invalid header size ({meta.size} instead of {fmt_size})"
            raise DDSError(msg)
        if meta.pf_size != pf_size:
            msg = f"Invalid pixelformat size ({meta.pf_size} instead of {pf_size})"
            raise DDSError(msg)
        if not check_flags(meta.flags, DDSD_CAPS | DDSD_PIXELFORMAT | DDSD_WIDTH | DDSD_HEIGHT):
            msg = "Not enough flags"
            raise DDSError(msg)
        if not check_flags(meta.caps1, DDSCAPS_TEXTURE):
            msg = "Not a DDS texture"
            raise DDSError(msg)

        self.count = 1
        if check_flags(meta.flags, DDSD_MIPMAPCOUNT):
            if not check_flags(meta.caps1, DDSCAPS_COMPLEX | DDSCAPS_MIPMAP):
                msg = "Invalid mipmap without flags"
                raise DDSError(msg)
            self.count = meta.mipmapCount

        hasrgb = check_flags(meta.pf_flags, DDPF_RGB)
        hasalpha = check_flags(meta.pf_flags, DDPF_ALPHAPIXELS)
        hasluminance = check_flags(meta.pf_flags, DDPF_LUMINANCE)
        dxt = block = pitch = 0
        bpp = meta.pf_rgbBitCount if hasrgb or hasalpha or hasluminance else None
        if hasrgb and hasluminance:
            msg = "File have RGB and Luminance"
            raise DDSError(msg)

        if hasrgb:
            dxt = 0
        elif hasalpha and not hasluminance:
            dxt = 1
        elif hasluminance and not hasalpha:
            dxt = 2
        elif hasalpha:
            dxt = 3
        elif check_flags(meta.pf_flags, DDPF_FOURCC):
            dxt = meta.pf_fourcc
            if dxt not in (DDS_DXT1, DDS_DXT2, DDS_DXT3, DDS_DXT4, DDS_DXT5):
                msg = "Unsupported FOURCC"
                raise DDSError(msg)
        else:
            msg = "Unsupported format specified"
            raise DDSError(msg)

        if bpp:
            block = align_value(bpp, 8) // 8
            pitch = align_value(block * meta.width, 4)

        if check_flags(meta.flags, DDSD_LINEARSIZE):
            if dxt in (0, 1, 2, 3):
                size = pitch * meta.height
            else:
                size = dxt_size(meta.width, meta.height, dxt)

        w = meta.width
        h = meta.height
        images = self.images
        images_size = self.images_size
        for i in range(self.count):
            if dxt in (0, 1, 2, 3):
                size = align_value(block * w, 4) * h
            else:
                size = dxt_size(w, h, dxt)
            image, data = data[:size], data[size:]
            if len(image) < size:
                msg = f"Truncated image for mipmap {i}"
                raise DDSError(msg)
            images_size.append((w, h))
            images.append(image)
            if w == 1 and h == 1:
                break
            w = max(1, w // 2)
            h = max(1, h // 2)

        if len(images) == 0:
            msg = "No images available"
            raise DDSError(msg)
        if len(images) < self.count:
            msg = "Not enough images"
            raise DDSError(msg)

        self._dxt = dxt

    def save(self, filename):
        if len(self.images) == 0:
            msg = "No images to save"
            raise DDSError(msg)

        fields = dict(DDSFile.fields)
        fields_keys = list(fields.keys())
        fields_index = list(fields.values())
        mget = self.meta.get
        header = []
        for idx in range(31):
            if idx in fields_index:
                value = mget(fields_keys[fields_index.index(idx)], 0)
            else:
                value = 0
            header.append(value)

        with open(filename, "wb") as fd:
            fd.write(b"DDS ")
            fd.write(pack("I" * 31, *header))
            for image in self.images:
                fd.write(image)

    def add_image(self, level, bpp, fmt, width, height, data):
        if bpp != 32:  # noqa: PLR2004
            msg = "Bits per pixel (bpp) must be 32."
            raise ValueError(msg)
        if fmt not in ("rgb", "rgba", "dxt1", "dxt2", "dxt3", "dxt4", "dxt5"):
            msg = "Format must be one of: rgb, rgba, dxt1, dxt2, dxt3, dxt4, dxt5."
            raise ValueError(msg)
        if level < 0:
            msg = "Level must be non-negative."
            raise ValueError(msg)
        if width <= 0 or height <= 0:
            msg = "Width and height must be positive integers."
            raise ValueError(msg)

        meta = self.meta
        images = self.images
        if len(images) == 0:
            # first image, set defaults !
            for k in meta.keys():
                meta[k] = 0

            self._fmt = fmt
            meta.size = calcsize("I" * 31)
            meta.pf_size = calcsize("I" * 8)
            meta.pf_flags = 0
            meta.caps1 = DDSCAPS_TEXTURE

            meta.flags = DDSD_CAPS | DDSD_PIXELFORMAT | DDSD_WIDTH | DDSD_HEIGHT
            meta.width = width
            meta.height = height
            meta.flags |= DDSD_LINEARSIZE
            meta.pitchOrLinearSize = len(data)

            self._initialize_pixel_format(meta, 0xFF000000)
            if fmt in ("rgb", "rgba"):
                meta.pf_flags |= DDPF_RGB
                self._initialize_pixel_format(meta, 0x00000000)
                if fmt == "rgba":
                    meta.pf_flags |= DDPF_ALPHAPIXELS
                    meta.pf_aBitMask = 0xFF000000
            else:
                meta.pf_flags |= DDPF_FOURCC
                if fmt == "dxt1":
                    meta.pf_fourcc = DDS_DXT1
                elif fmt == "dxt2":
                    meta.pf_fourcc = DDS_DXT2
                elif fmt == "dxt3":
                    meta.pf_fourcc = DDS_DXT3
                elif fmt == "dxt4":
                    meta.pf_fourcc = DDS_DXT4
                elif fmt == "dxt5":
                    meta.pf_fourcc = DDS_DXT5

            images.append(data)
        else:
            if level != len(images):
                msg = f"Level {level} does not match the number of images {len(images)}"
                raise DDSError(msg)
            if fmt != self._fmt:
                msg = f"Format {fmt} does not match the expected format {self._fmt}"
                raise DDSError(msg)

            images.append(data)

            meta.flags |= DDSD_MIPMAPCOUNT
            meta.caps1 |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
            meta.mipmapCount = len(images)

    def _initialize_pixel_format(self, meta, arg1):
        meta.pf_rgbBitCount = 32
        meta.pf_rBitMask = 0x00FF0000
        meta.pf_gBitMask = 0x0000FF00
        meta.pf_bBitMask = 0x000000FF
        meta.pf_aBitMask = arg1

    def __repr__(self):
        return f"<DDSFile filename={self.filename} size={self.size} dxt={self.dxt} len(images)=>{len(self.images)}"

    def _get_size(self):
        meta = self.meta
        return meta.width, meta.height

    def _set_size(self, size):
        self.meta.update({"width": size[0], "height": size[1]})

    size = property(_get_size, _set_size)

    def _get_dxt(self):
        return dxt_to_str(self._dxt)

    def _set_dxt(self, dxt):
        self._dxt = str_to_dxt(dxt)

    dxt = property(_get_dxt, _set_dxt)


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        logger.info("Usage: python ddsfile.py <file1> <file2> ...")
        sys.exit(0)
    for filename in sys.argv[1:]:
        logger.info("=== Loading", filename)
        try:
            dds = DDSFile(filename=filename)
            logger.info(dds)
            dds.save("bleh.dds")
        except OSError as e:
            logger.info("ERR>", e)
        except DDSError as e:
            logger.info("DDS>", e)
