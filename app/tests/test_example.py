# Import sys module for modifying Python's runtime environment
import sys
# Import os module for interacting with the operating system
import os
import time

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import pytest for writing and running tests
import pytest

def test_dummy():
    """run a simple dummy test"""
    time.sleep(5)
    assert 1+1 == 2