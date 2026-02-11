import logging
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings
from app.request_context import current_endpoint


engine = create_engine(settings.database_url, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_SLOW_QUERY_MS = settings.db_slow_query_ms
_slow_logger = logging.getLogger('app.db.slow_query')


@event.listens_for(engine, 'before_cursor_execute')
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.perf_counter()


@event.listens_for(engine, 'after_cursor_execute')
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start = getattr(context, '_query_start_time', None)
    if start is None:
        return
    duration_ms = (time.perf_counter() - start) * 1000.0
    if duration_ms >= _SLOW_QUERY_MS:
        endpoint = current_endpoint.get()
        sql_text = (statement or '').replace('\n', ' ').strip()
        _slow_logger.warning(
            'slow_query duration_ms=%.2f endpoint=%s sql=%s',
            duration_ms,
            endpoint,
            sql_text,
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
