import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Center
from app.services.rate_limit_service import SafeRateLimitError, check_rate_limit


def _utc(y, m, d, hh=0, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


def test_rate_limit_blocks_after_threshold_and_resets():
    tmpdir = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmpdir.name) / 'test_rate_limit.db'
        engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        db = Session()
        try:
            db.add(Center(id=1, name='Center A', slug='center-a'))
            db.commit()

            base = _utc(2026, 2, 16, 12, 0, 0)
            with patch('app.services.rate_limit_service.default_time_provider.now', return_value=base):
                for _ in range(20):
                    assert check_rate_limit(
                        db,
                        center_id=1,
                        scope_type='user',
                        scope_key='42',
                        action_name='commands_generate_token',
                        max_requests=20,
                        window_seconds=60,
                    )
                with pytest.raises(SafeRateLimitError):
                    check_rate_limit(
                        db,
                        center_id=1,
                        scope_type='user',
                        scope_key='42',
                        action_name='commands_generate_token',
                        max_requests=20,
                        window_seconds=60,
                    )

            with patch('app.services.rate_limit_service.default_time_provider.now', return_value=base + timedelta(seconds=61)):
                assert check_rate_limit(
                    db,
                    center_id=1,
                    scope_type='user',
                    scope_key='42',
                    action_name='commands_generate_token',
                    max_requests=20,
                    window_seconds=60,
                )
        finally:
            db.close()
            engine.dispose()
    finally:
        tmpdir.cleanup()
