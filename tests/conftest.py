import os
os.environ['DATABASE_URL']='sqlite:///./test_sat_coach.db'
os.environ['DIAGNOSTIC_PROVIDER']='rule_based'
import pytest
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import engine
from app.main import app
@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine); yield; Base.metadata.drop_all(bind=engine)
@pytest.fixture
def client():
    with TestClient(app) as c: yield c
