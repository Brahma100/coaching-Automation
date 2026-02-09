import logging

from app.db import Base, SessionLocal, engine
from app.services.bootstrap_service import run_bootstrap


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger('bootstrap')


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = run_bootstrap(db)
        if result.get('ran'):
            logger.info('Bootstrap executed: %s', result)
        else:
            logger.info('Bootstrap skipped: %s', result)
    finally:
        db.close()


if __name__ == '__main__':
    main()
