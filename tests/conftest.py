import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    session = TestingSession()
    yield session
    session.close()
