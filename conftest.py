import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from common import db,issue
from app import app

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

@pytest.fixture
def subject():
    return str(uuid4())

def auth(subject):
    return {"Authorization":"Bearer "+issue(subject)}
