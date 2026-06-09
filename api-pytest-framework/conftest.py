import sys
import os
import re
import pytest
import requests
import config
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "features"))


def pytest_collection_modifyitems(config, items):
    """Convertit les tags Gherkin (@smoke, @critical...) en marks pytest."""
    features_dir = Path(__file__).parent / "features"
    tc_tags: dict[int, set] = {}

    for feat_file in features_dir.glob("*.feature"):
        text = feat_file.read_text(encoding="utf-8")
        lines = text.splitlines()
        pending_tags: set = set()
        feature_tags: set = set()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Feature:"):
                feature_tags = set(pending_tags)
                pending_tags = set()
            elif re.match(r"^@", stripped):
                for tag in re.findall(r"@([\w-]+)", stripped):
                    pending_tags.add(tag)
            elif stripped.startswith("Scenario:"):
                all_tags = feature_tags | pending_tags
                tc_match = re.search(r"TC-(\d+)", stripped)
                if tc_match:
                    tc_tags[int(tc_match.group(1))] = all_tags
                pending_tags = set()
            elif stripped and not stripped.startswith("#"):
                pending_tags = set()

    for item in items:
        m = re.search(r"tc0*(\d+)", item.name, re.IGNORECASE)
        if m:
            tc_num = int(m.group(1))
            for tag in tc_tags.get(tc_num, set()):
                clean = re.sub(r"[^a-zA-Z0-9_]", "_", tag)
                if clean:
                    item.add_marker(getattr(pytest.mark, clean))


@pytest.fixture(scope="session")
def base_url():
    return config.BASE_URL


@pytest.fixture(scope="session")
def token(base_url):
    response = requests.post(
        f"{base_url}/auth",
        json={"username": config.USERNAME, "password": config.PASSWORD}
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json().get("token")


@pytest.fixture
def ctx():
    """Contexte mutable partagé entre tous les steps d'un scénario BDD."""
    return {}
