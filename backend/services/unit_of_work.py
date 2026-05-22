try:
    from backend.database import SessionLocal
except ModuleNotFoundError:
    from database import SessionLocal


class UnitOfWork:
    """Context manager transaccional para operaciones de auditoria."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.session = None

    def __enter__(self):
        self.session = self.session_factory()
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type:
                self.session.rollback()
            else:
                self.session.commit()
        finally:
            self.session.close()

        return False
