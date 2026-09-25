"""Opaque list cursors. The read API treats them as strings."""

import base64
import binascii
from datetime import datetime
from uuid import UUID

from switchboard_repositories.errors import InvalidCursor


def encode_cursor(moment: datetime, row_id: UUID) -> str:
    raw = f"{moment.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        moment_text, id_text = decoded.split("|", 1)
        moment = datetime.fromisoformat(moment_text)
        row_id = UUID(id_text)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise InvalidCursor("cursor is not valid") from exc
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise InvalidCursor("cursor is not valid")
    return moment, row_id
