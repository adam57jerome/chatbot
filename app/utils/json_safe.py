from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def _is_sqlalchemy_row(obj: Any) -> bool:
    return hasattr(obj, "_mapping")


def _is_sqlalchemy_model(obj: Any) -> bool:
    try:
        from sqlalchemy.inspection import inspect as sa_inspect

        inspected = sa_inspect(obj)
        return hasattr(inspected, "mapper") and hasattr(inspected.mapper, "column_attrs")
    except Exception:
        return False


def _sqlalchemy_model_to_dict(obj: Any) -> dict[str, Any]:
    from sqlalchemy.inspection import inspect as sa_inspect

    mapper = sa_inspect(obj).mapper
    return {attr.key: getattr(obj, attr.key) for attr in mapper.column_attrs}


def to_jsonable(obj: Any, *, on_fallback=None, path: str = "root") -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, Enum):
        value = obj.value
        return to_jsonable(value, on_fallback=on_fallback, path=path)

    if _is_sqlalchemy_row(obj):
        try:
            return to_jsonable(dict(obj._mapping), on_fallback=on_fallback, path=path)
        except Exception:
            pass

    if _is_sqlalchemy_model(obj):
        try:
            return to_jsonable(_sqlalchemy_model_to_dict(obj), on_fallback=on_fallback, path=path)
        except Exception:
            pass

    if is_dataclass(obj):
        return to_jsonable(asdict(obj), on_fallback=on_fallback, path=path)

    if isinstance(obj, dict):
        safe: dict[str, Any] = {}
        for key, value in obj.items():
            key_str = str(key)
            safe[key_str] = to_jsonable(value, on_fallback=on_fallback, path=f"{path}.{key_str}")
        return safe

    if isinstance(obj, (list, tuple, set)):
        values = list(obj)
        return [to_jsonable(value, on_fallback=on_fallback, path=f"{path}[{idx}]") for idx, value in enumerate(values)]

    fallback_value = str(obj)
    if on_fallback:
        on_fallback(path, type(obj).__name__, fallback_value)
    return fallback_value


def find_first_non_serializable_path(obj: Any, *, path: str = "root") -> tuple[str, str] | None:
    if obj is None or isinstance(obj, (str, int, float, bool, datetime, date, Decimal, UUID, Enum)):
        return None

    if _is_sqlalchemy_row(obj):
        try:
            return find_first_non_serializable_path(dict(obj._mapping), path=path)
        except Exception:
            return (path, type(obj).__name__)

    if _is_sqlalchemy_model(obj):
        try:
            return find_first_non_serializable_path(_sqlalchemy_model_to_dict(obj), path=path)
        except Exception:
            return (path, type(obj).__name__)

    if is_dataclass(obj):
        return find_first_non_serializable_path(asdict(obj), path=path)

    if isinstance(obj, dict):
        for key, value in obj.items():
            result = find_first_non_serializable_path(value, path=f"{path}.{key}")
            if result:
                return result
        return None

    if isinstance(obj, (list, tuple, set)):
        for idx, value in enumerate(list(obj)):
            result = find_first_non_serializable_path(value, path=f"{path}[{idx}]")
            if result:
                return result
        return None

    return (path, type(obj).__name__)


def safe_json_dumps(obj: Any) -> str:
    return json.dumps(to_jsonable(obj), ensure_ascii=False, indent=2)
