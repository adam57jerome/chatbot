from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.utils.json_safe import to_jsonable


class FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping


def test_to_jsonable_handles_datetime_decimal_row_and_uuid():
    payload = {
        "when": datetime(2026, 2, 12, 10, 30, 0),
        "day": date(2026, 2, 12),
        "score": Decimal("14.5"),
        "uid": uuid4(),
        "row": FakeRow({"a": 1, "b": Decimal("2.0")}),
    }

    converted = to_jsonable(payload)
    dumped = json.dumps(converted, ensure_ascii=False, indent=2)

    assert "2026-02-12T10:30:00" in dumped
    assert "2026-02-12" in dumped
    assert converted["score"] == 14.5
    assert isinstance(converted["uid"], str)
    assert converted["row"]["b"] == 2.0
