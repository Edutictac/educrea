import os
from cryptography.fernet import Fernet

os.environ["EDUCREA_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["EDUCREA_COOKIE_SECURE"] = "false"
os.environ["EDUCREA_CREDENTIAL_KEYS"] = Fernet.generate_key().decode()
os.environ["EDUCREA_GEMINI_FREE_MODELS"] = "gemini-test-free"
os.environ["EDUCREA_OPENROUTER_FREE_MODELS"] = "test/model:free"
os.environ["EDUCREA_GROQ_FREE_MODELS"] = "groq-test-free"
os.environ["EDUCREA_MISTRAL_FREE_MODELS"] = "mistral-small-latest"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from educrea_api.db import Base, get_db
from educrea_api.main import app

engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@pytest.fixture
def client():
    Base.metadata.create_all(engine)

    def db_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)

