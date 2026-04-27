# Excel Import Contract v1

## Supported file formats

- `.xlsx`
- `.xls`
- `.csv`

## Input columns (exact names)

1. `Дирекция`
2. `Проект`
3. `Статус КТ`
4. `Количество КТ`
5. `Количество этапов`
6. `РП`
7. `Куратор`
8. `Последнее изменение`
9. `Ссылка КТ`
10. `Ссылка на проект`
11. `Статус проекта в КТ`
12. `Статус согласования`

## Required business fields

- `target_object_external_key`
- `target_object_name`
- `responsible_email`

## Processing rules

- Import is atomic: if any blocking validation fails, whole import fails.
- `dry_run` mode is mandatory and returns:
  - validation errors,
  - diff summary: `create/update/no-change`.
- Duplicate `target_object_external_key` in one file is a blocking error.
- Empty `responsible` is a blocking error for whole import.
- Missing owner in people directory creates review task and blocks auto-send for impacted rows.
- If object disappears from next import:
  - assignment remains active,
  - warning is attached.
- Source of truth for target object attributes is Excel.

## Import metadata

- `import_version` (required, unique)
- `imported_at` (required, UTC)
- `imported_by` (required)
- `status`: `draft|validated|applied|failed`

## Apply permissions

- Any role with data mutation permission can apply import in MVP.
