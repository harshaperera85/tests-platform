# Migrations

Alembic environment for the Tests Platform backend. The DB URL and target
metadata come from the app (`alembic/env.py`) so migrations track the ORM.

```bash
# from backend/
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

`versions/0001_baseline.py` is the empty baseline — concrete tables (plan §8)
arrive in Phase 1.
