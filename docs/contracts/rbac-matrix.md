# RBAC Matrix (MVP)

Roles:

- `operator`
- `admin`
- `viewer`

## Permissions

| Action | operator | admin | viewer |
|---|---|---|---|
| View dashboard/lists/details | allow | allow | allow |
| View PII (`email`, `phone`) | allow | allow | allow |
| Update assignment fields | allow | allow | deny |
| Execute assignment actions | allow | allow | deny |
| Manual status override | allow | allow | deny |
| Set `cannot_be_done` | allow | allow | deny |
| Set manual `email_sent_flag` | allow | allow | deny |
| Run verification manually | allow | allow | deny |
| Upload import (dry run) | allow | allow | deny |
| Apply import | allow | allow | deny |
| Edit templates/policies | allow | allow | deny |
| Cancel jobs | allow | allow | deny |
| Retry failed jobs | allow | allow | deny |
| Read jobs page | allow | allow | allow |

## Audit requirements

- All mutating actions must write audit event asynchronously.
- Audit log is append-only.
- Audit includes:
  - actor id,
  - action name,
  - entity type/id,
  - field-level diff,
  - correlation id,
  - timestamp.
