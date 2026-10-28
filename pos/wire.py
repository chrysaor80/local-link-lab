"""Strict v1 wire parser. Runtime uses only the Python standard library."""
from __future__ import annotations

import json
import re

MAX_FRAME = 8192
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
CODES = {"INVALID_REQUEST", "UNSUPPORTED_VERSION", "ID_CONFLICT", "TEMPORARY_UNAVAILABLE", "POS_MISMATCH"}


class InvalidFrame(ValueError):
    def __init__(self, detail, code="INVALID_REQUEST", request_id=None):
        super().__init__(detail)
        self.code, self.request_id = code, request_id


def is_uuid(value):
    return isinstance(value, str) and UUID.fullmatch(value) is not None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidFrame("duplicate key")
        result[key] = value
    return result


def _non_integer(value):
    raise InvalidFrame("non-integer number")


def decode(frame: bytes):
    if len(frame) > MAX_FRAME or not frame.endswith(b"\n") or frame.count(b"\n") != 1 or b"\r" in frame:
        raise InvalidFrame("frame boundary")
    try:
        obj = json.loads(frame[:-1].decode("utf-8"), object_pairs_hook=_pairs,
                         parse_float=_non_integer, parse_constant=_non_integer)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise InvalidFrame("JSON encoding") from exc
    if not isinstance(obj, dict):
        raise InvalidFrame("object required")
    rid = obj.get("request_id") if is_uuid(obj.get("request_id")) else None
    if type(obj.get("version")) is not int or obj["version"] != 1:
        raise InvalidFrame("unsupported version", "UNSUPPORTED_VERSION", rid)
    typ = obj.get("type")
    fields = {
        "hello": {"version", "type"},
        "hello_ack": {"version", "type", "pos_db_id"},
        "submit_order": {"version", "type", "pos_db_id", "request_id", "order"},
        "ack": {"version", "type", "pos_db_id", "request_id", "receipt_id"},
        "error": {"version", "type", "pos_db_id", "request_id", "code"},
    }
    if not isinstance(typ, str) or typ not in fields or set(obj) != fields[typ]:
        raise InvalidFrame("message fields", request_id=rid)
    for field in ("pos_db_id", "receipt_id"):
        if field in obj and not is_uuid(obj[field]):
            raise InvalidFrame(field, request_id=rid)
    if "request_id" in obj and not is_uuid(obj["request_id"]):
        if not (typ == "error" and obj["request_id"] is None):
            raise InvalidFrame("request_id", request_id=rid)
    if typ == "submit_order":
        order = obj["order"]
        if not isinstance(order, dict) or set(order) != {"item_code", "quantity", "unit_price_krw"}:
            raise InvalidFrame("order fields", request_id=rid)
        item, qty, price = order["item_code"], order["quantity"], order["unit_price_krw"]
        if not isinstance(item, str) or not re.fullmatch(r"[A-Z0-9_-]{1,32}", item):
            raise InvalidFrame("item_code", request_id=rid)
        if type(qty) is not int or not 1 <= qty <= 99 or type(price) is not int or not 0 <= price <= 1_000_000_000:
            raise InvalidFrame("order numbers", request_id=rid)
    if typ == "error" and (not isinstance(obj["code"], str) or obj["code"] not in CODES):
        raise InvalidFrame("error code", request_id=rid)
    return obj


def encode(obj):
    data = (json.dumps(obj, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    decode(data)
    return data


def error(db_id, request_id, code):
    return dict(version=1, type="error", pos_db_id=db_id, request_id=request_id, code=code)
