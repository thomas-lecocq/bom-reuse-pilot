from pathlib import Path

import pytest

from bomreuse.generate import write_dataset

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "llm_responses.json"


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("data")
    write_dataset(out)
    return out
