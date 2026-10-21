from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    if sys.version_info >= (3, 12):
        from collections.abc import Buffer
    else:
        from typing_extensions import Buffer


def as_bytes(body: Buffer) -> bytes:
    """*body* as :class:`bytes`. Raises :exc:`TypeError` if it is not a bytes-like object."""
    return body if isinstance(body, bytes) else bytes(memoryview(body))


def as_scan_input(html: Union[Buffer, str]) -> Union[bytes, str]:
    """What the engine scans. `bytes` and `str` both cross the FFI boundary as-is — the native layer
    borrows a `str`'s UTF-8 view instead of allocating a second copy of the document (see the `Html`
    enum in `src/python.rs`), so a caller holding already-decoded text should NOT pre-encode it. Only
    the remaining bytes-likes need materializing."""
    return html if isinstance(html, str) else as_bytes(html)
