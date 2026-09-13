from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


connect_args = {}
db_url = settings.database_url
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(db_url, connect_args=connect_args, future=True)
except Exception:
    db_url = "sqlite:///./avsardoot.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, connect_args=connect_args, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_schema():
    """
    Auto-detect and add any columns that exist in SQLAlchemy models but are
    missing from the actual database tables. Safe to call on every startup.
    """
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    with engine.begin() as conn:
        dialect = conn.dialect.name

        for table in Base.metadata.sorted_tables:
            tname = table.name
            if tname not in existing_tables:
                # Table doesn't exist yet — create_all will handle it
                continue

            existing_cols = {c["name"] for c in inspector.get_columns(tname)}

            for col in table.columns:
                if col.name in existing_cols:
                    continue  # already present
                if col.primary_key:
                    continue  # can't add PK after the fact

                # Build a SQLite-compatible type string
                try:
                    col_type = col.type.compile(dialect=conn.dialect)
                except Exception:
                    col_type = "TEXT"

                # Default clause (nullable columns default to NULL)
                default_clause = ""
                if col.default is not None and hasattr(col.default, "arg"):
                    arg = col.default.arg
                    if isinstance(arg, str):
                        default_clause = f" DEFAULT '{arg}'"
                    elif isinstance(arg, (int, float, bool)):
                        default_clause = f" DEFAULT {int(arg)}"

                try:
                    conn.execute(text(
                        f"ALTER TABLE {tname} ADD COLUMN {col.name} {col_type}{default_clause}"
                    ))
                    print(f"[migrate] Added {tname}.{col.name} ({col_type})")
                except Exception as exc:
                    # Already exists or other benign error — ignore
                    pass


