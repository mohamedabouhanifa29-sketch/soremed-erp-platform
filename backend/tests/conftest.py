"""Isole les tests dans une base SQLite supprimée en fin de session."""
import os
from pathlib import Path
TEST_DATABASE = Path("database/test-suite.db").resolve()
BACKUP_DIRECTORY = Path("database/backups").resolve()
INITIAL_BACKUPS = set(BACKUP_DIRECTORY.glob("*")) if BACKUP_DIRECTORY.exists() else set()
os.environ["DATABASE_URL"] = "sqlite:///./database/test-suite.db"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-deployment"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "test-admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "test-only-password"
def pytest_sessionfinish(session, exitstatus):
    from app.database.session import engine
    engine.dispose()
    TEST_DATABASE.unlink(missing_ok=True)
    if BACKUP_DIRECTORY.exists():
        for generated in set(BACKUP_DIRECTORY.glob("*")) - INITIAL_BACKUPS:
            generated.unlink(missing_ok=True)
