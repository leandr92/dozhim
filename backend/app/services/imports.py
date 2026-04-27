from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.db.models import TargetObject

REQUIRED_COLUMNS = [
    "Дирекция",
    "Проект",
    "Статус КТ",
    "Количество КТ",
    "Количество этапов",
    "РП",
    "Куратор",
    "Последнее изменение",
    "Ссылка КТ",
    "Ссылка на проект",
    "Статус проекта в КТ",
    "Статус согласования",
]


@dataclass
class ImportValidationResult:
    is_valid: bool
    errors: list[str]
    diff: dict[str, int]


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {k: (v or "").strip() for k, v in row.items()}


def _read_csv(content: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    return [_normalize_row(r) for r in reader]


def _read_xlsx(content: bytes) -> list[dict[str, str]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.values)
    if not rows:
        return []
    headers = [str(c).strip() if c is not None else "" for c in rows[0]]
    data: list[dict[str, str]] = []
    for row in rows[1:]:
        item: dict[str, str] = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            raw = row[i] if i < len(row) else ""
            item[header] = "" if raw is None else str(raw).strip()
        data.append(_normalize_row(item))
    return data


def read_rows(filename: str, content: bytes) -> list[dict[str, str]]:
    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return _read_csv(content)
    if lowered.endswith(".xlsx") or lowered.endswith(".xls"):
        return _read_xlsx(content)
    raise ValueError("Unsupported file format")


def validate_and_diff(
    *,
    db: Session,
    project_id: str,
    rows: list[dict[str, str]],
) -> ImportValidationResult:
    errors: list[str] = []
    diff = {"create": 0, "update": 0, "no_change": 0}

    if not rows:
        return ImportValidationResult(is_valid=False, errors=["Файл пустой"], diff=diff)

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in rows[0]]
    if missing_columns:
        return ImportValidationResult(
            is_valid=False,
            errors=[f"Отсутствуют обязательные колонки: {', '.join(missing_columns)}"],
            diff=diff,
        )

    seen_keys: set[str] = set()
    for index, row in enumerate(rows, start=2):
        key = row.get("Ссылка на проект", "").strip()
        responsible = row.get("РП", "").strip()
        if not key:
            errors.append(f"Строка {index}: пустой target_object_external_key (Ссылка на проект)")
        if not responsible:
            errors.append(f"Строка {index}: пустой ответственный (РП)")
        if key in seen_keys:
            errors.append(f"Строка {index}: дубликат target_object_external_key: {key}")
        seen_keys.add(key)

    if errors:
        return ImportValidationResult(is_valid=False, errors=errors, diff=diff)

    existing = {
        obj.target_object_external_key: obj
        for obj in db.query(TargetObject).filter(TargetObject.project_id == project_id).all()
    }
    for row in rows:
        key = row["Ссылка на проект"].strip()
        if key not in existing:
            diff["create"] += 1
            continue
        current = existing[key]
        new_name = row.get("Проект", "").strip()
        new_responsible = row.get("РП", "").strip()
        if current.target_object_name == new_name and (current.responsible_person_ref or "") == new_responsible:
            diff["no_change"] += 1
        else:
            diff["update"] += 1

    return ImportValidationResult(is_valid=True, errors=[], diff=diff)
