"""Check the M0 contract artifacts; this does not execute the product scenarios."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def reject_non_integer(value):
    raise ValueError(f"not an integer literal: {value}")


def raw_message(data):
    if not data.endswith(b"\n") or data.count(b"\n") != 1 or b"\r" in data or len(data) > 8192:
        raise ValueError("invalid frame boundary")
    return json.loads(data[:-1].decode("utf-8"), object_pairs_hook=unique_object,
                      parse_float=reject_non_integer, parse_constant=reject_non_integer)


def check():
    schema = read_json("spec/wire.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    examples = read_json("spec/wire.examples.json")
    catalog = read_json("spec/scenarios.json")
    errors = []
    names = set()
    for example in examples:
        name = example["name"]
        if name in names:
            errors.append(f"duplicate example: {name}")
        names.add(name)
        expected = example["expected_valid"]
        if type(expected) is not bool:
            errors.append(f"{name}: expected_valid must be boolean")
        elif validator.is_valid(example["message"]) != expected:
            errors.append(f"{name}: schema result differs from expected_valid")
    if not examples or not any(e["expected_valid"] is True for e in examples):
        errors.append("missing valid wire examples")
    if not any(e["expected_valid"] is False for e in examples):
        errors.append("missing invalid wire examples")

    raw_examples = read_json("spec/wire.raw-examples.json")
    raw_names = set()
    for example in raw_examples:
        if example["name"] in raw_names:
            errors.append("duplicate raw example name")
        raw_names.add(example["name"])
        try:
            actual = validator.is_valid(raw_message(bytes.fromhex(example["frame_hex"])))
        except (ValueError, UnicodeError):
            actual = False
        if type(example["expected_valid"]) is not bool or actual != example["expected_valid"]:
            errors.append(f"raw {example['name']}: unexpected result")

    protocol = (ROOT / "docs/PROTOCOL.md").read_text(encoding="utf-8")
    doc_examples = re.findall(r"```json\n(.*?)\n```", protocol, re.DOTALL)
    for index, raw in enumerate(doc_examples):
        if not validator.is_valid(raw_message((raw + "\n").encode("utf-8"))):
            errors.append(f"protocol example {index}: invalid")
    invariants = set(re.findall(r"^## (I\d+)\b", protocol, re.MULTILINE))
    scenario_doc = (ROOT / "docs/SCENARIOS.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| ([SC]\d+) \|", scenario_doc, re.MULTILINE))
    scenarios = catalog["scenarios"]
    ids = {s["id"] for s in scenarios}
    if len(ids) != len(scenarios) or not ids:
        errors.append("scenario IDs must be unique and nonempty")
    if documented != ids:
        errors.append(f"scenario table and catalog differ: {sorted(documented ^ ids)}")
    if set(catalog["primary_demo_ids"]) != {"S01", "S02", "S03"}:
        errors.append("primary demo scope differs from M0")
    allowed_levels = {"JVM_UNIT", "POS_INTEGRATION", "ANDROID_MANUAL"}
    for scenario in scenarios:
        sid = scenario["id"]
        if not scenario["invariants"] or not set(scenario["invariants"]) <= invariants:
            errors.append(f"{sid}: unknown or missing invariant")
        if not scenario["execution_levels"] or not set(scenario["execution_levels"]) <= allowed_levels:
            errors.append(f"{sid}: unknown or missing execution level")
        if not scenario["trigger"] or not scenario["observations"]:
            errors.append(f"{sid}: trigger and observations are required")
        if sid == "S03" and scenario["execution_levels"] != ["ANDROID_MANUAL"]:
            errors.append("S03: process death needs Android evidence")
    for mutation in catalog["mutations"]:
        if not mutation["detected_by"] or not set(mutation["detected_by"]) <= ids:
            errors.append(f"{mutation['id']}: missing or unknown detecting scenario")

    documents = [ROOT / "README.md", ROOT / "AGENTS.md", *sorted((ROOT / "docs").rglob("*.md"))]
    links = 0
    for document in documents:
        body = document.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
            if "://" in target or target.startswith("#"):
                continue
            links += 1
            path = target.split("#", 1)[0]
            if path and not (document.parent / path).exists():
                errors.append(f"{document.relative_to(ROOT)}: missing link {target}")
    if errors:
        for error in errors:
            print(f"SPEC ERROR: {error}", file=sys.stderr)
        return 1
    print(f"SPEC CHECK OK: {len(examples)} wire examples, {len(raw_examples)} raw examples, "
          f"{len(doc_examples)} document examples, {len(scenarios)} scenario definitions, "
          f"{len(catalog['mutations'])} mutation plans, {links} local links")
    print("This command checks specification consistency only; runtime evidence is tracked in docs/CONTROL.md.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(check())
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"SPEC ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
