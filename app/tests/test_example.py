# Import sys module for modifying Python's runtime environment
import sys
# Import os module for interacting with the operating system
import os
import time

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app instance from the main app file
from app import app
# Import pytest for writing and running tests
import pytest

@pytest.fixture
def client():
    """A test client for the app."""
    with app.test_client() as client:
        yield client

def test_non_existent_route(client):
    """Test for a non-existent route."""
    response = client.get('/non-existent')
    assert response.status_code == 404


def test_dummy(client):
    """run a simple dummy test"""
    time.sleep(5)
    assert 1+1 == 2