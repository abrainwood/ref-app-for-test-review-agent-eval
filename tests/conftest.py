import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: clones the fixture or spawns pytest; deselect with -m 'not integration'")
