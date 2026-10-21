from __future__ import annotations

import codecs
import encodings
from functools import lru_cache
from typing import TYPE_CHECKING, Optional, Tuple, cast

if TYPE_CHECKING:
    from typing_extensions import Buffer

from ._frostwork import autodetect_encoding as _autodetect_encoding
from ._frostwork import bom_encoding as _bom_encoding
from ._frostwork import declared_encoding as _declared_encoding
from ._frostwork import decode as _decode
from ._frostwork import detect as _detect
from ._frostwork import resolve_label as _resolve_label

__all__ = [
    "autodetect_encoding",
    "bom_encoding",
    "codec_name",
    "declared_encoding",
    "decode",
    "detect",
    "resolve_label",
]

# WHATWG encoding name -> Python codec name, for every encoding of the Encoding Standard.
_CODEC_NAMES = {
    "UTF-8": "utf-8",
    "IBM866": "cp866",
    **{f"ISO-8859-{n}": f"iso8859-{n}" for n in (2, 3, 4, 5, 6, 7, 8, 10, 13, 14, 15, 16)},
    # Same index as ISO-8859-8; the two differ only in how a browser lays out bidirectional text.
    "ISO-8859-8-I": "iso8859-8",
    "KOI8-R": "koi8-r",
    "KOI8-U": "koi8-u",
    "macintosh": "mac-roman",
    "windows-874": "cp874",
    **{f"windows-125{n}": f"cp125{n}" for n in range(9)},
    "x-mac-cyrillic": "mac-cyrillic",
    "GBK": "gbk",
    "gb18030": "gb18030",
    "Big5": "big5hkscs",
    "EUC-JP": "euc_jp",
    "ISO-2022-JP": "iso2022_jp",
    "Shift_JIS": "cp932",
    "EUC-KR": "cp949",
    "replacement": "replacement",
    "UTF-16BE": "utf-16-be",
    "UTF-16LE": "utf-16-le",
    "x-user-defined": "x-user-defined",
}


@lru_cache(maxsize=256)
def resolve_label(label: str) -> Optional[str]:
    """The WHATWG name of the encoding charset *label* names (``"cp874"`` → ``"windows-874"``), or
    ``None`` if it names none (``"cp437"``).

    *label* can be a WHATWG label or a Python codec name, e.g. Scrapy's ``response.encoding``.
    """
    return _resolve_label(label)


def codec_name(label: str) -> Optional[str]:
    """The Python codec name of the encoding *label* names (``"latin1"`` → ``"cp1252"``), or ``None``
    if :func:`resolve_label` resolves it to no WHATWG encoding.

    Where a Python codec decodes differently from the WHATWG decoder, as with ``euc_jp``, the name
    still identifies the WHATWG encoding to every function here and to :func:`frostwork.extract`; use
    :func:`decode` to decode with it.
    """
    name = resolve_label(label)
    return None if name is None else _CODEC_NAMES[name]


def detect(body: bytes, label: Optional[str] = None, *, url: Optional[str] = None) -> Tuple[str, int]:
    """The encoding of *body* and the length of the BOM at its start, 0 if none.

    The encoding is the first answer of :func:`bom_encoding`, *label*, :func:`declared_encoding` and
    :func:`autodetect_encoding`, in that order, as in :func:`frostwork.detect_encoding`.
    """
    return _detect(body, None if label is None else resolve_label(label), url=url)


def bom_encoding(body: bytes) -> Optional[Tuple[str, int]]:
    """The encoding the byte order mark at the start of *body* names, and the length of that BOM.

    A UTF-16 document that starts with an XML declaration and no BOM is recognized too, with length
    0. A UTF-32 BOM is not a BOM, as in browsers.
    """
    return _bom_encoding(body)


def declared_encoding(body: bytes) -> Optional[str]:
    """The encoding a ``<meta>`` tag or an XML declaration in *body* declares, as a browser finds it.

    A declaration of a UTF-16 encoding gives ``"UTF-8"``, and of ``x-user-defined``,
    ``"windows-1252"``.
    """
    return _declared_encoding(body)


def autodetect_encoding(body: bytes, *, url: Optional[str] = None) -> str:
    """``"UTF-8"`` if *body* is valid UTF-8, else the encoding guessed from its bytes and from the
    top-level domain of *url*, like Firefox does for a page that declares none."""
    return _autodetect_encoding(body, url=url)


def decode(body: bytes, encoding: str) -> str:
    """*body* decoded with the WHATWG decoder of *encoding*, a WHATWG label or a Python codec name,
    replacing invalid input with U+FFFD.

    A BOM is decoded like any other bytes; strip the length :func:`detect` returns first. Raises
    :exc:`LookupError` if :func:`resolve_label` cannot resolve *encoding*.
    """
    name = resolve_label(encoding)
    if name is None:
        raise LookupError(f"unknown encoding: {encoding}")
    if name == "UTF-8":
        # Python's UTF-8 decoder replaces invalid input as WHATWG's does, and builds the str directly.
        return body.decode("utf-8", "replace")
    if name in _SINGLE_BYTE:
        return codecs.charmap_decode(body, "strict", _single_byte_table(name))[0]  # type: ignore[arg-type]
    return _decode(body, name)


# https://encoding.spec.whatwg.org/#legacy-single-byte-encodings, plus x-user-defined, whose decoder maps
# each byte on its own too.
_SINGLE_BYTE = frozenset(
    name
    for name in _CODEC_NAMES
    if name.startswith(("ISO-8859-", "windows-", "KOI8-"))
    or name in {"IBM866", "macintosh", "x-mac-cyrillic", "x-user-defined"}
)


@lru_cache(maxsize=None)
def _single_byte_table(name: str) -> str:
    """The decoder of the single-byte encoding *name*, as a table for :func:`codecs.charmap_decode`,
    which builds the str faster than the native decoder can hand one over."""
    return _decode(bytes(range(256)), name)


_X_USER_DEFINED_DECODING = "".join(chr(b) if b < 0x80 else chr(0xF700 + b) for b in range(256))
_X_USER_DEFINED_ENCODING = codecs.charmap_build(_X_USER_DEFINED_DECODING)


def _x_user_defined_encode(text: str, errors: str = "strict") -> Tuple[bytes, int]:
    return codecs.charmap_encode(text, errors, _X_USER_DEFINED_ENCODING)


def _x_user_defined_decode(data: Buffer, errors: str = "strict", /) -> Tuple[str, int]:
    return codecs.charmap_decode(data, errors, _X_USER_DEFINED_DECODING)  # type: ignore[arg-type]


def _replacement_encode(text: str, errors: str = "strict") -> Tuple[bytes, int]:
    return codecs.utf_8_encode(text, errors)


def _replacement_decode(data: Buffer, errors: str = "strict", /) -> Tuple[str, int]:
    data = bytes(data)
    if not data:
        return "", 0
    error = UnicodeDecodeError("replacement", data, 0, len(data), "the encoding decodes nothing")
    text, _ = codecs.lookup_error(errors)(error)
    return cast(str, text), len(data)


_CODECS = {
    "x_user_defined": codecs.CodecInfo(
        _x_user_defined_encode, _x_user_defined_decode, name="x-user-defined"
    ),
    "replacement": codecs.CodecInfo(_replacement_encode, _replacement_decode, name="replacement"),
}
codecs.register(lambda name: _CODECS.get(encodings.normalize_encoding(name)))
