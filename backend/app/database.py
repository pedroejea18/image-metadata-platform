import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

from common.settings import postgres_options


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    options = postgres_options()
    DATABASE_URL = URL.create(
        "postgresql+psycopg2",
        username=options["user"], password=options["password"],
        host=options["host"], port=options["port"], database=options["dbname"],
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
